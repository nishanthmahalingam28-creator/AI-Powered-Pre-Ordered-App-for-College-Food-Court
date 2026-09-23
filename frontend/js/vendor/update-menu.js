const UPDATE_MENU_API = window.FOOD_COURT_API_BASE || (typeof window.getApiUrl === 'function' ? window.getApiUrl('') : '/api');
let updateMenuShopId = null;
let updateMenuItems = [];

document.addEventListener('DOMContentLoaded', initUpdateMenu);

async function initUpdateMenu() {
  try {
    const [auth, shopRes] = await Promise.all([
      fetch(`${UPDATE_MENU_API}/auth/me`, {credentials:'include'}),
      fetch(`${UPDATE_MENU_API}/vendor/shop`, {credentials:'include'})
    ]);
    const authData = await auth.json();
    if (!auth.ok || !authData.authenticated || !['vendor','admin'].includes(authData.user.role)) { window.location.href='login.html'; return; }
    const shopData = await shopRes.json();
    if (!shopData.success || !shopData.shop) { showMenuMessage(shopData.message || 'No assigned shop found.', false); return; }
    updateMenuShopId = shopData.shop.id;
    document.getElementById('menu-shop-name').textContent = shopData.shop.name;
    await loadUpdateMenu();
  } catch(e) { showMenuMessage('Unable to connect to the server.', false); }
}

async function loadUpdateMenu() {
  const res = await fetch(`${UPDATE_MENU_API}/menu?shop_id=${updateMenuShopId}`);
  const data = await res.json();
  if (!data.success) { showMenuMessage(data.message || 'Unable to load menu.', false); return; }
  updateMenuItems = data.items || [];
  ['breakfast','lunch','dinner'].forEach(renderMealSection);
}

function renderMealSection(period) {
  const list = document.getElementById(period+'-list');
  const items = updateMenuItems.filter(i => (i.meal_period || 'lunch') === period);
  document.getElementById(period+'-count').textContent = items.length;
  list.innerHTML = items.length ? items.map(item => `
    <article class="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0"><h3 class="font-black text-sm truncate">${escapeHtml(item.name)}</h3><p class="text-[10px] text-slate-400 mt-1">${escapeHtml(item.category)}</p></div>
        <span class="font-black text-sm text-blue-600">₹${Number(item.price).toFixed(2)}</span>
      </div>
      <div class="grid grid-cols-2 gap-2 mt-4">
        <button onclick="editPrice(${item.id},${item.price})" class="py-2 rounded-lg bg-slate-100 hover:bg-blue-50 text-[10px] font-black"><i class="fa-solid fa-pen mr-1"></i>Price</button>
        <button onclick="changePeriod(${item.id},'${period}')" class="py-2 rounded-lg bg-slate-100 hover:bg-amber-50 text-[10px] font-black">Move Section</button>
      </div>
      <div class="flex items-center justify-between mt-3">
        <div class="flex items-center gap-2"><button onclick="changeQty(${item.id},-1)" class="w-8 h-8 rounded-lg bg-slate-100 font-black">−</button><span class="text-xs font-black w-8 text-center">${item.quantity}</span><button onclick="changeQty(${item.id},1)" class="w-8 h-8 rounded-lg bg-slate-100 font-black">+</button></div>
        <div class="flex items-center gap-2"><span class="text-[10px] font-bold ${item.is_available ? 'text-emerald-600':'text-rose-600'}">${item.is_available ? 'AVAILABLE':'UNAVAILABLE'}</span><button onclick="toggleAvailable(${item.id},${!!item.is_available})" class="w-8 h-8 rounded-lg bg-slate-100"><i class="fa-solid fa-power-off text-[10px]"></i></button><button onclick="removeItem(${item.id})" class="w-8 h-8 rounded-lg bg-rose-50 text-rose-600"><i class="fa-solid fa-trash text-[10px]"></i></button></div>
      </div>
    </article>`).join('') : '<div class="p-6 text-center text-xs text-slate-400 bg-white/60 rounded-2xl border border-dashed border-slate-200">No dishes in this section.</div>';
}

async function apiUpdate(id, body) {
  const res = await fetch(`${UPDATE_MENU_API}/vendor/menu/item/${id}`, {method:'PUT',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify(body)});
  const data = await res.json(); if (!data.success) throw new Error(data.message || 'Update failed'); await loadUpdateMenu();
}
async function changeQty(id, delta) { const item=updateMenuItems.find(x=>x.id===id); if(item) await apiUpdate(id,{quantity:Math.max(0,Number(item.quantity)+delta),available:Math.max(0,Number(item.quantity)+delta)>0}); }
async function toggleAvailable(id, current) { await apiUpdate(id,{available:!current}); }
async function editPrice(id,current) { const v=prompt('Enter new price (₹):',current); if(v===null)return; const n=Number(v); if(!n||n<=0){alert('Enter a valid price.');return;} await apiUpdate(id,{price:n}); }
async function changePeriod(id,current) { const next=prompt('Enter meal section: breakfast, lunch, or dinner',current); if(next===null)return; const p=next.trim().toLowerCase(); if(!['breakfast','lunch','dinner'].includes(p)){alert('Use breakfast, lunch, or dinner.');return;} await apiUpdate(id,{meal_period:p}); }
async function removeItem(id) {
  const item = updateMenuItems.find(x => Number(x.id) === Number(id));
  const name = item ? item.name : 'this dish';
  if(!confirm(`Remove "${name}" from the menu?`)) return;

  const buttons = document.querySelectorAll('button[onclick*="removeItem("]');
  buttons.forEach(button => {
    if (button.getAttribute('onclick')?.includes(`removeItem(${id},`)) {
      button.disabled = true;
      button.classList.add('opacity-50','pointer-events-none');
    }
  });

  try {
    const res = await fetch(`${UPDATE_MENU_API}/vendor/menu/item/${id}`, {
      method:'DELETE',
      credentials:'include',
      headers:{'Accept':'application/json'}
    });
    const data = await res.json().catch(() => ({}));

    if (!res.ok || !data.success) {
      throw new Error(data.message || `Delete failed (HTTP ${res.status}).`);
    }

    await loadUpdateMenu();
    showMenuMessage(data.message || 'Dish deleted successfully.', true);
  } catch (error) {
    console.error('Menu delete error:', error);
    alert(error.message || 'Unable to delete this dish. Please try again.');
  } finally {
    buttons.forEach(button => {
      if (button.getAttribute('onclick')?.includes(`removeItem(${id},`)) {
        button.disabled = false;
        button.classList.remove('opacity-50','pointer-events-none');
      }
    });
  }
}
async function addMenuItem(e) { e.preventDefault(); const body={name:document.getElementById('menu-name').value.trim(),description:document.getElementById('menu-description').value.trim(),price:Number(document.getElementById('menu-price').value),quantity:Number(document.getElementById('menu-quantity').value),category:document.getElementById('menu-category').value,meal_period:document.getElementById('menu-meal-period').value,available:document.getElementById('menu-available').checked}; try { const res=await fetch(`${UPDATE_MENU_API}/vendor/menu/item`,{method:'POST',headers:{'Content-Type':'application/json'},credentials:'include',body:JSON.stringify(body)}); const data=await res.json(); if(!data.success){alert(data.message||'Add failed.');return;} closeAddMenuModal(); e.target.reset(); await loadUpdateMenu(); } catch(err){alert('Failed to connect to server.');} }
function openAddMenuModal(){const x=document.getElementById('add-menu-modal');x.classList.remove('hidden');x.classList.add('flex');}
function closeAddMenuModal(){const x=document.getElementById('add-menu-modal');x.classList.add('hidden');x.classList.remove('flex');}
function showMenuMessage(m,ok){const x=document.getElementById('menu-page-message');x.textContent=m;x.className='mb-5 p-3 rounded-xl text-xs font-bold '+(ok?'bg-emerald-50 text-emerald-700':'bg-rose-50 text-rose-700');x.classList.remove('hidden');}
function escapeHtml(s){return String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}