document.addEventListener('DOMContentLoaded',loadMorningPoll);
const API_BASE=window.FOOD_COURT_API_BASE||(typeof window.getApiUrl==='function'?window.getApiUrl(''):'/api');

async function loadMorningPoll(){
 try{
  const auth=await fetch(API_BASE+'/auth/me',{credentials:'include'}),ad=await auth.json();
  if(!auth.ok||!ad.authenticated||ad.user.role!=='customer'){location.href='../auth/login.html';return;}
  const res=await fetch(API_BASE+'/customer/morning-poll/today',{credentials:'include'}),data=await res.json();
  if(!res.ok||!data.success)throw Error(data.message||'Unable to load morning survey.');
  document.getElementById('poll-loading').classList.add('hidden');
  const list=document.getElementById('poll-list'),surveys=data.surveys||[];
  if(!surveys.length){document.getElementById('poll-empty').classList.remove('hidden');return;}
  list.innerHTML=surveys.map(renderSurvey).join('');
 }catch(e){
  document.getElementById('poll-loading').classList.add('hidden');
  showPollMessage(e.message||'Unable to load morning survey.',false);
 }
}

function renderSurvey(s){
 const options=s.options||[];
 const grouped={breakfast:[],lunch:[],dinner:[]};
 options.forEach(o=>grouped[String(o.meal_period||'lunch').toLowerCase()]?.push(o));
 const sections=Object.entries(grouped).filter(([,rows])=>rows.length).map(([period,rows])=>`
  <div class="mb-5">
   <p class="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">${period}</p>
   <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
    ${rows.map(o=>`<label class="food-vote-option block cursor-pointer rounded-2xl border-2 border-slate-200 hover:border-teal-400 p-4">
      <input type="radio" name="food-choice-${s.survey_id}" value="${o.id}" class="sr-only" ${String(s.voted_menu_item_id)===String(o.id)?'checked':''} ${s.voted?'disabled':''}>
      <div class="flex items-center justify-between gap-3">
       <div><p class="font-black text-slate-900">${escapeHtml(o.item_name)}</p><p class="text-xs text-slate-400 mt-1">₹${Number(o.price||0).toFixed(2)}</p></div>
       <i class="fa-solid fa-circle-check text-teal-600 opacity-0 vote-check"></i>
      </div>
    </label>`).join('')}
   </div>
  </div>`).join('');
 return `<section class="bg-white rounded-3xl border border-slate-200 shadow-sm p-5 sm:p-6">
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
   <div><p class="text-[10px] font-black uppercase tracking-widest text-teal-600">Today's Food Vote</p><h2 class="text-xl font-black text-slate-900 mt-1">${escapeHtml(s.shop_name||'Food Court')}</h2><p class="text-xs text-slate-400 mt-1">Which food do you want to eat today?</p></div>
   <span class="px-3 py-1.5 rounded-full text-[10px] font-black ${s.voted?'bg-emerald-100 text-emerald-700':'bg-amber-100 text-amber-700'}">${s.voted?'✓ Vote Recorded':'Vote Needed'}</span>
  </div>
  ${sections||'<p class="text-sm text-slate-400 text-center py-6">No food choices published for this shop yet.</p>'}
  <div class="flex justify-end"><button onclick="submitFoodVote(${s.survey_id})" class="px-5 py-3 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-black ${s.voted?'hidden':''}">Submit Food Vote</button></div>
 </section>`;
}

async function submitFoodVote(id){
 const selected=document.querySelector(`input[name="food-choice-${id}"]:checked`);
 if(!selected){showPollMessage('Please choose the food you want to eat today.',false);return;}
 try{
  const res=await fetch(API_BASE+'/customer/morning-poll/vote',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({survey_id:id,menu_item_id:Number(selected.value)})});
  const data=await res.json();
  if(!res.ok||!data.success)throw Error(data.message||'Unable to record vote.');
  showPollMessage('Your food vote has been recorded.',true);
  await loadMorningPoll();
 }catch(e){showPollMessage(e.message||'Unable to record vote.',false);}
}
function showPollMessage(m,ok){const e=document.getElementById('poll-message');e.textContent=m;e.className='mb-5 p-4 rounded-2xl text-sm font-bold '+(ok?'bg-emerald-50 border border-emerald-200 text-emerald-700':'bg-rose-50 border border-rose-200 text-rose-700');e.classList.remove('hidden');}
function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}