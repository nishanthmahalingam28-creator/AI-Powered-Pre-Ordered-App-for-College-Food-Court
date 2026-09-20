document.addEventListener('DOMContentLoaded', loadMorningPoll);
const API_BASE = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');

async function loadMorningPoll(){
  try{
    const auth=await fetch(`${API_BASE}/auth/me`,{credentials:'include'}), ad=await auth.json();
    if(!auth.ok || !ad.authenticated || ad.user.role!=='customer'){ location.href='../auth/login.html'; return; }
    const res=await fetch(`${API_BASE}/customer/morning-poll/today`,{credentials:'include'}), data=await res.json();
    if(!res.ok || !data.success) throw new Error(data.message||'Unable to load morning surveys.');
    document.getElementById('poll-loading').classList.add('hidden');
    const list=document.getElementById('poll-list');
    const surveys=data.surveys||[];
    if(!surveys.length){document.getElementById('poll-empty').classList.remove('hidden');return;}
    list.innerHTML=surveys.map(renderSurvey).join('');
  }catch(e){
    document.getElementById('poll-loading').classList.add('hidden');
    showPollMessage(e.message||'Unable to load today\'s morning survey.',false);
  }
}

function renderSurvey(s){
  const disabled=s.voted?'disabled':'';
  const grouped={breakfast:[],lunch:[],dinner:[]};
  (s.options||[]).forEach(o=>(grouped[o.meal_period]||(grouped[o.meal_period]=[])).push(o));
  const body=Object.keys(grouped).filter(k=>grouped[k].length).map(period=>`
    <div><p class="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-2">${escapeHtml(period)}</p>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">${grouped[period].map(o=>`
        <label class="poll-option block cursor-pointer rounded-2xl border-2 ${s.voted&&Number(s.voted_menu_item_id)===Number(o.menu_item_id)?'border-emerald-500 bg-emerald-50':'border-slate-200 bg-white hover:border-teal-400'} p-4">
          <input type="radio" name="survey-${s.survey_id}" value="${o.menu_item_id}" class="mr-2 accent-teal-600" ${disabled} ${s.voted&&Number(s.voted_menu_item_id)===Number(o.menu_item_id)?'checked':''}>
          <span class="font-black text-sm text-slate-800">${escapeHtml(o.item_name)}</span>
          <span class="block text-[11px] text-slate-400 mt-1">₹${Number(o.price).toFixed(2)} · ${Number(o.quantity)} available</span>
        </label>`).join('')}</div>
    </div>`).join('');
  return `<section class="bg-white rounded-3xl border border-slate-200 shadow-sm p-5 sm:p-6">
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
      <div><p class="text-[10px] font-black uppercase tracking-widest text-teal-600">Vendor Morning Survey</p><h2 class="text-xl font-black text-slate-900 mt-1">${escapeHtml(s.shop_name)}</h2><p class="text-xs text-slate-400 mt-1">Choose one food option.</p></div>
      <span class="px-3 py-1.5 rounded-full text-[10px] font-black ${s.voted?'bg-emerald-100 text-emerald-700':'bg-amber-100 text-amber-700'}">${s.voted?'✓ Voted':'Voting Open'}</span>
    </div>
    <div class="space-y-5">${body}</div>
    <div class="mt-6 flex flex-col sm:flex-row items-center justify-between gap-3">
      <p class="text-xs ${s.voted?'text-emerald-600':'text-slate-400'} font-bold">${s.voted?'Your vote has already been recorded for this survey.':'You can vote once for this survey.'}</p>
      <button onclick="submitMorningVote(${s.survey_id})" class="px-5 py-3 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-black ${s.voted?'hidden':''}">Submit Vote</button>
    </div>
  </section>`;
}

async function submitMorningVote(surveyId){
  const selected=document.querySelector(`input[name="survey-${surveyId}"]:checked`);
  if(!selected){showPollMessage('Please select one food option before voting.',false);return;}
  try{
    const res=await fetch(`${API_BASE}/customer/morning-poll/vote`,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({survey_id:surveyId,menu_item_id:Number(selected.value)})});
    const data=await res.json();
    if(!res.ok||!data.success)throw new Error(data.message||'Unable to record your vote.');
    showPollMessage('Your vote has been recorded successfully.',true);
    await loadMorningPoll();
  }catch(e){showPollMessage(e.message||'Unable to record your vote.',false);}
}

function showPollMessage(message,ok){
  const el=document.getElementById('poll-message');el.textContent=message;el.className='mb-5 p-4 rounded-2xl text-sm font-bold '+(ok?'bg-emerald-50 border border-emerald-200 text-emerald-700':'bg-rose-50 border border-rose-200 text-rose-700');el.classList.remove('hidden');
}
function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}