function formatOrderDateTime(value) {
  const raw = String(value || '').trim();
  if (!raw) return '—';
  let normalized = raw.includes('T') ? raw : raw.replace(' ', 'T');
  if (!/[zZ]|[+-]\d{2}:?\d{2}$/.test(normalized)) normalized += 'Z';
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return raw;
  return new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true
  }).format(date);
}

const MANAGE_ORDERS_API = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');
let manageOrdersShopId = null;
let selectedOrderStatus = 'all';

document.addEventListener('DOMContentLoaded', initManageOrders);

async function initManageOrders() {
  try {
    const auth = await fetch(`${MANAGE_ORDERS_API}/auth/me`, {credentials:'include'});
    const authData = await auth.json();
    if (!auth.ok || !authData.authenticated || !['vendor','admin'].includes(authData.user.role)) { window.location.href='login.html'; return; }
    const shopRes = await fetch(`${MANAGE_ORDERS_API}/vendor/shop`, {credentials:'include'});
    const shopData = await shopRes.json();
    if (!shopRes.ok || !shopData.success || !shopData.shop) { showOrdersMessage(shopData.message || 'No assigned shop found.', false); return; }
    manageOrdersShopId = shopData.shop.id;
    document.getElementById('order-shop-name').textContent = shopData.shop.name;
    document.querySelectorAll('.order-filter').forEach(btn => btn.addEventListener('click', () => {
      selectedOrderStatus = btn.dataset.status;
      document.querySelectorAll('.order-filter').forEach(x => x.className='order-filter px-3 py-2 rounded-xl bg-slate-100 text-slate-700 text-xs font-black');
      btn.className='order-filter px-3 py-2 rounded-xl bg-blue-600 text-white text-xs font-black';
      renderOrders();
    }));
    await loadOrders();
  } catch (e) { showOrdersMessage('Unable to connect to the server.', false); }
}

let cachedOrders = [];
async function loadOrders() {
  try {
    const res = await fetch(`${MANAGE_ORDERS_API}/vendor/orders?include_all=1`, {credentials:'include'});
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.message || 'Unable to load orders');
    cachedOrders = data.orders || [];
    renderOrders();
  } catch(e) {
    showOrdersMessage(e.message || 'Failed to load orders.', false);
  }
}

function renderOrders() {
  const container = document.getElementById('orders-list');
  const orders = (selectedOrderStatus === 'all' ? cachedOrders : cachedOrders.filter(o => String(o.order_status).toLowerCase() === selectedOrderStatus))
    .slice()
    .sort((a, b) => {
      const statusRank = {pending: 1, preparing: 2, ready: 3, completed: 4, cancelled: 5};
      const sa = statusRank[String(a.order_status || '').toLowerCase()] || 6;
      const sb = statusRank[String(b.order_status || '').toLowerCase()] || 6;
      if (sa !== sb) return sa - sb;
      const da = new Date(String(a.created_at || '').replace(' ', 'T') + (String(a.created_at || '').includes('Z') ? '' : 'Z')).getTime();
      const db = new Date(String(b.created_at || '').replace(' ', 'T') + (String(b.created_at || '').includes('Z') ? '' : 'Z')).getTime();
      if (Number.isFinite(da) && Number.isFinite(db) && da !== db) return da - db;
      return Number(a.id || 0) - Number(b.id || 0);
    });
  if (!orders.length) {
    container.innerHTML='<div class="col-span-full p-12 text-center bg-white rounded-3xl border border-dashed border-slate-200 text-slate-400 text-xs"><i class="fa-regular fa-folder-open text-2xl mb-2"></i><p>No orders in this section.</p></div>';
    return;
  }
  container.innerHTML = orders.map(order => {
    const status = String(order.order_status || '').toLowerCase();
    const statusClass = status==='pending'?'bg-amber-100 text-amber-800':status==='preparing'?'bg-blue-100 text-blue-800':status==='ready'?'bg-purple-100 text-purple-800':status==='completed'?'bg-emerald-100 text-emerald-800':'bg-rose-100 text-rose-800';
    let action='';
    if(status==='pending') action=`<button onclick="setOrderStatus(${order.id},'preparing')" class="px-3 py-2 rounded-xl bg-blue-600 text-white text-xs font-black">Start Preparing</button>`;
    else if(status==='preparing') action=`<button onclick="setOrderStatus(${order.id},'ready')" class="px-3 py-2 rounded-xl bg-amber-500 text-white text-xs font-black">Mark Ready</button>`;
    else if(status==='ready') action='<span class="px-3 py-2 rounded-xl bg-purple-50 text-purple-700 text-xs font-black border border-purple-100">Awaiting Pickup</span>';
    else if(status==='completed') action='<span class="px-3 py-2 rounded-xl bg-emerald-50 text-emerald-700 text-xs font-black">Completed ✓</span>';
    else action='<span class="px-3 py-2 rounded-xl bg-rose-50 text-rose-700 text-xs font-black">Cancelled</span>';
    const items=(order.items||[]).map(i=>`<li class="flex justify-between gap-3"><span>${escapeHtml(i.item_name)} × ${i.quantity}</span><span>₹${Number(i.subtotal||0).toFixed(2)}</span></li>`).join('');
    return `<article class="bg-white rounded-3xl border border-slate-200 shadow-sm p-5">
      <div class="flex items-start justify-between gap-3">
        <div><div class="flex flex-wrap items-center gap-2"><span class="font-mono text-sm font-black text-blue-900">#${escapeHtml(order.order_reference)}</span><span class="px-2.5 py-1 rounded-full text-[10px] font-black uppercase ${statusClass}">${status}</span></div>
        <p class="text-xs font-bold text-slate-700 mt-2">${escapeHtml(order.customer_name||'Customer')}</p>
        <p class="text-[10px] text-slate-400 mt-1">${escapeHtml(formatOrderDateTime(order.created_at))} · ${escapeHtml(order.payment_method||'')} · Payment: ${escapeHtml(order.payment_status||'')}</p>${order.pickup_at ? `<p class="text-[10px] text-teal-700 font-black mt-1"><i class="fa-solid fa-clock mr-1"></i>Pickup: ${escapeHtml(formatOrderDateTime(order.pickup_at))}</p>` : ""}</div>
        <strong class="text-lg font-black text-slate-900">₹${Number(order.total_amount||0).toFixed(2)}</strong>
      </div>
      <div class="mt-4 bg-slate-50 rounded-2xl p-3"><p class="text-[10px] font-black uppercase text-slate-400 mb-2">Items</p><ul class="space-y-1 text-xs text-slate-700">${items||'<li>No item details</li>'}</ul></div>
      <div class="mt-4 flex justify-end">${action}</div>
    </article>`;
  }).join('');
}

async function setOrderStatus(orderId,status) {
  try {
    const res=await fetch(`${MANAGE_ORDERS_API}/orders/${orderId}/status`,{method:'PUT',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({status})});
    const data=await res.json();
    if(!res.ok||!data.success) throw new Error(data.message||'Unable to update order');
    await loadOrders();
  } catch(e) { showOrdersMessage(e.message||'Order update failed.',false); }
}

async function lookupPickupOtp() {
  const input=document.getElementById('verify-otp-input');
  const box=document.getElementById('otp-message');
  const preview=document.getElementById('otp-preview');
  const actions=document.getElementById('otp-verify-actions');
  const otp=(input.value||'').trim();

  preview.classList.add('hidden');
  actions.classList.add('hidden');

  if(!/^\d{6}$/.test(otp)){
    box.className='mt-3 p-3 rounded-xl text-xs font-bold bg-rose-50 border border-rose-200 text-rose-700';
    box.textContent='Enter a valid 6-digit OTP.';
    box.classList.remove('hidden');
    return;
  }

  try {
    const res=await fetch(`${MANAGE_ORDERS_API}/orders/lookup-otp`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      credentials:'include',
      body:JSON.stringify({otp,shop_id:manageOrdersShopId})
    });
    const data=await res.json();
    if(!res.ok||!data.success) throw new Error(data.message||'No matching ready order found.');

    const order=data.order;
    const items=(order.items||[]).map(i=>`<div class="flex justify-between gap-3 text-xs py-1"><span>${escapeHtml(i.item_name)} × ${i.quantity}</span><strong>₹${Number(i.subtotal||0).toFixed(2)}</strong></div>`).join('');

    preview.innerHTML=`<div class="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-4">
      <div class="flex items-start justify-between gap-3">
        <div>
          <div class="flex items-center gap-2"><span class="font-mono text-sm font-black text-blue-900">#${escapeHtml(order.order_reference)}</span><span class="px-2 py-1 rounded-full bg-purple-100 text-purple-700 text-[10px] font-black uppercase">READY</span></div>
          <p class="text-xs font-bold text-slate-800 mt-2">${escapeHtml(order.customer_name||'Customer')}</p>
          <p class="text-[10px] text-slate-500 mt-1">${escapeHtml(formatOrderDateTime(order.created_at))} · ${escapeHtml(order.payment_method||'')}</p>${order.pickup_at ? `<p class="text-[10px] text-teal-700 font-black mt-1"><i class="fa-solid fa-clock mr-1"></i>Pickup: ${escapeHtml(formatOrderDateTime(order.pickup_at))}</p>` : ""}
        </div>
        <strong class="text-lg font-black text-slate-900">₹${Number(order.total_amount||0).toFixed(2)}</strong>
      </div>
      <div class="mt-3 rounded-xl bg-white border border-emerald-100 p-3">
        <p class="text-[10px] font-black uppercase text-slate-400 mb-1">Items</p>
        ${items||'<p class="text-xs text-slate-500">No item details.</p>'}
      </div>
      <p class="mt-3 text-[11px] font-bold text-emerald-700"><i class="fa-solid fa-circle-check mr-1"></i>Order found. Review the details, then click Verify & Complete.</p>
    </div>`;
    preview.classList.remove('hidden');
    actions.classList.remove('hidden');
    box.classList.add('hidden');
  } catch(e) {
    box.className='mt-3 p-3 rounded-xl text-xs font-bold bg-rose-50 border border-rose-200 text-rose-700';
    box.textContent='✗ '+(e.message||'Unable to find the order.');
    box.classList.remove('hidden');
  }
}

function clearPickupOtpPreview(){
  const input=document.getElementById('verify-otp-input');
  const preview=document.getElementById('otp-preview');
  const actions=document.getElementById('otp-verify-actions');
  const box=document.getElementById('otp-message');
  if(input) input.value='';
  if(preview){preview.innerHTML='';preview.classList.add('hidden');}
  if(actions) actions.classList.add('hidden');
  if(box) box.classList.add('hidden');
}

async function verifyPickupOtp() {
  const input=document.getElementById('verify-otp-input'), box=document.getElementById('otp-message');
  const preview=document.getElementById('otp-preview'), actions=document.getElementById('otp-verify-actions');
  const otp=(input.value||'').trim();
  if(!/^\d{6}$/.test(otp)){ box.className='mt-3 p-3 rounded-xl text-xs font-bold bg-rose-50 border border-rose-200 text-rose-700'; box.textContent='Enter a valid 6-digit OTP.'; box.classList.remove('hidden'); return; }
  if(preview.classList.contains('hidden')){
    box.className='mt-3 p-3 rounded-xl text-xs font-bold bg-amber-50 border border-amber-200 text-amber-700';
    box.textContent='Show the matching order first, then verify.';
    box.classList.remove('hidden');
    return;
  }
  try {
    const res=await fetch(`${MANAGE_ORDERS_API}/orders/verify-otp`,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify({otp,shop_id:manageOrdersShopId})});
    const data=await res.json();
    box.className='mt-3 p-3 rounded-xl text-xs font-bold '+(data.success?'bg-emerald-50 border border-emerald-200 text-emerald-700':'bg-rose-50 border border-rose-200 text-rose-700');
    box.textContent=(data.success?'✓ ':'✗ ')+(data.message||'OTP verification failed.');
    box.classList.remove('hidden');
    if(data.success){input.value='';preview.innerHTML='';preview.classList.add('hidden');actions.classList.add('hidden');await loadOrders();}
  } catch(e){ box.className='mt-3 p-3 rounded-xl text-xs font-bold bg-rose-50 border border-rose-200 text-rose-700';box.textContent='Connection error while verifying OTP.';box.classList.remove('hidden'); }
}
function showOrdersMessage(message,success){const el=document.getElementById('orders-message');if(!el)return;el.className='mb-5 p-3 rounded-xl text-xs font-bold '+(success?'bg-emerald-50 border border-emerald-200 text-emerald-700':'bg-rose-50 border border-rose-200 text-rose-700');el.textContent=message;el.classList.remove('hidden');}
function escapeHtml(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}