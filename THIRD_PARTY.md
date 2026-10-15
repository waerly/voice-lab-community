# 第三方模型与依赖

本仓库的 MIT 许可证仅覆盖本项目应用代码，不替代以下项目和权重的许可。本仓库不分发上游模型权重或 IndexTTS 上游源码，安装时分别获取并保留其原许可证。

| 项目 | 用途 | 来源及许可核对位置 |
| --- | --- | --- |
| Qwen3-TTS | 语音克隆、内置音色、音色设计 | https://github.com/QwenLM/Qwen3-TTS 及具体下载模型的 model card / LICENSE |
| MLX Audio | Apple Silicon 推理 | https://github.com/Blaizzy/mlx-audio 及安装版本 LICENSE |
| Spark-TTS | 声音创建与克隆 | https://github.com/SparkAudio/Spark-TTS 及具体 MLX 转换权重的说明 |
| IndexTTS 2.5 | 情绪与参考音色克隆 | https://github.com/index-tts/index-tts ，bilibili Model Use License Agreement；需独立遵守其使用与商业条款 |
| Wav2Vec2-BERT / CAMPPlus / BigVGAN | IndexTTS 声学组件 | 下载脚本中的各上游模型仓库及其许可证 |
| PyTorch / MLX / Transformers / SoundFile 等 | 运行依赖 | 各安装版本元数据与许可证 |

免费公开代码不代表所有第三方模型及模型输出都可以无条件商用。商用部署时应按实际使用的模型版本核对许可，不能把本项目 MIT 许可当作模型授权。请只使用有权使用的参考录音，并保留来源与授权记录。
