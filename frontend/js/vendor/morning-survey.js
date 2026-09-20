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
  const serving=document.getElementById('serving-today'); if(serving)serving.checked=currentSurvey?currentSurvey.is_serving_today!==false:true;
  ['breakfast','lunch','dinner'].forEach(p=>renderMeal(p,(data.selected&&data.selected[p])||[]));
  renderResult(data);
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

async function saveSurvey(){
  const btn=document.getElementById('publish-btn'), serving=document.getElementById('serving-today');
  const meals={breakfast:[],lunch:[],dinner:[]};
  document.querySelectorAll('.survey-check:checked').forEach(ch=>{const p=ch.dataset.period,id=Number(ch.dataset.id),q=document.querySelector(`[data-qty-period="${p}"][data-qty-id="${id}"]`);meals[p].push({menu_item_id:id,quantity:q?Math.max(0,parseInt(q.value||'0',10)):0});});
  btn.disabled=true;btn.innerHTML='<i class="fa-solid fa-spinner fa-spin mr-1.5"></i>Publishing...';
  try{
    const res=await fetch(`${MORNING_SURVEY_API}/vendor/daily-survey`,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({is_serving_today:serving.checked,meals})}),data=await res.json();
    if(!res.ok||!data.success){showSurveyMessage(data.message||'Unable to publish menu.',false);return;}
    showSurveyMessage('Today\'s Breakfast, Lunch and Dinner menu has been published.',true); await loadSurvey();
  }catch(e){showSurveyMessage('Connection error while publishing today\'s menu.',false);}
  finally{btn.disabled=false;btn.innerHTML='<i class="fa-solid fa-cloud-arrow-up mr-1.5"></i>Publish Today\'s Menu';}
}
function showSurveyMessage(m,ok){const el=document.getElementById('survey-message');el.className='mb-5 p-3 rounded-xl text-xs font-bold '+(ok?'bg-emerald-50 border border-emerald-200 text-emerald-700':'bg-rose-50 border border-rose-200 text-rose-700');el.textContent=m;el.classList.remove('hidden');}
function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}