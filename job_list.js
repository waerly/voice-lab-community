/* History owns filtering/pagination; existing generation controls keep their state. */
(() => {
  let page = 1, pages = 1, requestVersion = 0, debounce;
  const selected = new Set();
  function selectionCount(){ $('selectionCount').textContent='已选择 '+selected.size+' 项'; }
  const statuses = {queued:'排队中', running:'生成中', done:'已完成', failed:'失败', cancelled:'已停止'};
  const modes = {clone:'声音克隆', custom:'预设音色', design:'创建音色'};
  const engines = {qwen:'Qwen3-TTS', index:'IndexTTS', spark:'Spark-TTS'};
  const node = (tag, text, className) => {
    const el = document.createElement(tag);
    if (text != null) el.textContent = text;
    if (className) el.className = className;
    return el;
  };
  function button(text, fn, className) {
    const el = node('button', text, className); el.type = 'button';
    el.onclick = () => act(async () => { el.disabled = true; try { await fn(); } finally { el.disabled = false; } });
    return el;
  }
  function roleName(j) {
    if (j.engine === 'qwen' && j.mode === 'design' && j.voice_design_template) return window.generationInfo(j).voice;
    return j.display_role || j.style_name || (j.mode === 'custom' ? (state?.speakers?.find(s => s.id === j.speaker)?.name || j.speaker) : j.mode === 'design' ? '新设计音色' : j.reference?.name) || '未命名声音';
  }
  const seconds = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? Number(value.toFixed(1)) + ' 秒' : '—';
  function updateTiming(row, j) {
    const cell = row.querySelector('.row-elapsed');
    cell.textContent = seconds(j.audio_duration) + ' / ' + seconds(j.elapsed);
    cell.title = '音频时长：' + seconds(j.audio_duration) + '；生成耗时：' + seconds(j.elapsed) + '（含模型加载）';
    cell.setAttribute('aria-label', cell.title);
  }
  function createRow(j) {
    const row = node('article', null, 'job'); row.id = 'job-' + j.id;
    row.dataset.status = j.status;
    const main = node('div', null, 'job-main');
    const tags = node('div', null, 'job-tags');
    tags.append(node('span', engines[j.engine] || j.engine, 'engine-tag ' + j.engine), node('span', statuses[j.status] || j.status, 'status-tag ' + j.status), node('span', modes[j.mode] || j.mode, 'mode-tag'));
    const text = node('p', j.text, 'excerpt'); text.title = j.text;
    const meta = node('p', roleName(j) + ' · ' + new Date(j.created * 1000).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}) + (j.elapsed != null ? ' · 生成 ' + j.elapsed + ' 秒' : ''), 'job-meta');
    meta.title = meta.textContent;
    const heading = node('div', null, 'job-heading');
    heading.append(tags, meta); main.append(heading, text);
    const playback = node('div', null, 'job-playback');
    if (j.status === 'done') {
      const audio = node('audio'); audio.controls = true; audio.preload = 'none'; audio.src = j.audio_url || '/audio/' + j.id + '.wav';
      audio.setAttribute('aria-label', '试听 ' + roleName(j));
      audio.addEventListener('play', () => { for (const other of document.querySelectorAll('audio')) if (other !== audio) other.pause(); });
      playback.append(audio);
    } else playback.append(node('span', j.status === 'failed' ? '本次未生成音频' : statuses[j.status], 'playback-placeholder'));
    const actions = node('div', null, 'job-actions');
    if (j.status === 'done') {
      const link = node('a', '下载', 'download'); link.href = j.audio_url || '/audio/' + j.id + '.wav'; link.download = j.engine + '-' + (j.source_id || j.id).slice(0, 8) + '.wav';
      const saveRole = button('保存角色', async () => {
        const name = prompt('给这个角色命名（样音需为 3～30 秒）'); if (!name) return;
        const ref = await api('/api/roles', {job_id:j.id, name}); await refresh();
        $('reference').value = ref.id; $('reference').onchange(); message('角色已保存，可以在参考声音中选择。');
      }); actions.append(link, saveRole);
    }
    const more = node('details', null, 'job-more'); more.append(node('summary', '详情 / 管理'));
    const detail = node('div', null, 'job-detail');
    detail.append(node('p', j.text, 'full-text'), node('p', [window.generationInfo(j).model, modes[j.mode], j.instruction || '', j.reference?.name || '', j.engine === 'index' ? '情绪：' + j.emotion + ' · 强度：' + j.intensity + ' · 时长：' + j.duration_factor : '', j.engine === 'spark' && j.mode === 'design' ? '音高：' + ({0:'很低',0.5:'偏低',1:'正常',1.5:'偏高',2:'很高'}[j.spark_pitch ?? 1]) + ' · 语速：' + ({0:'很慢',0.5:'偏慢',1:'正常',1.5:'偏快',2:'很快'}[j.spark_speed ?? 1]) + ' · 候选：' + (j.spark_seed ?? 42) : '', '对比组：' + j.group].filter(Boolean).join(' · ')));
    if (j.error) detail.append(node('p', j.error, 'error'));
    const logs = node('details'); logs.append(node('summary', '运行日志'), node('pre', j.log || '任务尚未开始')); detail.append(logs);
    const deletion = node('div', null, 'delete-actions');
    for (const purge of [false, true]) {
      const remove = button(purge ? '删除记录和音频' : '仅删除记录', async () => {
        if (!confirm(purge ? '永久删除这条记录、WAV 音频和日志？已保存角色的独立样音不受影响。' : '删除这条历史记录？音频文件会保留。')) return;
        await api('/api/jobs/delete', {id:j.source_id || j.id, delete_audio:purge});
        await window.refreshJobList();
      }, 'delete');
      remove.disabled = ['queued', 'running'].includes(j.status); deletion.append(remove);
    }
    detail.append(deletion); more.append(detail);
    const selection=node('input');selection.type='checkbox';selection.className='row-select';selection.setAttribute('aria-label','选择作品 '+j.text.slice(0,16));selection.checked=selected.has(j.id);
    selection.onchange=()=>{selection.checked?selected.add(j.id):selected.delete(j.id);row.classList.toggle('selected',selection.checked);selectionCount();if(selection.checked)window.renderWorkDetail?.(j);};
    const number=node('span','', 'row-number');
    const identity=node('div',null,'row-identity');identity.append(node('span',j.engine==='qwen'?'Qwen3 · '+window.generationInfo(j).variant:engines[j.engine]||j.engine,'engine-tag '+j.engine),node('span',roleName(j),'row-role'));identity.title=window.generationInfo(j).model+' · '+roleName(j);
    main.replaceChildren(text);
    const status=node('span',statuses[j.status]||j.status,'status-tag '+j.status);
    const elapsed=node('span','','row-elapsed');
    const created=node('time',new Date(j.created*1000).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}),'row-created');
    more.firstChild.textContent='详情';
    row.append(selection,number,identity,main,status,elapsed,created,playback,actions,more);
    updateTiming(row, j);
    row.classList.toggle('selected',selected.has(j.id));
    return row;
  }
  function render(data) {
    page = data.page; pages = data.pages;
    $('resultCount').textContent = data.total + ' 条';
    $('historySummary').textContent = data.total ? `共 ${data.total} 条 · 当前 ${(page - 1) * data.page_size + 1}–${Math.min(page * data.page_size, data.total)} 条` : '共 0 条';
    $('historyPage').textContent = page + ' / ' + pages;
    $('historyPrev').disabled = page === 1; $('historyNext').disabled = page === pages;
    const list = $('jobs'), ids = new Set(data.jobs.map(j => 'job-' + j.id));
    for (const row of [...list.children]) if (!ids.has(row.id)) row.remove();
    if (!data.jobs.length) { list.append(node('div', '没有找到匹配的试听记录，试试其他关键词或重置筛选。', 'empty-state')); return; }
    const pageNumbers=$('pageNumbers');pageNumbers.replaceChildren();
    const visiblePages=[...new Set([1,...Array.from({length:5},(_,i)=>page-2+i).filter(n=>n>=1&&n<=pages),pages])].sort((a,b)=>a-b);
    let last=0;for(const n of visiblePages){if(last&&n-last>1)pageNumbers.append(node('span','…'));const b=button(String(n),()=>{page=n;window.refreshJobList();},n===page?'current':'');b.setAttribute('aria-label','第 '+n+' 页');if(n===page)b.setAttribute('aria-current','page');pageNumbers.append(b);last=n;}
    data.jobs.forEach((j, index) => {
      let row = document.getElementById('job-' + j.id);
      if (!row || row.dataset.status !== j.status) {
        const next = createRow(j); if (row) row.replaceWith(next); row = next;
      } else row.querySelector('pre').textContent = j.log || '任务尚未开始';
      updateTiming(row, j);
      // Do not detach unchanged rows: polling must not interrupt audio playback.
      row.querySelector('.row-number').textContent=(page-1)*data.page_size+index+1;
      if (list.children[index] !== row) list.insertBefore(row, list.children[index] || null);
    });
    selectionCount();
  }
  window.refreshJobList = async () => {
    const version = ++requestVersion;
    const query = new URLSearchParams({page, page_size:$('historySize').value, q:$('historyQuery').value, engine:$('historyEngine').value, status:$('historyStatus').value, mode:$('historyMode').value, start_date:$('historyStart').value, end_date:$('historyEnd').value});
    if ($('historyStart').value && $('historyEnd').value && $('historyStart').value > $('historyEnd').value) {
      $('historyFeedback').textContent = '开始日期不能晚于结束日期';
      $('historyFeedback').className = 'error'; return;
    }
    try {
      const data = await api('/api/jobs?' + query);
      if (version !== requestVersion) return;
      $('historyFeedback').textContent = ''; render(data);
    } catch (e) {
      if (version === requestVersion) { $('historyFeedback').textContent = '记录加载失败：' + e.message; $('historyFeedback').className = 'error'; }
    }
  };
  function changed() { page = 1; window.refreshJobList(); }
  $('historyFilters').onsubmit = e => { e.preventDefault(); clearTimeout(debounce); changed(); };
  $('historyFilters').onreset = () => { clearTimeout(debounce); setTimeout(changed, 0); };
  for (const id of ['historyEngine', 'historyStatus', 'historyMode', 'historySize', 'historyStart', 'historyEnd']) $(id).onchange = changed;
  $('historyQuery').oninput = () => { clearTimeout(debounce); ++requestVersion; debounce = setTimeout(changed, 250); };
  $('historyPrev').onclick = () => { if (page > 1) { page--; window.refreshJobList(); } };
  $('historyNext').onclick = () => { if (page < pages) { page++; window.refreshJobList(); } };
  window.refreshJobList();
})();
