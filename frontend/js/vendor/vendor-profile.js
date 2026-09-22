(function(){
'use strict';
function apiBase(){return window.FOOD_COURT_API_BASE||(typeof window.getApiUrl==='function'?window.getApiUrl('').replace(/\/$/,''):'https://college-food-court-api.onrender.com/api');}
async function loadVendorProfile(){
 try{
  const res=await fetch(apiBase()+'/auth/me',{credentials:'include'});
  const data=await res.json();
  if(!res.ok||!data.authenticated||data.user.role!=='vendor'){location.href='login.html';return;}
  const u=data.user||{};
  const name=u.full_name||'Vendor';
  const shop=u.shop_name||'No stall assigned';
  const initial=(name.trim().charAt(0)||'V').toUpperCase();
  document.getElementById('vendor-profile-name').textContent=name;
  document.getElementById('vendor-profile-role').textContent=shop+' Vendor';
  document.getElementById('vendor-profile-email').textContent=u.email||'—';
  document.getElementById('vendor-profile-shop').textContent=shop;
  document.getElementById('vendor-profile-id').textContent=u.id??'—';
  document.getElementById('vendor-profile-avatar').textContent=initial;
 }catch(e){
  const m=document.getElementById('vendor-profile-message');m.textContent='Unable to load profile. Please refresh and try again.';m.className='mt-5 rounded-xl p-3 text-xs font-bold bg-rose-50 border border-rose-200 text-rose-700';
 }
}
async function logout(){
 if(!confirm('Are you sure you want to sign out?'))return;
 try{await fetch(apiBase()+'/auth/logout',{method:'POST',credentials:'include'});}catch(e){}
 sessionStorage.removeItem('foodCourtUser');localStorage.removeItem('foodCourtUser');location.href='login.html';
}
document.addEventListener('DOMContentLoaded',function(){loadVendorProfile();document.getElementById('vendor-profile-logout').addEventListener('click',logout);});
})();