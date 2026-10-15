/* Derive labels from the mode actually submitted to the synthesis worker. */
(() => {
  function info(job, speakers = []) {
    const e = job.engine, mode = e === 'index' ? 'clone' : job.mode;
    const variant = e === 'qwen' ? (job.model_variant || {clone:'Base',custom:'CustomVoice',design:'VoiceDesign'}[mode] || '') : '';
    const model = e === 'qwen' ? `Qwen3-TTS 1.7B ${variant} · MLX 8-bit` : e === 'spark' ? 'Spark-TTS 0.5B · MLX' : e === 'index' ? 'IndexTTS 2.5 · MPS' : job.model;
    const modeName = ({clone:'声音克隆',custom:'预设音色',design:'文字设计'})[mode] || mode;
    let voice;
    if (mode === 'clone') voice = job.reference?.name || '请先选择参考声音';
    else if (e === 'spark') voice = `${job.gender === 'male' ? '男声' : '女声'} · 候选 ${job.spark_seed ?? 42}`;
    else if (mode === 'design') voice = job.voice_design_template ? `${job.voice_design_template}${job.voice_design_modified ? '（描述已调整）' : ''}` : '自定义音色描述';
    else voice = speakers.find(s => s.id === job.speaker)?.name || job.display_role || job.speaker || '请选择预设音色';
    return {model, variant, mode: e === 'spark' && mode === 'design' ? '创建声音' : modeName, voice, usesReference: mode === 'clone', description: job.instruction || ''};
  }
  globalThis.generationInfo = info;
})();
