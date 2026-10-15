"""Local three-model community laboratory with private local data."""
import base64
import binascii
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from speaker_catalog import qwen_speakers
from studio_navigation import model_tabs
from app_config import ROOT, RUNTIME, PORT
from role_library import save_role
from spark_controls import spark_controls
from job_history import query_jobs
from index_resources import ensure_index_ready, wait_for_index, stop_process, IndexResourceError
from urllib.parse import urlsplit, parse_qs

DATA = ROOT / 'data'
LOCK = threading.Lock()
RUN_LOCK = threading.Lock()
CANCEL = threading.Event()
PROCESS = None
ACTIVE = None


def builtin_styles():
    path = DATA / 'builtin-styles.json'
    return json.loads(path.read_text()) if path.is_file() else []


def save(path, obj):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    tmp.replace(path)


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{32}', value):
        raise ValueError('无效的记录编号')
    return value


def readiness():
    states = {engine: {'installed': (RUNTIME / env / 'bin/python').exists() and marker.exists(),
                     'name': name}
            for engine, env, marker, name in [
                ('qwen', 'qwen-venv', RUNTIME / 'models/qwen.ready', 'Qwen3-TTS 1.7B · MLX 8-bit'),
                ('index', 'index-tts/.venv', RUNTIME / 'models/index.ready', 'IndexTTS 2.5 · MPS')
            ]}
    def qwen_files(variant):
        root = RUNTIME/'models'/variant
        return all((root/f).is_file() for f in ['config.json','model.safetensors','tokenizer_config.json',
                   'vocab.json','merges.txt','speech_tokenizer/config.json','speech_tokenizer/model.safetensors'])
    states['qwen']['installed'] = qwen_files('qwen-base')
    states['qwen']['custom_ready'] = qwen_files('qwen-custom')
    checkpoint = RUNTIME/'index-tts/checkpoints'
    states['index']['installed'] = all((checkpoint/f).is_file() for f in [
        'config.yaml','gpt.pth','codec.pth','s2mel.pth','feat1.pt','feat2.pt',
        'wav2vec2bert_stats.pt','multilingual_zh_ja_yue_char_del.tiktoken',
        'hf_cache/w2v-bert-2.0/config.json','hf_cache/w2v-bert-2.0/model.safetensors',
        'hf_cache/w2v-bert-2.0/preprocessor_config.json','hf_cache/campplus_cn_common.bin',
        'hf_cache/bigvgan/config.json','hf_cache/bigvgan/bigvgan_generator.pt'])
    states['qwen']['design_ready'] = qwen_files('qwen-design')
    states['spark'] = {'name': 'Spark-TTS 0.5B · MLX', 'installed': all((RUNTIME/'models/spark'/f).is_file() for f in ['config.json', 'model.safetensors', 'tokenizer.json', 'tokenizer_config.json', 'BiCodec/config.yaml', 'BiCodec/model.safetensors', 'wav2vec2-large-xlsr-53/config.json', 'wav2vec2-large-xlsr-53/model.safetensors', 'wav2vec2-large-xlsr-53/preprocessor_config.json'])}
    return states


def run(jobs):
    global PROCESS, ACTIVE
    try:
        for job in jobs:
            path = DATA / 'jobs' / (job['id'] + '.json')
            with LOCK:
                ACTIVE = job['id']
                if CANCEL.is_set():
                    job['status'] = 'cancelled'
                    save(path, job)
                    continue
                job.update(status='running', started=time.time())
                save(path, job)
            log_path = path.with_suffix('.log')
            env = os.environ.copy()
            env.update(PYTHONUNBUFFERED='1', HF_HOME=str(DATA / 'cache/hf'),
                       MPLCONFIGDIR=str(DATA / 'cache/matplotlib'), NLTK_DATA=str(RUNTIME / 'nltk-data'),
                       HF_HUB_DISABLE_XET='1', PYTORCH_ENABLE_MPS_FALLBACK='1',
                       PYTHONPATH=str(RUNTIME / 'index-tts'))
            if job['engine'] == 'index':
                env.update(OMP_NUM_THREADS='4', VECLIB_MAXIMUM_THREADS='4',
                           PYTORCH_MPS_HIGH_WATERMARK_RATIO='0.5',
                           PYTORCH_MPS_LOW_WATERMARK_RATIO='0.4')
            python = RUNTIME / ('qwen-venv' if job['engine'] != 'index' else 'index-tts/.venv') / 'bin/python'
            cwd = RUNTIME / 'index-tts' if job['engine'] == 'index' else ROOT
            try:
                if job['engine'] == 'index':
                    ensure_index_ready(job['text'])
                with log_path.open('w') as log:
                    with LOCK:
                        if CANCEL.is_set():
                            continue
                        PROCESS = subprocess.Popen([str(python), str(ROOT / 'worker.py'), str(path)],
                                                   cwd=cwd, env=env, stdout=log, stderr=log,
                                                   start_new_session=True)
                    try:
                        code = (wait_for_index(PROCESS, CANCEL.is_set) if job['engine'] == 'index'
                                else PROCESS.wait(timeout=480))
                    except subprocess.TimeoutExpired:
                        stop_process(PROCESS)
                        raise RuntimeError('本次生成超过 8 分钟，已停止。请缩短文案后再试。')
                with LOCK:
                    if job['status'] != 'cancelled':
                        if code != 0 or not Path(job['output']).is_file():
                            if job['engine'] == 'index':
                                tail = log_path.read_text(errors='replace')[-5000:]
                                if 'out of memory' in tail.lower() or '内存保护' in tail:
                                    raise IndexResourceError('IndexTTS 内存保护：已停止本次生成，避免继续占用内存。请关闭占内存的应用或改用轻量模型。')
                            raise RuntimeError('模型生成失败，请展开运行日志查看原因。')
                        job['status'] = 'done'
            except Exception as error:
                with LOCK:
                    if job['status'] != 'cancelled':
                        job.update(status='failed', error=str(error))
            finally:
                if PROCESS is not None and PROCESS.poll() is None:
                    stop_process(PROCESS)
                if job['engine'] == 'index' and job['status'] != 'done':
                    Path(job['output']).with_suffix('.partial.wav').unlink(missing_ok=True)
                with LOCK:
                    if CANCEL.is_set():
                        job['status'] = 'cancelled'
                    job['elapsed'] = round(time.time() - job['started'], 1)
                    save(path, job)
                    PROCESS = None
        with LOCK:
            ACTIVE = None
    finally:
        RUN_LOCK.release()


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, value):
        content = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(content)

    def allowed(self):
        hosts = {f'127.0.0.1:{PORT}', f'localhost:{PORT}'}
        return self.headers.get('Host') in hosts and self.headers.get('Origin', f'http://127.0.0.1:{PORT}') in {f'http://{h}' for h in hosts}

    def do_GET(self):
        if not self.allowed():
            return self.reply(403, {'error': '仅限本地访问'})
        path = self.path.split('?')[0]
        if path == '/api/jobs':
            try:
                with LOCK:
                    result = query_jobs(DATA, parse_qs(urlsplit(self.path).query))
                return self.reply(200, result)
            except (ValueError, TypeError):
                return self.reply(400, {'error': '无效的历史筛选或分页参数'})
        if path == '/api/state':
            with LOCK:
                refs = [json.loads(p.read_text()) for p in sorted((DATA / 'references').glob('*.json'))]
                paths = sorted((DATA / 'jobs').glob('*.json'), key=lambda p:p.stat().st_mtime, reverse=True)
                jobs = []
                for p in paths:
                    job = json.loads(p.read_text())
                    if not job.get('deleted_at'):
                        jobs.append(job)
                    if len(jobs) == 40:
                        break
            for job in jobs:
                log = DATA / 'jobs' / (job['id'] + '.log')
                job['log'] = log.read_text(errors='replace')[-3500:] if log.exists() else ''
            return self.reply(200, dict(engines=readiness(), references=refs, jobs=jobs,
                                        styles=builtin_styles(), speakers=qwen_speakers(), busy=RUN_LOCK.locked()))
        if path in ('/', '/qwen', '/index', '/spark'):
            file, mime = ROOT / 'index.html', 'text/html; charset=utf-8'
        elif path in ('/classic.css', '/job_list.js', '/spark_controls.js', '/generation_context.js'):
            file = ROOT / path[1:]
            mime = 'text/css; charset=utf-8' if path.endswith('.css') else 'text/javascript; charset=utf-8'
        elif path == '/voice_tools.js':
            file, mime = ROOT / 'voice_tools.js', 'text/javascript; charset=utf-8'
        elif re.fullmatch(r'/audio/[a-f0-9]{32}\.wav', path):
            file, mime = DATA / 'audio' / path.rsplit('/',1)[1], 'audio/wav'
        elif re.fullmatch(r'/reference/[a-f0-9]{32}\.wav', path):
            file, mime = DATA / 'references' / path.rsplit('/',1)[1], 'audio/wav'
        else:
            return self.reply(404, {'error': '地址不存在'})
        if not file.is_file():
            return self.reply(404, {'error': '文件不存在'})
        content = file.read_bytes()
        if file.name == 'index.html':
            active = self.path.split('?')[0].strip('/') or 'qwen'
            content = content.replace(b'<!--MODEL_TABS-->', model_tabs(active).encode())
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        if not self.allowed():
            return self.reply(403, {'error': '仅限本地访问'})
        acquired = False
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size < 30_000_000:
                raise ValueError('请求过大，请上传 20 MB 以内的音频')
            value = json.loads(self.rfile.read(size))
            if self.path == '/api/jobs/delete':
                identity = identifier(value.get('id'))
                delete_audio = value.get('delete_audio', False)
                if not isinstance(delete_audio, bool):
                    raise ValueError('无效的文件删除选项')
                path = DATA / 'jobs' / (identity + '.json')
                with LOCK:
                    if not path.is_file():
                        return self.reply(404, {'error': '记录不存在'})
                    job = json.loads(path.read_text())
                    if job['status'] in ('queued', 'running') or identity == ACTIVE:
                        return self.reply(409, {'error': '任务尚未结束，请等待完成后再删除'})
                    if delete_audio:
                        # Derive paths from the validated id; never trust a saved output path.
                        (DATA / 'audio' / (identity + '.wav')).unlink(missing_ok=True)
                        path.with_suffix('.log').unlink(missing_ok=True)
                        path.unlink()
                    else:
                        job['deleted_at'] = job.get('deleted_at') or time.time()
                        save(path, job)
                return self.reply(200, {'ok': True})
            if self.path == '/api/roles':
                with LOCK:
                    ref = save_role(DATA, identifier(value.get('job_id')), value.get('name'), save)
                return self.reply(200, ref)
            if self.path == '/api/reference':
                name = str(value.get('name', '')).strip()[:80]
                transcript = str(value.get('transcript', '')).strip()[:1000]
                if not name:
                    raise ValueError('请为参考声音命名')
                content = base64.b64decode(value['audio'], validate=True)
                identity = uuid.uuid4().hex
                raw = DATA / 'references' / (identity + '.upload')
                wav = raw.with_suffix('.wav')
                raw.write_bytes(content)
                try:
                    subprocess.run(['ffmpeg','-y','-v','error','-i',str(raw),'-t','31','-ar','24000','-ac','1',str(wav)],
                                   check=True, timeout=30, capture_output=True)
                    import wave
                    with wave.open(str(wav)) as audio:
                        duration = audio.getnframes()/audio.getframerate()
                    if not 3 <= duration <= 30:
                        wav.unlink(missing_ok=True)
                        raise ValueError('参考录音请控制在 3～30 秒')
                finally:
                    raw.unlink(missing_ok=True)
                ref = dict(id=identity, name=name, transcript=transcript, duration=round(duration,2), path=str(wav))
                with LOCK:
                    save(wav.with_suffix('.json'), ref)
                return self.reply(200, ref)
            if self.path == '/api/cancel':
                with LOCK:
                    CANCEL.set()
                    for p in (DATA / 'jobs').glob('*.json'):
                        job = json.loads(p.read_text())
                        if job['status'] in ('queued', 'running'):
                            job['status'] = 'cancelled'
                            save(p, job)
                    if PROCESS and PROCESS.poll() is None:
                        os.killpg(PROCESS.pid, signal.SIGTERM)
                return self.reply(200, {'ok': True})
            if self.path != '/api/generate':
                return self.reply(404, {'error': '接口不存在'})
            engines = value.get('engines', [])
            if engines not in (['qwen'], ['index'], ['spark'], ['qwen','index']):
                raise ValueError('请选择有效模型')
            if any(not readiness()[e]['installed'] for e in engines):
                raise ValueError('模型尚未安装完成，请等待准备状态更新')
            text = str(value.get('text', '')).strip()
            if not 1 <= len(text) <= 1500:
                raise ValueError('试听文案应为 1～1500 字')
            mode = value.get('mode', 'clone') if len(engines)==1 else 'clone'
            if mode not in ('clone','custom','design') or (engines == ['index'] and mode != 'clone') or (engines == ['spark'] and mode == 'custom'):
                raise ValueError('无效的生成模式')
            if 'qwen' in engines and mode=='custom' and not readiness()['qwen']['custom_ready']:
                raise ValueError('Qwen 预设音色模型仍在下载，请先使用克隆模式')
            controls = spark_controls(value, mode) if engines == ['spark'] else {}
            instruction = str(value.get('instruction', '')).strip()[:300]
            gender = value.get('gender', 'female')
            if gender not in ('female', 'male'):
                raise ValueError('无效的声音性别')
            if mode == 'design' and engines == ['qwen']:
                if not readiness()['qwen']['design_ready']:
                    raise ValueError('请先下载 Qwen VoiceDesign 模型：python download_models.py design')
                if not instruction:
                    raise ValueError('请填写音色描述')
            if mode == 'design' and len(text) > 120:
                raise ValueError('创建角色请先使用 120 字以内的短文，满意后保存为角色再克隆长文')
            ref = None
            if 'index' in engines or mode == 'clone':
                ref_path = DATA / 'references' / (identifier(value.get('reference_id')) + '.json')
                if not ref_path.is_file():
                    raise ValueError('请先保存参考录音')
                ref = json.loads(ref_path.read_text())
                if 'qwen' in engines and not ref['transcript']:
                    raise ValueError('Qwen 克隆需要填写参考录音对应的文字')
            emotion = value.get('emotion','reference')
            if emotion not in ('reference','happy','sad','surprised','calm'):
                raise ValueError('无效的情绪')
            intensity = float(value.get('intensity', .5))
            duration = float(value.get('duration_factor', 1))
            if not math.isfinite(intensity) or not 0<=intensity<=1 or not math.isfinite(duration) or not .5<=duration<=2:
                raise ValueError('情绪强度或时长倍率超出范围')
            speaker = value.get('speaker', 'Vivian')
            if 'qwen' in engines and mode == 'custom' and speaker not in {s['id'] for s in qwen_speakers()}:
                raise ValueError('无效的预设音色')
            preset = next((p for p in builtin_styles() if p['id'] == value.get('preset_id')), None)
            if 'index' in engines:
                ensure_index_ready(text)
            acquired = RUN_LOCK.acquire(blocking=False)
            if not acquired:
                return self.reply(409, {'error':'已有任务正在生成，请等待或停止当前任务'})
            group = uuid.uuid4().hex
            CANCEL.clear()
            jobs = []
            for engine in engines:
                identity = uuid.uuid4().hex
                job = dict(id=identity, group=group, engine=engine, model=readiness()[engine]['name'],
                           mode=mode if engine!='index' else 'clone', text=text, reference=ref,
                           speaker=speaker, instruction=instruction, gender=gender,
                           emotion=emotion, intensity=intensity, duration_factor=duration,
                           style_name=preset['name'] if preset else None,
                           style_adjusted=bool(preset and (
                               (engine=='qwen' and mode=='custom' and
                                (speaker!=preset['speaker'] or value.get('instruction','')!=preset['instruction'])) or
                               ((engine=='index' or mode=='clone') and
                                (not ref or ref['id']!=preset['reference_id'])) or
                               (engine=='index' and (emotion!=preset['emotion'] or duration!=preset['duration_factor'])))),
                           status='queued', created=time.time(), output=str(DATA/'audio'/(identity+'.wav')))
                if engine == 'index':
                    job['index_runtime'] = dict(mode='stable', num_beams=1, segment_chars=40,
                                                reference_seconds=8, max_mel_tokens=768)
                if engine == 'qwen' and mode == 'design':
                    job['voice_design_template'] = str(value.get('voice_design_template', ''))[:80]
                    job['voice_design_modified'] = bool(value.get('voice_design_modified', False))
                if engine == 'qwen':
                    job['model_variant'] = {'clone': 'Base', 'custom': 'CustomVoice', 'design': 'VoiceDesign'}[mode]
                job.update(controls)
                save(DATA/'jobs'/(identity+'.json'),job)
                jobs.append(job)
            threading.Thread(target=run,args=(jobs,),daemon=True).start()
            acquired = False
            return self.reply(202, {'jobs':jobs})
        except (ValueError, KeyError, TypeError, binascii.Error) as error:
            return self.reply(400, {'error':str(error)})
        except IndexResourceError as error:
            self.reply(409, {'error': str(error)})
        except (subprocess.SubprocessError, OSError) as error:
            return self.reply(500, {'error':'音频处理失败：'+str(error)})
        finally:
            if acquired:
                RUN_LOCK.release()


if __name__ == '__main__':
    for folder in ['references','jobs','audio']:
        (DATA/folder).mkdir(parents=True,exist_ok=True)
    for p in (DATA/'jobs').glob('*.json'):
        j=json.loads(p.read_text())
        if j['status'] in ('queued','running'):
            j.update(status='failed',error='服务重启，请重新生成')
            save(p,j)
    print(f'语音对比实验室 http://127.0.0.1:{PORT}',flush=True)
    def stop_service(signum, frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop_service)
    try:
        ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
    finally:
        if PROCESS is not None:
            stop_process(PROCESS)
