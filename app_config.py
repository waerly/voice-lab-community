"""All writable data stays in this project; only dependencies may be reused locally."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get('VOICE_LAB_PORT', '8776'))
if not 1024 <= PORT <= 65535:
    raise ValueError('VOICE_LAB_PORT 应为 1024～65535')
config = ROOT / 'local_runtime.json'
local = json.loads(config.read_text()) if config.exists() else {}
RUNTIME = Path(os.environ.get('VOICE_LAB_RUNTIME', local.get('runtime', ROOT/'runtime'))).expanduser().resolve()
