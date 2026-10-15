"""One isolated model process per synthesis; its parent owns timeout and cancellation."""
import argparse
import json
import os
import re
from pathlib import Path
import time

from app_config import ROOT, RUNTIME


def text_segments(text, limit=120):
    segments, current = [], ''
    for sentence in re.findall(r'[^。！？\n]+[。！？\n]*|[。！？\n]+', text):
        if current and len(current) + len(sentence) > limit:
            segments.append(current)
            current = ''
        while len(sentence) > limit:
            segments.append(sentence[:limit])
            sentence = sentence[limit:]
        current += sentence
    if current:
        segments.append(current)
    return segments


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('job')
    args = parser.parse_args()
    job = json.loads(Path(args.job).read_text())
    start = time.monotonic()
    print('正在加载模型…', flush=True)
    if job['engine'] in ('qwen', 'spark'):
        import mlx.core as mx
        import numpy as np
        import soundfile as sf
        from mlx_audio.tts.utils import load_model
        mx.random.seed(job.get('spark_seed', 42) if job['engine'] == 'spark' else 42)
        mode = job['mode']
        variant = 'spark' if job['engine'] == 'spark' else {'clone': 'qwen-base', 'custom': 'qwen-custom', 'design': 'qwen-design'}[mode]
        model = load_model(str(RUNTIME / 'models' / variant))
        if job['engine'] == 'spark':
            # MLX-Audio's tokenizer is not a child Module: explicitly disable
            # training BatchNorm/dropout for single-reference inference.
            model._audio_tokenizer.model.eval()
            model._audio_tokenizer.feature_extractor.eval()
        print('模型已加载，开始生成普通话…', flush=True)
        chunks = []
        rate = 24000
        segments = text_segments(job['text'])
        for i, text in enumerate(segments):
            print(f'生成文案分段 {i+1}/{len(segments)}', flush=True)
            if job['engine'] == 'spark':
                options = dict(ref_audio=job['reference']['path'], ref_text=job['reference']['transcript']) if mode == 'clone' else dict(gender=job['gender'], pitch=job.get('spark_pitch', 1.0), speed=job.get('spark_speed', 1.0))
                results = model.generate(text=text, max_tokens=2048, **options)
            elif mode == 'design':
                results = model.generate_voice_design(text=text, instruct=job['instruction'], language='Chinese', max_tokens=2048)
            elif mode == 'clone':
                results = model.generate(text=text, ref_audio=job['reference']['path'],
                                         ref_text=job['reference']['transcript'], lang_code='Chinese',
                                         max_tokens=2048)
            else:
                results = model.generate_custom_voice(text=text, speaker=job['speaker'],
                                                     language='Chinese', instruct=job['instruction'],
                                                     max_tokens=2048)
            segment_audio = []
            for result in results:
                mx.eval(result.audio)
                segment_audio.append(np.asarray(result.audio))
                rate = result.sample_rate
                print('已生成音频片段', flush=True)
            if not segment_audio:
                raise RuntimeError(f'第 {i+1} 段未返回音频')
            if chunks:
                chunks.append(np.zeros(round(rate * .2), dtype=segment_audio[0].dtype))
            chunks.extend(segment_audio)
        if not chunks:
            raise RuntimeError('模型未返回音频')
        sf.write(job['output'], np.concatenate(chunks), rate)
    else:
        from index_worker import render_index
        render_index(job, RUNTIME, text_segments)
    print(f'音频已生成，总耗时 {time.monotonic()-start:.1f} 秒', flush=True)


if __name__ == '__main__':
    main()
