const SURVEY_RESULTS_API=window.FOOD_COURT_API_BASE||(typeof window.getApiUrl==='function'?window.getApiUrl(''):'/api');
document.addEventListener('DOMContentLoaded',loadResults);
async function loadResults(){
 try{
  const auth=await fetch(`${SURVEY_RESULTS_API}/auth/me`,{credentials:'include'}),ad=await auth.json();
  if(!auth.ok||!ad.authenticated||!['vendor','admin'].includes(ad.user.role)){location.href='login.html';return;}
  const res=await fetch(`${SURVEY_RESULTS_API}/vendor/daily-survey/vote-results`,{credentials:'include'}),data=await res.json();
  if(!res.ok||!data.success)throw new Error(data.message||'Unable to load vote results');
  document.getElementById('results-date').textContent=data.survey?`Student votes for ${data.date}`:`No survey published for ${data.date}`;
  const total=Number(data.total_votes)||0, options=data.options||[];
  document.getElementById('summary').innerHTML=[
   ['Total Student Votes',total,'fa-users','bg-blue-50 text-blue-700'],
   ['Food Options',options.length,'fa-utensils','bg-emerald-50 text-emerald-700'],
   ['Survey Status',data.survey?(data.survey.is_serving_today?'Open':'Closed'):'Not Published','fa-sun','bg-amber-50 text-amber-700']
  ].map(x=>`<div class="bg-white rounded-3xl border border-slate-200 p-5 shadow-sm"><div class="w-10 h-10 rounded-xl ${x[3]} flex items-center justify-center mb-3"><i class="fa-solid ${x[2]}"></i></div><p class="text-[10px] font-black uppercase text-slate-400">${x[0]}</p><p class="text-2xl font-black text-slate-900 mt-1">${x[1]}</p></div>`).join('');
  renderVotes('meal',options.filter(x=>x.meal_period==='breakfast'),'Breakfast');
  renderVotes('preferences',options.filter(x=>x.meal_period==='lunch'),'Lunch');
  renderVotes('diet',options.filter(x=>x.meal_period==='dinner'),'Dinner');
  const hunger=document.getElementById('hunger');hunger.innerHTML=options.length?'<p class="text-xs text-slate-500">Students can vote once per survey. Results update whenever this page is refreshed.</p>':'<p class="text-xs text-slate-400 py-5 text-center">No votes yet.</p>';
 }catch(e){const m=document.getElementById('message');m.className='mb-5 p-3 rounded-xl text-xs font-bold bg-rose-50 border border-rose-200 text-rose-700';m.textContent=e.message||'Unable to load results';m.classList.remove('hidden');}
}
function renderVotes(id,rows,title){
 const el=document.getElementById(id);if(!rows.length){el.innerHTML=`<p class="text-xs text-slate-400 py-5 text-center">No ${title} options.</p>`;return;}
 el.innerHTML=`<h3 class="font-black text-slate-800 mb-4">${title}</h3>`+rows.map(r=>`<div class="mb-4"><div class="flex justify-between text-xs font-bold mb-1"><span class="truncate pr-3">${escapeHtml(r.item_name)}</span><span>${r.vote_count} vote(s) · ${r.percentage}%</span></div><div class="h-2 rounded-full bg-slate-100 overflow-hidden"><div class="h-full rounded-full bg-blue-500" style="width:${Math.min(100,Number(r.percentage)||0)}%"></div></div></div>`).join('');
}
function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}