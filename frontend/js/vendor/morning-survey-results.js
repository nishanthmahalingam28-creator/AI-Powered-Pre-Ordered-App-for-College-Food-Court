const SURVEY_RESULTS_API=window.FOOD_COURT_API_BASE||(typeof window.getApiUrl==='function'?window.getApiUrl(''):'/api');
document.addEventListener('DOMContentLoaded',loadResults);
async function loadResults(){
 try{
  const auth=await fetch(`${SURVEY_RESULTS_API}/auth/me`,{credentials:'include'}),ad=await auth.json();
  if(!auth.ok||!ad.authenticated||!['vendor','admin'].includes(ad.user.role)){location.href='login.html';return;}
  const res=await fetch(`${SURVEY_RESULTS_API}/vendor/daily-survey/user-results`,{credentials:'include'}),data=await res.json();
  if(!res.ok||!data.success)throw new Error(data.message||'Unable to load results');
  document.getElementById('results-date').textContent=`Customer responses for ${data.date}`;
  const s=data.summary||{};
  document.getElementById('summary').innerHTML=[
   ['Total Responses',s.total_responses,'fa-users','bg-blue-50 text-blue-700'],
   ['Planning To Eat',s.planning_to_eat,'fa-utensils','bg-emerald-50 text-emerald-700'],
   ['Not Eating Today',s.not_planning_to_eat,'fa-ban','bg-rose-50 text-rose-700']
  ].map(x=>`<div class="bg-white rounded-3xl border border-slate-200 p-5 shadow-sm"><div class="w-10 h-10 rounded-xl ${x[3]} flex items-center justify-center mb-3"><i class="fa-solid ${x[2]}"></i></div><p class="text-[10px] font-black uppercase text-slate-400">${x[0]}</p><p class="text-3xl font-black text-slate-900 mt-1">${x[1]||0}</p></div>`).join('');
  renderList('meal',data.meal_periods||[],'meal_type');
  renderList('preferences',data.food_preferences||[],'meal_preference');
  renderList('diet',data.dietary_preferences||[],'dietary_preference');
  renderList('hunger',data.hunger_levels||[],'hunger_level');
 }catch(e){const m=document.getElementById('message');m.className='mb-5 p-3 rounded-xl text-xs font-bold bg-rose-50 border border-rose-200 text-rose-700';m.textContent=e.message||'Unable to load results';m.classList.remove('hidden');}
}
function renderList(id,rows,key){
 const el=document.getElementById(id); if(!rows.length){el.innerHTML='<p class="text-xs text-slate-400 py-5 text-center">No responses yet.</p>';return;}
 const max=Math.max(...rows.map(r=>Number(r.response_count)||0),1);
 el.innerHTML=rows.map(r=>{const n=Number(r.response_count)||0;const label=String(r[key]||'Not specified').replace(/_/g,' ');return `<div class="mb-4"><div class="flex justify-between text-xs font-bold mb-1"><span class="capitalize truncate pr-3">${escapeHtml(label)}</span><span>${n}</span></div><div class="h-2 rounded-full bg-slate-100 overflow-hidden"><div class="h-full rounded-full bg-blue-500" style="width:${Math.round(n/max*100)}%"></div></div></div>`}).join('');
}
function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}