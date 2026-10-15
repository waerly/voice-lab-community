"""UI descriptions of speakers verified against the official CustomVoice card."""
import json
from pathlib import Path
from app_config import RUNTIME

SOURCE = 'https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice'
# Display labels are Chinese summaries; IDs are the unchanged model identifiers.
SPEAKERS = [
    dict(id='Vivian', gender='女声', name='明亮年轻女声', native='中文',
         description='声音明亮，略带个性与棱角的年轻女声。'),
    dict(id='Serena', gender='女声', name='温暖柔和女声', native='中文',
         description='温暖、温柔的年轻女声。'),
    dict(id='Ono_Anna', gender='女声', name='轻盈俏皮女声', native='日语',
         description='俏皮、轻盈，表达灵动的日语女声。'),
    dict(id='Sohee', gender='女声', name='温暖细腻女声', native='韩语',
         description='温暖、情感表达丰富的韩语女声。'),
    dict(id='Uncle_Fu', gender='男声', name='低沉醇厚男声', native='中文',
         description='成熟男声，音色低沉、圆润醇厚。'),
    dict(id='Dylan', gender='男声', name='清朗青年男声', native='中文·北京话',
         description='年轻北京男声，音色清晰、自然。', dialect=True),
    dict(id='Eric', gender='男声', name='活泼微沙男声', native='中文·四川话',
         description='活泼的成都男声，明亮中带一点沙哑。', dialect=True),
    dict(id='Ryan', gender='男声', name='动感节奏男声', native='英语',
         description='有活力，节奏感鲜明的英语男声。'),
    dict(id='Aiden', gender='男声', name='阳光清晰男声', native='英语·美式',
         description='阳光的美式男声，中音区清晰。'),
]


def qwen_speakers():
    config = RUNTIME / 'models/qwen-custom/config.json'
    if not config.is_file():
        return []
    installed = json.loads(config.read_text())['talker_config']['spk_id']
    return [dict(s, label=f'{s["name"]} · {s["id"]} · {s["native"]}', source=SOURCE)
            for s in SPEAKERS if s['id'].lower() in installed]
