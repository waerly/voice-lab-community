// Short auditions and reusable descriptions do not trigger model loading on their own.
const voiceDescriptions = {
  '温暖女旁白': '成年女性，普通话，温暖清亮，中低音区，像给孩子讲科学故事，语气自然，不夸张。',
  '清爽女讲解': '年轻成年女性，普通话，清晰明亮，语气轻快，咬字自然，适合知识讲解，避免播音腔。',
  '沉静女叙述': '成年女性，普通话，中低音，柔和沉静，节奏舒缓，适合夜晚讲故事，不耳语。',
  '活泼女角色': '年轻成年女性，普通话，音调偏高但不尖锐，有好奇心，表达活泼，句子起伏自然。',
  '温和男旁白': '成年男性，普通话，中音区，温和亲切，气息稳定，像朋友一样自然讲述。',
  '沉稳男解说': '成熟男性，普通话，中低音，沉稳清晰，节奏从容，适合技术与知识讲解，避免过度压低声音。',
  '清朗男角色': '年轻成年男性，普通话，清朗明亮，精力充沛，语速适中，表达自然不喊叫。',
  '年长讲述者': '年长男性，普通话，温厚略带沙哑，吐字清晰，节奏舒缓，像长辈讲述往事。'
};
const designBox = $('designSettings');
const templateLabel = document.createElement('label');
templateLabel.htmlFor = 'voiceTemplate'; templateLabel.textContent = '音色描述模板（生成后需试听筛选）';
const template = document.createElement('select'); template.id = 'voiceTemplate';
template.append(new Option('自定义音色描述', ''));
for (const name of Object.keys(voiceDescriptions)) template.append(new Option(name, name));
template.value = Object.keys(voiceDescriptions).find(name => voiceDescriptions[name] === $('designInstruction').value.trim()) || '';
template.onchange = () => { if (voiceDescriptions[template.value]) $('designInstruction').value = voiceDescriptions[template.value]; };
designBox.prepend(templateLabel, template);

const textBox = $('text');
const sentenceRow = document.createElement('div'); sentenceRow.className = 'row';
const sentenceLabel = document.createElement('label'); sentenceLabel.htmlFor = 'sentencePreview'; sentenceLabel.textContent = '按句试听';
const sentences = document.createElement('select'); sentences.id = 'sentencePreview'; sentences.style.maxWidth = '600px';
const preview = document.createElement('button'); preview.textContent = '只生成选中句';
function updateSentences() {
  const previous = sentences.value;
  sentences.replaceChildren();
  const parts = textBox.value.match(/[^。！？\n]+[。！？\n]*|[。！？]+/g) || [];
  for (const part of parts.map(t => t.trim()).filter(Boolean)) sentences.append(new Option(part, part));
  if ([...sentences.options].some(o => o.value === previous)) sentences.value = previous;
  preview.disabled = !sentences.value;
}
textBox.addEventListener('input', updateSentences);
for (const id of ['science', 'story', 'dialogue']) $(id).addEventListener('click', updateSentences);
preview.onclick = () => act(async () => {
  updateSentences();
  if (!sentences.value) throw Error('请先输入文案');
  if (pending || state?.busy) throw Error('请等待当前任务结束');
  preview.disabled = true;
  try { await generate(false, sentences.value); }
  finally { preview.disabled = false; }
});
sentenceRow.append(sentenceLabel, sentences, preview); document.querySelector(".script-actions").prepend(sentenceRow); updateSentences();

// Plain form feedback, independent of the commercial workspace UI.
const updateCounter = () => { $('textCounter').textContent = $('text').value.length + ' / 1500'; };
$('text').addEventListener('input', updateCounter);
for (const id of ['science','story','dialogue']) $(id).addEventListener('click', updateCounter);
$('clearText').onclick = () => { $('text').value=''; $('text').dispatchEvent(new Event('input')); $('text').focus(); };
updateCounter();
