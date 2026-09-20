const WORKERS_API = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');
let workers = [];

function todayISO() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}
function monthISO() { return todayISO().slice(0,7); }
function money(v) { return `₹${Number(v||0).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2})}`; }
function esc(v) { const d=document.createElement('div'); d.textContent=v==null?'':String(v); return d.innerHTML; }
function showMessage(text, ok=true) {
  const el=document.getElementById('message'); el.textContent=text;
  el.className=`mb-5 px-4 py-3 rounded-xl text-sm font-bold ${ok?'bg-emerald-50 border border-emerald-100 text-emerald-700':'bg-rose-50 border border-rose-100 text-rose-700'}`;
}
function hideMessage(){document.getElementById('message').classList.add('hidden');}

async function api(path, options={}) {
  const res=await fetch(`${WORKERS_API}${path}`,{credentials:'include',headers:{'Content-Type':'application/json',...(options.headers||{})},...options});
  const data=await res.json().catch(()=>({}));
  if(!res.ok) throw new Error(data.message||'Request failed.');
  return data;
}

document.addEventListener('DOMContentLoaded', async ()=>{
  document.getElementById('attendance-date').value=todayISO();
  document.getElementById('salary-month').value=monthISO();
  try {
    const me=await api('/auth/me');
    if(!me.authenticated || !me.user || !['vendor','admin'].includes(me.user.role)){location.href='login.html';return;}
    const shop=await api('/vendor/shop');
    if(shop.success && shop.shop) document.getElementById('shop-name').textContent=shop.shop.name;
    await Promise.all([loadWorkers(),loadAttendance(),loadSalary()]);
  } catch(e) { showMessage(e.message,false); }
});

async function loadWorkers(){
  const data=await api('/vendor/workers'); workers=data.workers||[];
  document.getElementById('total-workers').textContent=workers.length;
  document.getElementById('active-workers').textContent=workers.filter(w=>w.status==='active').length;
  document.getElementById('monthly-salary').textContent=money(workers.filter(w=>w.status==='active'&&w.salary_type==='monthly').reduce((s,w)=>s+Number(w.salary_amount||0),0));
  renderWorkers();
}
function renderWorkers(){
  const body=document.getElementById('workers-table');
  if(!workers.length){body.innerHTML='<tr><td colspan="5" class="px-5 py-12 text-center text-sm text-slate-400">No workers added yet. Click Add Worker.</td></tr>';return;}
  body.innerHTML=workers.map(w=>`
    <tr class="border-b border-slate-100 hover:bg-slate-50">
      <td class="px-5 py-4"><div class="font-black">${esc(w.full_name)}</div><div class="text-[11px] text-slate-400">${esc(w.employee_code)} · ${esc(w.phone||'No phone')}</div></td>
      <td class="px-5 py-4"><span class="font-bold">${esc(w.role_title)}</span><div class="text-[11px] text-slate-400">${w.status}</div></td>
      <td class="px-5 py-4 font-black">${money(w.salary_amount)} <span class="text-[10px] text-slate-400 font-bold">/${w.salary_type}</span></td>
      <td class="px-5 py-4 font-bold">${w.attendance_days||0} days</td>
      <td class="px-5 py-4 text-right"><button onclick="editWorker(${w.id})" class="px-3 py-2 rounded-lg bg-blue-50 text-blue-700 text-xs font-black mr-1"><i class="fa-solid fa-pen"></i></button><button onclick="deleteWorker(${w.id})" class="px-3 py-2 rounded-lg bg-rose-50 text-rose-700 text-xs font-black"><i class="fa-solid fa-trash"></i></button></td>
    </tr>`).join('');
}
function openWorkerModal(worker=null){
  document.getElementById('worker-modal').classList.remove('hidden');document.getElementById('worker-modal').classList.add('flex');
  document.getElementById('modal-title').textContent=worker?'Edit Worker':'Add Worker';
  document.getElementById('worker-id').value=worker?.id||'';
  document.getElementById('employee-code').value=worker?.employee_code||'';
  document.getElementById('employee-code').disabled=!!worker;
  document.getElementById('full-name').value=worker?.full_name||'';
  document.getElementById('phone').value=worker?.phone||'';
  document.getElementById('role-title').value=worker?.role_title||'Kitchen Staff';
  document.getElementById('salary-type').value=worker?.salary_type||'monthly';
  document.getElementById('salary-amount').value=worker?.salary_amount||0;
  document.getElementById('joining-date').value=worker?.joining_date||'';
}
function closeWorkerModal(){const m=document.getElementById('worker-modal');m.classList.add('hidden');m.classList.remove('flex');}
function editWorker(id){const w=workers.find(x=>Number(x.id)===Number(id));if(w)openWorkerModal(w);}
async function saveWorker(e){
  e.preventDefault();hideMessage();
  const id=document.getElementById('worker-id').value;
  const payload={employee_code:document.getElementById('employee-code').value.trim(),full_name:document.getElementById('full-name').value.trim(),phone:document.getElementById('phone').value.trim(),role_title:document.getElementById('role-title').value.trim(),salary_type:document.getElementById('salary-type').value,salary_amount:document.getElementById('salary-amount').value,joining_date:document.getElementById('joining-date').value||null};
  try{await api(id?`/vendor/workers/${id}`:'/vendor/workers',{method:id?'PUT':'POST',body:JSON.stringify(payload)});closeWorkerModal();showMessage(id?'Worker updated.':'Worker added.');await Promise.all([loadWorkers(),loadAttendance(),loadSalary()]);}catch(e){showMessage(e.message,false);}
}
async function deleteWorker(id){
  const w=workers.find(x=>Number(x.id)===Number(id));if(!w)return;
  if(!confirm(`Delete worker "${w.full_name}"? This will also remove attendance and salary records for this worker.`))return;
  try{await api(`/vendor/workers/${id}`,{method:'DELETE'});showMessage('Worker deleted.');await Promise.all([loadWorkers(),loadAttendance(),loadSalary()]);}catch(e){showMessage(e.message,false);}
}

async function loadAttendance(){
  try{
    const date=document.getElementById('attendance-date').value||todayISO();
    const data=await api(`/vendor/workers/attendance?date=${encodeURIComponent(date)}`);
    const rows=data.attendance||[];
    document.getElementById('present-workers').textContent=rows.filter(x=>x.attendance_status==='present').length;
    const box=document.getElementById('attendance-list');
    if(!rows.length){box.innerHTML='<p class="text-sm text-slate-400 text-center py-8">Add workers to record attendance.</p>';return;}
    box.innerHTML=rows.map(r=>`
      <div class="bg-white rounded-xl border border-cyan-100 p-3">
        <div class="flex items-center justify-between gap-3 mb-2"><div><div class="font-black text-sm">${esc(r.full_name)}</div><div class="text-[10px] text-slate-400">${esc(r.employee_code)} · ${esc(r.role_title)}</div></div>
        <select id="att-${r.worker_id}" class="rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-bold"><option value="present" ${r.attendance_status==='present'?'selected':''}>Present</option><option value="absent" ${r.attendance_status==='absent'?'selected':''}>Absent</option><option value="half_day" ${r.attendance_status==='half_day'?'selected':''}>Half Day</option><option value="leave" ${r.attendance_status==='leave'?'selected':''}>Leave</option></select></div>
        <div class="grid grid-cols-2 gap-2"><input id="in-${r.worker_id}" type="time" value="${r.check_in||''}" class="rounded-lg border border-slate-200 px-2 py-2 text-xs"><input id="out-${r.worker_id}" type="time" value="${r.check_out||''}" class="rounded-lg border border-slate-200 px-2 py-2 text-xs"></div>
        <button onclick="saveAttendance(${r.worker_id})" class="w-full mt-2 rounded-lg bg-cyan-600 hover:bg-cyan-700 text-white py-2 text-xs font-black">Save Attendance</button>
      </div>`).join('');
  }catch(e){showMessage(e.message,false);}
}
async function saveAttendance(workerId){
  const date=document.getElementById('attendance-date').value||todayISO();
  const payload={worker_id:workerId,attendance_date:date,status:document.getElementById(`att-${workerId}`).value,check_in:document.getElementById(`in-${workerId}`).value||null,check_out:document.getElementById(`out-${workerId}`).value||null};
  try{await api('/vendor/workers/attendance',{method:'POST',body:JSON.stringify(payload)});showMessage('Attendance saved.');await Promise.all([loadAttendance(),loadWorkers(),loadSalary()]);}catch(e){showMessage(e.message,false);}
}

async function loadSalary(){
  try{
    const monthInput=document.getElementById('salary-month').value||monthISO();
    const month=`${monthInput}-01`;
    const data=await api(`/vendor/workers/salary?month=${month}`);
    const rows=data.salary||[]; const box=document.getElementById('salary-list');
    if(!rows.length){box.innerHTML='<p class="text-sm text-slate-400 text-center py-8">No workers added yet.</p>';return;}
    box.innerHTML=rows.map(r=>`
      <div class="bg-white rounded-xl border border-amber-100 p-4">
        <div class="flex items-center justify-between gap-3"><div><div class="font-black text-sm">${esc(r.full_name)}</div><div class="text-[10px] text-slate-400">${esc(r.employee_code)} · ${r.attendance_days} attendance days</div></div><span class="px-2 py-1 rounded-full text-[10px] font-black ${r.salary_status==='paid'?'bg-emerald-100 text-emerald-700':'bg-rose-100 text-rose-700'}">${r.salary_status.toUpperCase()}</span></div>
        <div class="grid grid-cols-2 gap-2 mt-3"><div><div class="text-[10px] text-slate-400">Salary</div><div class="font-black">${money(r.salary_amount)}</div></div><div><div class="text-[10px] text-slate-400">Paid</div><div class="font-black">${money(r.paid_amount)}</div></div></div>
        <button onclick="recordSalary(${r.worker_id},${Number(r.salary_amount||0)})" class="w-full mt-3 rounded-lg bg-amber-500 hover:bg-amber-600 text-white py-2 text-xs font-black">${r.salary_status==='paid'?'Update Salary Payment':'Mark Salary Paid'}</button>
      </div>`).join('');
  }catch(e){showMessage(e.message,false);}
}
async function recordSalary(workerId,amount){
  const monthInput=document.getElementById('salary-month').value||monthISO();
  const paid=prompt('Enter paid salary amount (₹):',String(amount));
  if(paid===null)return;
  const status=confirm('Mark this salary as PAID? Click Cancel for Pending.')?'paid':'pending';
  try{await api(`/vendor/workers/${workerId}/salary`,{method:'POST',body:JSON.stringify({salary_month:`${monthInput}-01`,paid_amount:paid,status,paid_on:status==='paid'?todayISO():null})});showMessage('Salary record saved.');await loadSalary();}catch(e){showMessage(e.message,false);}
}
