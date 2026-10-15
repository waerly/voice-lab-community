**简体中文** | [English](README.en.md)

# 小思音台 · 本地 AI 配音与声音克隆工具

**在 Apple Silicon Mac 上，把文字变成配音，用参考录音克隆音色，在同一个网页里体验 Qwen3-TTS、IndexTTS 和 Spark-TTS。**

小思音台免费开源版把三套语音模型整合进一个本地网页，提供文字输入、参考录音、音色选择、生成试听和音频下载。适合为短视频、故事朗读、知识讲解制作配音，也适合对比不同模型的声音效果。

完成依赖安装和模型下载后，可以直接在浏览器中操作；日常生成无需逐条编写推理命令，也无需配置云端语音 API Key。模型在本机运行，录音、参考角色和生成音频保存在本地项目目录。当前面向 **Apple Silicon Mac**，采用朴素表单和结果列表界面。

## 你可以用它做什么

- **给文稿配音**：输入文字，选择内置音色或参考声音，生成后试听、下载音频，用于后续视频剪辑或音频制作。
- **用自己的录音克隆音色**：上传或直接录制有权使用的参考音频，让模型按参考音色朗读新文本。
- **用文字描述创建声音**：通过 Qwen 或 Spark 的声音创建能力尝试不同音色；Spark 还提供音高、语速选择和候选切换。
- **为不同内容复用角色**：把合成声音保存为参考角色，后续配音时重复选择，减少反复上传素材的操作。
- **比较模型效果**：在同一网页切换三套模型，也可以让同一参考声音依次经过 Qwen Base 与 IndexTTS，试听差异。
- **管理生成记录**：搜索、筛选、分页查看历史音频，试听、下载或删除，并查看音频时长和生成耗时。

## 三套模型，各有所用

| 模型 | 已集成能力 | 可以尝试的用途 |
| --- | --- | --- |
| Qwen3-TTS | 参考声音克隆、9 个内置音色、文字描述创建声音 | 从内置音色快速开始，或尝试自定义声音 |
| IndexTTS 2.5 | 参考声音克隆、情绪和时长倍率、稳定模式 | 调整短段旁白的情绪与节奏 |
| Spark-TTS | 声音创建、音高/语速选择、候选切换、参考声音克隆 | 探索不同声音设定，再选取合适的候选 |

实际效果和速度取决于模型、参考录音、文本和设备配置。IndexTTS 保留内存检查、MPS 分配限制和短文本分段保护，具体限制见下文。

## 实际界面

以下截图来自免费开源版本地页面，展示模型设置与试听文案区域。界面目前为中文；截图不包含私人录音或生成记录，也不代表本次已执行模型推理。

### Qwen：预设音色与讲述风格

![Qwen 实际界面：内置音色、讲述风格与试听文案](docs/images/qwen.png)

### IndexTTS：情绪、节奏与内存保护

![IndexTTS 实际界面：情绪强度、时长倍率与稳定模式提示](docs/images/index.png)

### Spark：创建声音与音高、语速设置

![Spark 实际界面：声音创建与可选控制参数](docs/images/spark.png)

## 免费开源与许可

本项目应用代码采用 **MIT 许可证**，可免费使用、修改、分发和商用。模型、模型输出及第三方依赖遵循各自许可，详见 [THIRD_PARTY.md](THIRD_PARTY.md)。MIT 许可不替代模型授权。

这是从现有项目分离整理的基础版，维护范围为 Qwen、IndexTTS、Spark 三套模型的本地配音流程。

## 快速开始

仅网页服务需要 Python 3.11 及以上；模型环境使用 Python 3.11。音频转换需要系统 `ffmpeg`。当前只适配 Apple Silicon macOS，未验证 Windows/Linux。

### 已有本机环境

本机已配置一个被 Git 忽略的 `local_runtime.json`，仅指向现有依赖和模型目录。应用源码独立，录音、角色、作品、日志写入本仓库的 `data/`，不访问另一版本的作品数据。不要在共享运行环境上升级依赖；需要独立升级时使用下面的独立安装流程。

```sh
zsh start.command
# 浏览器访问 http://127.0.0.1:8776/qwen
zsh stop.command
```

默认端口 **8776**，与原项目的 8766 分开。`VOICE_LAB_PORT` 可覆盖端口；`VOICE_LAB_RUNTIME` 可覆盖依赖与权重位置。网页可同时打开，考虑到统一内存限制，不建议两个版本同时跑重模型。

### 从 Git 仓库安装

仓库不带模型、虚拟环境、用户音频或参考角色。请准备 Python 3.11、Git 和 ffmpeg。

```sh
git clone https://github.com/waerly/voice-lab-community.git
cd voice-lab-community
```

```sh
# 1. 安装 Qwen / Spark 的 MLX 依赖
python3 scripts/setup_runtime.py mlx
# 2. 按需下载模型（体积较大）
runtime/qwen-venv/bin/python download_models.py qwen
runtime/qwen-venv/bin/python download_models.py design
runtime/qwen-venv/bin/python download_models.py spark
# 3. 可选：准备 IndexTTS 上游源码、依赖和模型
python3 scripts/setup_runtime.py index
runtime/qwen-venv/bin/python download_models.py index
# 4. 启动
zsh start.command
```

IndexTTS 上游需提供 `indextts.infer_v2_5.IndexTTS2` 和 `use_qwen_emo=False` 接口。安装脚本使用上游当前默认分支，尚未固定源码版本；首次安装前请核对上游版本兼容性。Python 包版本来自当前可用的本机环境。**本次分离未执行全新机器安装或重新下载模型**，上述独立安装路径仍需在干净环境验证。已有环境下已验证服务与三模型页面，未重新跑模型推理。

如需“轻柔讲述、活泼科普、沉稳解说”内置样音，可在 Qwen 模型就绪、网页服务运行后执行 `python3 prepare_builtin_styles.py`。这会真实生成合成参考声音，并非仓库预置的真人录音。

## 内存和生成限制

IndexTTS 每次最多 200 字，约 40 字分段，参考音频只取前 8 秒，单候选搜索。启动前与生成中会检查内存，并限制 MPS 分配；触线时拒绝或停止任务。其他模型一般最多 1500 字，文字创建角色先用 120 字以内样音。每任务最多 8 分钟。

保护不能保证消除系统或 GPU 驱动故障。32 GB Mac 也可能因其他应用占用而拒绝 IndexTTS；建议从 20～40 字开始。不同模型环境、量化精度和加载开销不同，耗时只反映当前本机配置。

## 开发与验证

```sh
python3 -m unittest discover -s . -p 'test_*.py' -v
node test_generation_context.cjs
# WAV 流程测试使用已有 soundfile，但不会加载真实模型
runtime/qwen-venv/bin/python -m unittest discover -s . -p 'test_index_worker.py' -v
```

`server.py` 为本地 HTTP/API；`worker.py` 为独立模型进程；`index_resources.py` 和 `index_worker.py` 为 IndexTTS 保护与分段；`classic.css` 为基础界面；`job_history.py` / `job_list.js` 为历史记录。

## 发布范围

提交 Git 时仅提交应用源码、文档和测试。`.gitignore` 排除模型、虚拟环境、录音、生成作品、私有运行路径、日志及临时文件。用户数据保存在本地，不随源码发布。
