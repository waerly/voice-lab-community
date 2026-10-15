"""Reusable synthetic voices; keep samples independent of disposable job audio."""
import json
import shutil
import uuid
import wave


def save_role(data, job_id, name, save):
    name = str(name or '').strip()
    if not name or len(name) > 80:
        raise ValueError('角色名称应为 1～80 字')
    path = data / 'jobs' / (job_id + '.json')
    if not path.is_file():
        raise ValueError('生成记录不存在')
    job = json.loads(path.read_text())
    audio = data / 'audio' / (job_id + '.wav')
    if job['status'] != 'done' or not audio.is_file():
        raise ValueError('只能保存已成功生成的声音')
    with wave.open(str(audio)) as wav:
        duration = wav.getnframes() / wav.getframerate()
    if not 3 <= duration <= 30:
        raise ValueError('角色样音需为 3～30 秒，请用短文重新生成；不会自动裁剪以免文字错位')
    identity = uuid.uuid4().hex
    target = data / 'references' / (identity + '.wav')
    ref = dict(id=identity, name=name, transcript=job['text'], duration=round(duration, 2),
               path=str(target), synthetic=True, source_job=job_id,
               source_model=job['model'], source_parameters={k: job.get(k) for k in
               ('mode', 'speaker', 'instruction', 'gender', 'spark_pitch', 'spark_speed', 'spark_seed', 'emotion', 'intensity', 'duration_factor')})
    shutil.copy2(audio, target)
    save(target.with_suffix('.json'), ref)
    return ref
