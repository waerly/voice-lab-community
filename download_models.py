"""Download model files to the isolated lab; run with the Qwen environment."""
import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / 'runtime'
os.environ['HF_HOME'] = str(RUNTIME / 'hf-cache')
os.environ['HF_HUB_DISABLE_XET'] = '1'
os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '60'


def main():
    from huggingface_hub import snapshot_download, hf_hub_download
    parser = argparse.ArgumentParser()
    parser.add_argument('engine', choices=['qwen','index','design','spark'])
    args = parser.parse_args()
    models = RUNTIME / 'models'
    models.mkdir(parents=True, exist_ok=True)
    if args.engine == 'qwen':
        for suffix, local in [('Base','qwen-base'),('CustomVoice','qwen-custom')]:
            repo = f'mlx-community/Qwen3-TTS-12Hz-1.7B-{suffix}-8bit'
            print('Downloading',repo,flush=True)
            snapshot_download(repo,local_dir=models/local,max_workers=4)
    elif args.engine in ('design', 'spark'):
        repo, local = ('mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit', 'qwen-design') if args.engine == 'design' else ('mlx-community/Spark-TTS-0.5B-bf16', 'spark')
        print('Downloading', repo, flush=True)
        snapshot_download(repo, local_dir=models/local, max_workers=2)
    else:
        checkpoint = RUNTIME / 'index-tts/checkpoints'
        print('Downloading IndexTTS-2.5',flush=True)
        snapshot_download('IndexTeam/IndexTTS-2.5',local_dir=checkpoint,
                          ignore_patterns=['qwen0.6bemo4-merge/*'],max_workers=4)
        cache = checkpoint/'hf_cache'
        print('Downloading w2v-bert-2.0',flush=True)
        snapshot_download('facebook/w2v-bert-2.0',local_dir=cache/'w2v-bert-2.0',
                          allow_patterns=['*.json','*.safetensors'],max_workers=4)
        print('Downloading CAMPPlus and BigVGAN',flush=True)
        hf_hub_download('funasr/campplus','campplus_cn_common.bin',local_dir=cache)
        snapshot_download('nvidia/bigvgan_v2_22khz_80band_256x',local_dir=cache/'bigvgan',
                          allow_patterns=['config.json','bigvgan_generator.pt'],max_workers=2)
    (models/(args.engine+'.ready')).write_text('download complete\n')
    print(args.engine,'MODELS READY',flush=True)


if __name__=='__main__':
    main()
