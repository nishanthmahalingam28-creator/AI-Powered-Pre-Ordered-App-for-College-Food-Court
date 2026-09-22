(function(){
'use strict';
var timer=null;
function api(){return window.FOOD_COURT_API_BASE||(typeof window.getApiUrl==='function'?window.getApiUrl(''):'/api');}
function els(){return {drawer:document.getElementById('vendor-notif-drawer'),backdrop:document.getElementById('vendor-notif-backdrop'),items:document.getElementById('vendor-notif-items')};}
async function fetchCount(){
 try{var r=await fetch(api()+'/notifications/unread-count',{credentials:'include'});if(!r.ok)return;var d=await r.json();if(!d.success)return;
  var n=Number(d.unread_count)||0;document.querySelectorAll('#vendor-notif-badge').forEach(function(b){b.textContent=n>99?'99+':n;b.classList.toggle('hidden',n===0);});
 }catch(e){console.debug('Vendor notification count:',e);}
}
async function load(){
 var e=els();if(!e.items)return;
 e.items.innerHTML='<div class="py-8 text-center text-slate-400"><i class="fa-solid fa-spinner fa-spin text-xl mb-2 text-blue-600"></i><p class="text-xs font-semibold">Loading kitchen alerts...</p></div>';
 try{var r=await fetch(api()+'/notifications?limit=30',{credentials:'include'});var d=await r.json();
  if(!r.ok||!d.success||!d.notifications||!d.notifications.length){e.items.innerHTML='<div class="py-10 text-center text-slate-400"><i class="fa-regular fa-bell-slash text-2xl mb-2 text-slate-300"></i><p class="text-xs font-bold text-slate-600">No active alerts</p><p class="text-[11px] text-slate-400 mt-0.5">New orders and kitchen events will appear here.</p></div>';return;}
  e.items.innerHTML=d.notifications.map(function(item){return '<div class="p-3.5 rounded-2xl border text-xs flex items-start gap-3 '+(item.is_read?'bg-white border-slate-100':'bg-blue-50/50 border-blue-200')+'"><div class="w-8 h-8 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center shrink-0"><i class="fa-solid '+(item.type==='ORDER_CANCELLED'?'fa-ban text-rose-500':'fa-receipt')+'"></i></div><div class="flex-grow min-w-0"><div class="flex items-center justify-between gap-1 mb-0.5"><span class="font-black text-slate-900 truncate">'+String(item.title||'Notification')+'</span><span class="text-[10px] text-slate-400 shrink-0">'+(item.created_at?String(item.created_at).split(' ')[1]||'':'')+'</span></div><p class="text-slate-600 text-[11px] leading-relaxed">'+String(item.message||'')+'</p></div></div>';}).join('');
 }catch(err){e.items.innerHTML='<div class="p-4 text-center text-xs text-rose-500 font-bold">Failed to load alerts.</div>';}
}
window.toggleVendorNotifDrawer=async function(show){var e=els();if(!e.drawer||!e.backdrop)return;e.drawer.classList.toggle('translate-x-full',!show);e.backdrop.classList.toggle('hidden',!show);if(show)await load();};
window.markAllVendorNotifsRead=async function(){try{var r=await fetch(api()+'/notifications/read-all',{method:'PUT',credentials:'include'});if(r.ok){await fetchCount();await load();}}catch(e){console.debug('Mark notifications read:',e);}};
function init(){fetchCount();if(timer)clearInterval(timer);timer=setInterval(fetchCount,30000);}
window.vendorNotificationsReady=init();
window.addEventListener('beforeunload',function(){if(timer)clearInterval(timer);});
})();