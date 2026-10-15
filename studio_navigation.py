"""Three-model community navigation."""
MODELS = [('qwen', 'Qwen3-TTS'), ('index', 'IndexTTS 2.5'), ('spark', 'Spark-TTS')]


def model_tabs(active=None):
    return '<nav class="model-tabs" aria-label="配音模型">' + ''.join(
        f'<a href="/{key}" id="{key}Tab"' + (' class="active" aria-current="page"' if key == active else '') +
        f'>{name}</a>' for key, name in MODELS) + '</nav>'
