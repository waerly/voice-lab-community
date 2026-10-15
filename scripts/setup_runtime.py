"""Prepare isolated dependencies; does not download weights or run inference."""
import argparse
from pathlib import Path
import platform
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('engine', choices=['mlx', 'index'])
    args = parser.parse_args()
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise SystemExit('当前只适配 Apple Silicon Mac。')
    if (ROOT/'local_runtime.json').exists():
        raise SystemExit('当前配置为复用本机依赖。请先移开 local_runtime.json，避免修改共享环境。')
    python = shutil.which('python3.11')
    if not python:
        raise SystemExit('请先安装 Python 3.11，并确认 python3.11 在 PATH 中。')
    runtime = ROOT/'runtime'; runtime.mkdir(exist_ok=True)
    env = runtime/'qwen-venv' if args.engine == 'mlx' else runtime/'index-tts/.venv'
    if args.engine == 'index' and not (runtime/'index-tts').exists():
        subprocess.run(['git','clone','--depth','1','https://github.com/index-tts/index-tts.git',
                        str(runtime/'index-tts')], check=True, timeout=300)
    subprocess.run([python,'-m','venv',str(env)],check=True,timeout=60)
    requirements = ROOT/('requirements-mlx.txt' if args.engine == 'mlx' else 'requirements-index.txt')
    subprocess.run([str(env/'bin/python'),'-m','pip','install','-r',str(requirements)],
                   check=True,timeout=600)
    print('依赖已准备。请按 README 单独下载模型；此步骤不会启动模型。')


if __name__ == '__main__':
    main()
