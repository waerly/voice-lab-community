"""Read-only filtering and pagination over saved synthesis jobs."""
import json
import math
import re
import unicodedata
import wave
from datetime import date, datetime, time, timedelta, timezone
from speaker_catalog import SPEAKERS

BEIJING = timezone(timedelta(hours=8))
SPEAKER_NAMES = {s["id"]: s["name"] for s in SPEAKERS}


def display_role(job):
    if job.get("engine") == "qwen" and job.get("mode") == "design" and job.get("voice_design_template"):
        return job["voice_design_template"] + ("（描述已调整）" if job.get("voice_design_modified") else "")
    if job.get("style_name"):
        return job["style_name"]
    if job.get("mode") == "custom":
        return SPEAKER_NAMES.get(job.get("speaker"), job.get("speaker")) or "未命名声音"
    if job.get("mode") == "design":
        return "新设计音色"
    return (job.get("reference") or {}).get("name") or "未命名声音"


def normalize(value):
    return unicodedata.normalize("NFKC", str(value or "")).casefold()


def date_bound(value, exclusive_end=False):
    if not value:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("日期格式应为 YYYY-MM-DD")
    try:
        day = date.fromisoformat(value)
        if exclusive_end:
            day += timedelta(days=1)
        return datetime.combine(day, time.min, tzinfo=BEIJING).timestamp()
    except (ValueError, OverflowError) as error:
        raise ValueError("请选择有效日期") from error


def saved_jobs(data):
    for path in (data / 'jobs').glob('*.json'):
        try:
            yield json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue


def query_jobs(data, query):
    def field(key, default=''):
        return query.get(key, [default])[0]
    page = int(field('page', '1'))
    size = int(field('page_size', '10'))
    engine, status, mode = field('engine'), field('status'), field('mode')
    keyword = normalize(field('q')).strip()
    terms = keyword.split()
    start = date_bound(field('start_date'))
    end = date_bound(field('end_date'), exclusive_end=True)
    if start is not None and end is not None and start >= end:
        raise ValueError('开始日期不能晚于结束日期')
    if page < 1 or size not in (10, 20, 50):
        raise ValueError('无效的页码或每页条数')
    if engine not in ('', 'qwen', 'index', 'spark') or status not in ('', 'done', 'failed', 'running', 'queued', 'cancelled') or mode not in ('', 'clone', 'custom', 'design'):
        raise ValueError('无效的筛选条件')
    if len(keyword) > 200:
        raise ValueError('关键词最多 200 字')
    records = []
    for job in saved_jobs(data):
        if job.get('deleted_at'):
            continue
        if any(value and job.get(key) != value for key, value in [('engine', engine), ('status', status), ('mode', mode)]):
            continue
        created = job.get('created', 0)
        if (start is not None and created < start) or (end is not None and created >= end):
            continue
        if job.get('engine') == 'qwen':
            job.setdefault('model_variant', {'clone': 'Base', 'custom': 'CustomVoice', 'design': 'VoiceDesign'}.get(job.get('mode'), ''))
        job['display_role'] = display_role(job)
        search = job['display_role'] + ' ' + ' '.join(str(job.get(k) or '') for k in ('text', 'style_name', 'speaker', 'model', 'model_variant', 'instruction'))
        search += ' ' + str((job.get('reference') or {}).get('name', ''))
        search = normalize(search)
        if terms and not all(term in search for term in terms):
            continue
        records.append(job)
    records.sort(key=lambda j: (j.get('created', 0), j['id']), reverse=True)
    total = len(records)
    pages = max(1, math.ceil(total / size))
    page = min(page, pages)
    items = records[(page - 1) * size:page * size]
    for job in items:
        job['audio_duration'] = None
        if job.get('status') == 'done':
            audio_path = data / 'audio' / (job['id'] + '.wav')
            try:
                with wave.open(str(audio_path)) as audio:
                    job['audio_duration'] = round(audio.getnframes() / audio.getframerate(), 1)
            except (OSError, EOFError, wave.Error):
                pass
        log = data / 'jobs' / (job['id'] + '.log')
        job['log'] = log.read_text(errors='replace')[-3500:] if log.exists() else ''
    return dict(jobs=items, total=total, page=page, pages=pages, page_size=size)
