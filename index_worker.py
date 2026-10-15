"""Bounded MPS synthesis for the local IndexTTS worker."""
import gc
from pathlib import Path
import subprocess
import tempfile

from index_resources import (GIB, MAX_TEXT, REFERENCE_SECONDS, SEGMENT_CHARS,
                             ensure_index_ready, limits)


def render_index(job, runtime, split_text):
    snapshot = ensure_index_ready(job['text'])
    import torch
    import soundfile as sf
    from indextts.infer_v2_5 import IndexTTS2

    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.manual_seed(42)
    budget = limits(snapshot['total'])['mps']
    # Relative to Metal's recommended working set, not physical RAM.
    recommended = torch.mps.recommended_max_memory()
    torch.mps.set_per_process_memory_fraction(float(min(1.0, budget / recommended)))
    print(f'IndexTTS 稳定模式：MPS 上限 {budget/GIB:.1f} GiB，单候选，'
          f'{SEGMENT_CHARS} 字分段，每次最多 {MAX_TEXT} 字。', flush=True)
    checkpoint = runtime / 'index-tts' / 'checkpoints'
    model = IndexTTS2(cfg_path=str(checkpoint/'config.yaml'), model_dir=str(checkpoint),
                      device='mps', use_bf16=False, use_cuda_kernel=False,
                      use_deepspeed=False, use_qwen_emo=False)
    print('模型已加载，开始分段生成普通话…', flush=True)
    vector = None
    if job['emotion'] != 'reference':
        vector = [0.0] * 8
        vector[{'happy': 0, 'sad': 2, 'surprised': 6, 'calm': 7}[job['emotion']]] = job['intensity']

    output = Path(job['output'])
    partial = output.with_suffix('.partial.wav')
    try:
        with tempfile.TemporaryDirectory(prefix='index-segments-') as directory:
            directory = Path(directory)
            reference = directory/'reference.wav'
            subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i',
                            job['reference']['path'], '-t', str(REFERENCE_SECONDS),
                            '-ar', '24000', '-ac', '1', str(reference)], check=True, timeout=20)
            segments = split_text(job['text'], limit=SEGMENT_CHARS)
            with sf.SoundFile(str(partial), 'w', samplerate=22050, channels=1, subtype='PCM_16') as target:
                for i, text in enumerate(segments):
                    print(f'IndexTTS 分段 {i+1}/{len(segments)}', flush=True)
                    path = directory/'segment.wav'
                    model.infer(spk_audio_prompt=str(reference), text=text, lang='ZH',
                                output_path=str(path), emo_vector=vector, use_random=False,
                                duration_factor=job['duration_factor'], verbose=False,
                                num_beams=1, max_text_tokens_per_segment=64, max_mel_tokens=768)
                    # Stream each completed segment to disk, never accumulate MPS tensors.
                    with sf.SoundFile(str(path)) as source:
                        if source.samplerate != target.samplerate or source.channels != 1:
                            raise RuntimeError('IndexTTS 返回的音频格式异常')
                        if i:
                            target.write([0.0] * 4410)
                        for block in source.blocks(blocksize=65536):
                            target.write(block)
                    path.unlink()
                    gc.collect()
                    torch.mps.empty_cache()
            partial.replace(output)
    finally:
        partial.unlink(missing_ok=True)
