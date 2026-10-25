const DATA_URL = '../thesis_data.json';
const STORAGE_KEY = 'following-robot-thesis-dashboard-v1';
const DONE = 'เสร็จแล้ว';
const statusClass = { 'เสร็จแล้ว': 'done', 'กำลังทำ': 'progress', 'รอเริ่ม': 'wait', 'ติดเงื่อนไข': 'blocked', 'พักไว้': 'paused' };
const labels = { overview: 'ภาพรวม', quests: 'งานทั้งหมด', evidence: 'แหล่งข้อมูล' };
const state = { seed: null, overrides: {}, view: 'overview', selectedId: null, search: '', type: 'all', status: 'all' };
const $ = id => document.getElementById(id);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const tasks = () => state.seed.tasks.map(t => ({ ...t, ...(state.overrides[t.id] || {}) }));
const mainQuests = () => tasks().filter(t => t.quest_type === 'Main Quest').sort((a,b) => (a.quest_order || a.quest_no) - (b.quest_order || b.quest_no));
const sources = task => String(task.source || '').split('·').map(s => s.trim()).filter(Boolean);
function sourceHref(path) {
  if (!/^(docs|experiments|config|tools|ros2_yolo_ws)\/[\w./-]+$/.test(path) || path.includes('..')) return null;
  return '../../../' + path.split('/').map(encodeURIComponent).join('/');
}
function toast(message) { const el=$('toast'); el.textContent=message; el.classList.add('show'); clearTimeout(toast.timer); toast.timer=setTimeout(()=>el.classList.remove('show'),2600); }
function persist() { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state.overrides)); } catch { toast('ไม่สามารถบันทึกในเบราว์เซอร์นี้ได้'); } }
function mergeTask(id, patch) { state.overrides[id] = { ...(state.overrides[id] || {}), ...patch }; persist(); render(); }
function go(view) {
  state.view=view;
  document.querySelectorAll('.view').forEach(el => el.classList.toggle('active', el.id === `view-${view}`));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.view === view));
  $('crumbCurrent').textContent=labels[view];
  window.scrollTo({top:0,behavior:'smooth'});
}
function openTask(id) {
  const t=tasks().find(task => task.id === Number(id)); if(!t) return;
  state.selectedId=t.id;
  $('drawerContent').innerHTML=`<div class="drawer-kicker">${escapeHtml(t.quest_type)} · #${escapeHtml(t.quest_no || t.id)}</div><h2>${escapeHtml(t.title)}</h2><p class="drawer-summary">${escapeHtml(t.quest_goal || '')}</p><div class="form-group"><label for="editStatus">สถานะ</label><select id="editStatus">${['รอเริ่ม','กำลังทำ','ติดเงื่อนไข','พักไว้','เสร็จแล้ว'].map(x=>`<option ${x===t.status?'selected':''}>${x}</option>`).join('')}</select></div><div class="form-group"><label for="editPriority">ความสำคัญ</label><select id="editPriority">${['สูง','กลาง','ต่ำ'].map(x=>`<option ${x===t.priority?'selected':''}>${x}</option>`).join('')}</select></div><div class="form-group"><label for="editDue">กำหนดส่ง</label><input id="editDue" type="date" value="${escapeHtml(t.due || '')}"></div><div class="form-group"><label for="editNotes">บันทึก</label><textarea id="editNotes">${escapeHtml(t.notes || '')}</textarea></div><div class="drawer-source"><strong>แหล่งข้อมูลต้นทาง</strong><p>${sources(t).map(s=>{const href=sourceHref(s);return href?`<a href="${href}" target="_blank" rel="noopener">${escapeHtml(s)} ↗</a>`:`<span>${escapeHtml(s)}</span>`}).join('')}</p></div><div class="drawer-actions"><button class="button button-light" id="cancelEdit">ยกเลิก</button><button class="button button-dark" id="saveTask">บันทึกการเปลี่ยนแปลง</button></div>`;
  $('drawerBackdrop').hidden=false; $('taskDrawer').classList.add('open'); $('taskDrawer').setAttribute('aria-hidden','false'); document.body.style.overflow='hidden'; $('closeDrawer').focus();
  $('cancelEdit').onclick=closeTask;
  $('saveTask').onclick=()=>{mergeTask(t.id,{status:$('editStatus').value,priority:$('editPriority').value,due:$('editDue').value,notes:$('editNotes').value});closeTask();toast('บันทึกในเบราว์เซอร์แล้ว');};
}
function closeTask(){ $('drawerBackdrop').hidden=true; $('taskDrawer').classList.remove('open'); $('taskDrawer').setAttribute('aria-hidden','true'); document.body.style.overflow=''; state.selectedId=null; }
function renderOverview(){
  const all=tasks(), done=all.filter(t=>t.status===DONE).length, mains=mainQuests(), completedMains=mains.filter(t=>t.status===DONE).length, percent=Math.round(done/all.length*100);
  $('navCount').textContent=all.length; $('heroPercent').innerHTML=`${percent}<span>%</span>`; $('heroCaption').textContent='ความคืบหน้าจากงานทั้งหมด'; $('heroRatio').textContent=`${done} / ${all.length} เสร็จแล้ว`; $('heroTrack').style.width=`${percent}%`; $('heroRing').style.background=`conic-gradient(#e9bc82 ${percent}%,#ffffff22 ${percent}%)`;
  const next=mains.find(t=>t.status!==DONE) || mains[mains.length-1]; $('nextStepLabel').textContent=`MAIN QUEST ${next.quest_order || next.quest_no}`; $('nextTitle').textContent=next.title; $('nextDescription').textContent=next.quest_goal || next.notes || ''; $('nextOpen').onclick=()=>openTask(next.id);
  const metrics=[['งานทั้งหมด',all.length,'◈','ทุกเควสใน Thesis Desk'],['สำเร็จแล้ว',done,'✓','อัปเดตตามสถานะ'],['Main Quest',`${completedMains}/${mains.length}`,'✦','เส้นทางหลัก'],['กำลังทำ',all.filter(t=>t.status==='กำลังทำ').length,'↗','งานที่เดินอยู่']];
  $('metrics').innerHTML=metrics.map(([label,value,icon,desc],i)=>`<article class="metric ${i===2?'accent':''}"><div class="metric-head">${label}<span>${icon}</span></div><strong>${value}</strong><small>${desc}</small></article>`).join('');
  $('roadmap').innerHTML=mains.map((t,i)=>`<button class="roadmap-card ${t.status===DONE?'done':t.id===next.id?'current':''}" data-id="${t.id}"><span class="roadmap-num">CHAPTER ${String(i+1).padStart(2,'0')}</span><strong>${escapeHtml(t.title)}</strong><span class="roadmap-state">${escapeHtml(t.status)} ↗</span></button>`).join('');
  const upcoming=all.filter(t=>t.status!==DONE).sort((a,b)=>(a.quest_type==='Main Quest'?-1:1)-(b.quest_type==='Main Quest'?-1:1)||(a.quest_order||99)-(b.quest_order||99)).slice(0,3);
  $('upNext').innerHTML=upcoming.map((t,i)=>`<button class="next-row" data-id="${t.id}"><span class="round-index">0${i+1}</span><span><strong>${escapeHtml(t.title)}</strong><small>${escapeHtml(t.quest_type)} · ${escapeHtml(t.status)}</small></span><span class="row-arrow">↗</span></button>`).join('');
  $('sourceCount').textContent=new Set(all.flatMap(sources)).size;
}
function renderQuests(){
  const q=state.search.toLocaleLowerCase('th');
  const rows=tasks().filter(t=>(state.type==='all'||t.quest_type===state.type)&&(state.status==='all'||t.status===state.status)&&(!q||`${t.title} ${t.phase} ${t.notes} ${t.source}`.toLocaleLowerCase('th').includes(q)));
  $('resultCount').textContent=`แสดง ${rows.length} จาก ${tasks().length} งาน`;
  $('taskList').innerHTML=rows.length?rows.map(t=>`<button class="task-row" data-id="${t.id}"><span class="task-index">${String(t.id).padStart(2,'0')}</span><span><strong>${escapeHtml(t.title)}</strong><small>${escapeHtml(t.quest_type)} · ${escapeHtml(t.phase || '')}</small></span><span class="pill ${statusClass[t.status]||'wait'}">${escapeHtml(t.status)}</span><span class="row-arrow">↗</span></button>`).join(''):'<div class="evidence-note">ไม่พบงานที่ตรงกับตัวกรอง</div>';
}
function renderEvidence(){
  const map=new Map(); tasks().forEach(t=>sources(t).forEach(path=>{ if(!map.has(path))map.set(path,[]); map.get(path).push(t); }));
  $('evidenceList').innerHTML=[...map].sort((a,b)=>a[0].localeCompare(b[0])).map(([path,related])=>`<article class="source-card"><strong>${sourceHref(path)?`<a href="${sourceHref(path)}" target="_blank" rel="noopener">${escapeHtml(path)} ↗</a>`:escapeHtml(path)}</strong><small>${related.length} งานอ้างอิง</small><div class="source-tasks">${related.slice(0,3).map(t=>escapeHtml(t.title)).join(' · ')}${related.length>3?' …':''}</div></article>`).join('');
}
function render(){renderOverview();renderQuests();renderEvidence();}
function exportData(){const payload={...state.seed,tasks:tasks()};const blob=new Blob([JSON.stringify(payload,null,2)+'\n'],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='thesis_dashboard_export.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('ส่งออกไฟล์ JSON แล้ว');}
function bind(){
  document.querySelectorAll('[data-view]').forEach(el=>el.addEventListener('click',()=>go(el.dataset.view)));
  for(const id of ['openQuests','roadmapAll']) $(id).onclick=()=>go('quests');
  $('overviewEvidence').onclick=()=>go('evidence'); $('exportBtn').onclick=exportData;
  $('resetBtn').onclick=()=>{if(!confirm('คืนค่าสถานะและบันทึกทั้งหมดในเบราว์เซอร์นี้?'))return;state.overrides={};persist();render();toast('คืนค่าข้อมูลตั้งต้นแล้ว');};
  $('searchInput').oninput=e=>{state.search=e.target.value;renderQuests();};
  $('typeFilter').onchange=e=>{state.type=e.target.value;renderQuests();};
  $('statusFilter').onchange=e=>{state.status=e.target.value;renderQuests();};
  document.addEventListener('click',e=>{const el=e.target.closest('[data-id]');if(el)openTask(el.dataset.id);});
  $('closeDrawer').onclick=closeTask;$('drawerBackdrop').onclick=closeTask;
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&state.selectedId!==null)closeTask();});
}
async function init(){
  $('todayLabel').textContent=new Intl.DateTimeFormat('th-TH',{dateStyle:'medium',timeZone:'Asia/Bangkok'}).format(new Date());
  try {
    const response=await fetch(DATA_URL,{cache:'no-store'}); if(!response.ok)throw new Error(`HTTP ${response.status}`);
    const data=await response.json(); if(!Array.isArray(data.tasks))throw new Error('ข้อมูล tasks ไม่ถูกต้อง');
    state.seed=data;
    try {const saved=JSON.parse(localStorage.getItem(STORAGE_KEY)||'{}');if(saved&&typeof saved==='object'&&!Array.isArray(saved))state.overrides=saved;}catch{}
    const statuses=[...new Set(tasks().map(t=>t.status))]; $('statusFilter').innerHTML='<option value="all">ทุกสถานะ</option>'+statuses.map(s=>`<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join('');
    bind();render();
  } catch(err){$('alert').hidden=false;$('alert').textContent=`โหลด thesis_data.json ไม่สำเร็จ (${err.message}) กรุณาเปิดผ่าน local web server ตาม README ของ dashboard`;}
}
init();
