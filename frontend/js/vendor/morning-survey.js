const MORNING_SURVEY_API = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');
let surveyCatalog=[]; let currentSurvey=null;

document.addEventListener('DOMContentLoaded', initMorningSurvey);

async function initMorningSurvey(){
  try{
    const auth=await fetch(`${MORNING_SURVEY_API}/auth/me`,{credentials:'include'}), ad=await auth.json();
    if(!auth.ok||!ad.authenticated||ad.user.role!=='vendor'){window.location.href='login.html';return;}
    await loadSurvey();
  }catch(e){showSurveyMessage('Unable to connect to the server.',false);}
}

async function loadSurvey(){
  const res=await fetch(`${MORNING_SURVEY_API}/vendor/daily-survey/today`,{credentials:'include'}), data=await res.json();
  if(!res.ok||!data.success){showSurveyMessage(data.message||'Unable to load today\'s survey.',false);return;}
  surveyCatalog=data.menu_catalog||[]; currentSurvey=data.survey||null;
  document.getElementById('survey-shop-name').textContent=(data.shop&&data.shop.name)||'Assigned Shop';
  document.getElementById('survey-date').textContent=data.date||'Today';
  renderSurveyWindows(data.meal_windows||{});
  const serving=document.getElementById('serving-today'); if(serving)serving.checked=currentSurvey?currentSurvey.is_serving_today!==false:true;
  ['breakfast','lunch','dinner'].forEach(p=>renderMeal(p,(data.selected&&data.selected[p])||[]));
  renderResult(data);
  // Vote results are independent of the published survey details; load them in parallel
  // so the main survey UI becomes interactive without waiting for the second request.
  void loadVoteResults();
}

function renderSurveyWindows(windows){
  const el=document.getElementById('food-survey-windows');
  if(!el)return;
  const icons={breakfast:'🍳',lunch:'🍛',dinner:'🌙'};
  const periods=['breakfast','lunch','dinner'];
  el.innerHTML=periods.map(function(p){
    const w=windows[p]||{};
    const label=w.status==='open'?'OPEN NOW':w.status==='upcoming'?'UPCOMING':'CLOSED';
    return '<div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">'+
      '<div class="flex items-center justify-between gap-2 mb-3"><span class="font-black text-slate-800">'+icons[p]+' '+p.charAt(0).toUpperCase()+p.slice(1)+'</span>'+
      '<span class="survey-window-status px-2 py-1 rounded-full bg-blue-50 text-blue-700 text-[9px] font-black uppercase">'+label+'</span></div>'+
      '<div class="grid grid-cols-2 gap-2">'+
      '<label class="text-[10px] font-bold text-slate-500">Start<input type="time" id="survey-'+p+'-start" value="'+String(w.start_time||'').slice(0,5)+'" class="mt-1 w-full px-2 py-2 rounded-lg border border-slate-200 bg-white text-xs font-bold"></label>'+
      '<label class="text-[10px] font-bold text-slate-500">End<input type="time" id="survey-'+p+'-end" value="'+String(w.end_time||'').slice(0,5)+'" class="mt-1 w-full px-2 py-2 rounded-lg border border-slate-200 bg-white text-xs font-bold"></label>'+
      '</div><p class="text-[10px] text-slate-400 mt-2">Students can submit only inside this window.</p></div>';
  }).join('');
}
function getSurveyTimeSettings(){
  const windows={};
  ['breakfast','lunch','dinner'].forEach(function(p){
    windows[p]={
      start_time:(document.getElementById('survey-'+p+'-start')||{}).value||'',
      end_time:(document.getElementById('survey-'+p+'-end')||{}).value||''
    };
  });
  return windows;
}
function formatSurveyTime(value){
  if(!value)return '—';
  const a=String(value).split(':').map(Number),d=new Date();
  d.setHours(a[0],a[1],0,0);
  return d.toLocaleTimeString([], {hour:'numeric',minute:'2-digit'});
}

function renderMeal(period,selectedRows){
  const el=document.getElementById(period+'-items'); const selected=new Map(selectedRows.map(x=>[String(x.menu_item_id),x]));
  const items=surveyCatalog.filter(i=>String(i.meal_period||'lunch').toLowerCase()===period);
  if(!items.length){el.innerHTML='<p class="text-[11px] text-slate-400 text-center p-4">No permanent dishes assigned to this meal period. Add or move dishes in Update Menu.</p>';return;}
  el.innerHTML=items.map(item=>{const row=selected.get(String(item.id));const qty=row?row.quantity:item.stock_quantity;return `<label class="block bg-white rounded-2xl border border-slate-100 p-3 cursor-pointer hover:border-amber-300"><div class="flex items-center gap-2"><input type="checkbox" class="survey-check accent-amber-600 w-4 h-4" data-period="${period}" data-id="${item.id}" ${row?'checked':''}><span class="text-xs font-bold truncate flex-1">${escapeHtml(item.name)}</span><span class="text-[10px] font-black text-slate-500">₹${Number(item.price).toFixed(2)}</span></div><div class="flex items-center justify-between mt-2 ml-6"><span class="text-[10px] text-slate-400">${escapeHtml(item.category)}</span><input type="number" min="0" max="100000" data-qty-period="${period}" data-qty-id="${item.id}" value="${Math.max(0,qty)}" class="w-20 px-2 py-1 rounded-lg border border-slate-200 text-[10px] font-bold text-right"></div></label>`}).join('');
}

function renderResult(data){
  const s=data.survey||{}, selected=data.selected||{};
  const status=document.getElementById('survey-status'); status.textContent=s.submitted?'Submitted Today':'Not Submitted'; status.className='px-3 py-1.5 rounded-full text-[10px] font-black uppercase '+(s.submitted?'bg-emerald-100 text-emerald-700':'bg-slate-100 text-slate-600');
  document.getElementById('result-summary').innerHTML=['breakfast','lunch','dinner'].map(p=>`<div class="rounded-2xl bg-slate-50 border border-slate-100 p-4"><p class="text-[10px] font-black uppercase text-slate-400">${p}</p><p class="text-2xl font-black text-slate-800 mt-1">${(selected[p]||[]).length}</p><p class="text-[10px] text-slate-400">dishes published</p></div>`).join('');
}

async function loadVoteResults(){
  const wrap=document.getElementById('vote-results'), totalEl=document.getElementById('vote-total');
  if(!wrap) return;
  try{
    const res=await fetch(MORNING_SURVEY_API+'/vendor/daily-survey/vote-results',{credentials:'include'});
    const data=await res.json();
    if(!res.ok||!data.success) throw new Error(data.message||'Unable to load student votes.');
    const total=Number(data.total_votes)||0, options=data.options||[];
    if(totalEl) totalEl.textContent=total+' vote'+(total===1?'':'s');
    if(!options.length){
      wrap.innerHTML='<p class="text-xs text-slate-400 py-4">No food choices or votes available for today.</p>';
      return;
    }
    wrap.innerHTML=options.map(o=>'<div class="rounded-2xl border border-slate-100 bg-slate-50 p-4"><div class="flex items-center justify-between gap-3"><div><p class="text-xs font-black text-slate-800">'+escapeHtml(o.item_name)+'</p><p class="text-[10px] text-slate-400 uppercase">'+escapeHtml(o.meal_period||'food')+'</p></div><span class="text-sm font-black text-blue-700">'+(Number(o.vote_count)||0)+' vote'+(Number(o.vote_count)===1?'':'s')+'</span></div><div class="h-2 rounded-full bg-slate-200 overflow-hidden mt-3"><div class="h-full rounded-full bg-blue-500" style="width:'+Math.min(100,Number(o.percentage)||0)+'%"></div></div><p class="text-[10px] text-slate-400 mt-1 text-right">'+(Number(o.percentage)||0)+'% of votes</p></div>').join('');
  }catch(e){
    wrap.innerHTML='<p class="text-xs text-rose-600">'+escapeHtml(e.message||'Unable to load student votes.')+'</p>';
  }
}

async function saveSurvey(){
  const btn=document.getElementById('publish-btn'), serving=document.getElementById('serving-today');
  const meals={breakfast:[],lunch:[],dinner:[]};
  document.querySelectorAll('.survey-check:checked').forEach(ch=>{const p=ch.dataset.period,id=Number(ch.dataset.id),q=document.querySelector(`[data-qty-period="${p}"][data-qty-id="${id}"]`);meals[p].push({menu_item_id:id,quantity:q?Math.max(0,parseInt(q.value||'0',10)):0});});
  btn.disabled=true;btn.innerHTML='<i class="fa-solid fa-spinner fa-spin mr-1.5"></i>Publishing...';
  try{
    const res=await fetch(`${MORNING_SURVEY_API}/vendor/daily-survey`,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({is_serving_today:serving.checked,meal_windows:getSurveyTimeSettings(),meals})}),data=await res.json();
    if(!res.ok||!data.success){showSurveyMessage(data.message||'Unable to publish menu.',false);return;}
    showSurveyMessage('Today\'s Breakfast, Lunch and Dinner menu has been published.',true); await loadSurvey();
  }catch(e){showSurveyMessage('Connection error while publishing today\'s menu.',false);}
  finally{btn.disabled=false;btn.innerHTML='<i class="fa-solid fa-cloud-arrow-up mr-1.5"></i>Publish Today\'s Menu';}
}
function showSurveyMessage(m,ok){const el=document.getElementById('survey-message');el.className='mb-5 p-3 rounded-xl text-xs font-bold '+(ok?'bg-emerald-50 border border-emerald-200 text-emerald-700':'bg-rose-50 border border-rose-200 text-rose-700');el.textContent=m;el.classList.remove('hidden');}
function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}