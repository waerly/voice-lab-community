"""Create local IndexTTS reference voices from Qwen's native CustomVoice presets."""
import base64
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
from app_config import PORT
BASE = f'http://127.0.0.1:{PORT}'
TEXT = '你好，我是你的讲述伙伴。今天，我们一起发现生活里的小知识。'
STYLES = [
    dict(id='gentle',name='轻柔讲述',speaker='Serena',instruction='用温柔、舒缓、自然的普通话讲述，像给朋友讲故事。',emotion='reference',intensity=.5,duration_factor=1),
    dict(id='bright',name='活泼科普',speaker='Vivian',instruction='用明快、亲切、有好奇心的普通话讲解，轻松活泼，发音清晰。',emotion='reference',intensity=.5,duration_factor=1),
    dict(id='steady',name='沉稳解说',speaker='Uncle_Fu',instruction='用沉稳、清晰、自然的普通话解说，语气从容，适合知识讲解。',emotion='reference',intensity=.5,duration_factor=1),
]


def request(path, value=None):
    req = urllib.request.Request(BASE+path,data=json.dumps(value).encode() if value is not None else None,
                                 headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=40) as response:
        return json.load(response)


def main():
    target=ROOT/'data/builtin-styles.json'
    if target.exists():
        raise SystemExit('内置风格已存在，不覆盖已有配置。')
    for style in STYLES:
        print('Preparing',style['name'],flush=True)
        job=request('/api/generate',dict(engines=['qwen'],mode='custom',text=TEXT,
                                        speaker=style['speaker'],instruction=style['instruction']))['jobs'][0]
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            state=request('/api/state')
            result=next(j for j in state['jobs'] if j['id']==job['id'])
            if result['status'] not in ('running','queued'):
                break
            time.sleep(2)
        else:
            raise RuntimeError('内置声音准备超时，请查看页面中的任务')
        if result['status']!='done':
            raise RuntimeError(result.get('error',result['status']))
        audio=Path(result['output']).read_bytes()
        ref=request('/api/reference',dict(name='内置 · '+style['name']+'（Qwen 合成）',
                                         transcript=TEXT,audio=base64.b64encode(audio).decode()))
        style.update(reference_id=ref['id'],source='Qwen3-TTS CustomVoice 合成',sample_job_id=result['id'])
        print('Ready',style['name'],ref['duration'],'seconds',flush=True)
    target.write_text(json.dumps(STYLES,ensure_ascii=False,indent=2))
    print('BUILTIN STYLES READY',flush=True)


if __name__=='__main__':
    main()
