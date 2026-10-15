// Spark controls are discrete model conditions, not playback speed multipliers.
let sparkSeed = 42;
const sparkPanel = document.createElement('div');
sparkPanel.id = 'sparkCreationControls';
for (const [id, title, names] of [
  ['sparkPitch', '音高', ['很低', '偏低', '正常', '偏高', '很高']],
  ['sparkSpeed', '语速', ['很慢', '偏慢', '正常', '偏快', '很快']]
]) {
  const label = document.createElement('label'); label.htmlFor = id; label.textContent = title;
  const select = document.createElement('select'); select.id = id;
  names.forEach((name, index) => select.append(new Option(name, String(index / 2))));
  select.value = '1'; sparkPanel.append(label, select);
}
const nextVoice = document.createElement('button');
nextVoice.id = 'sparkNewVoice'; nextVoice.textContent = '换一个声音并试听';
nextVoice.className = 'primary';
const row = document.createElement('div'); row.className = 'row'; row.append(nextVoice);
const candidate = document.createElement('p'); candidate.id = 'sparkCandidate'; candidate.className = 'hint';
const tip = document.createElement('p'); tip.className = 'hint';
tip.textContent = '普通生成沿用当前候选；换一个声音会重新采样并生成，变化可能包含音色和语气。固定角色请保存样音，再使用克隆模式。';
row.append(candidate); sparkPanel.append(row, tip); $('gender').after(sparkPanel);
window.updateSparkControls = () => {
  const clone = $('sparkMode').value === 'clone';
  sparkPanel.classList.toggle('hidden', clone);
  $('gender').disabled = clone;
  nextVoice.disabled = clone || pending || !!state?.busy || !state?.engines.spark?.installed;
  candidate.textContent = '当前声音候选：' + sparkSeed;
};
function sparkRequest(change) {
  if (engine !== 'spark') return {};
  return {spark_pitch:Number($('sparkPitch').value), spark_speed:Number($('sparkSpeed').value),
    spark_seed:sparkSeed, spark_new_voice:change};
}
function rememberSparkCandidate(result) {
  const job = result.jobs.find(j => j.engine === 'spark');
  if (job) sparkSeed = job.spark_seed ?? 42;
  updateSparkControls();
}
nextVoice.onclick = () => act(async () => {
  if (pending || state?.busy) throw Error('请等待当前任务结束');
  nextVoice.disabled = true;
  try { await generate(false, undefined, true); }
  finally { updateSparkControls(); }
});
$('sparkMode').addEventListener('change', updateSparkControls);
updateSparkControls();
