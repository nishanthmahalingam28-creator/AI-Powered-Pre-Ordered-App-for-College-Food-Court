(function(){
'use strict';
var titles={dashboard:'Admin Dashboard',shops:'Stalls & Operations',vendors:'Vendors & Assignments',customers:'Customer Management',temporary:'Temporary Accounts',orders:'Global Orders',payments:'Payment Monitoring',audit:'Security Audit Trail'};
function apiBase(){return window.FOOD_COURT_API_BASE||(typeof window.getApiUrl==='function'?window.getApiUrl('').replace(/\/$/,''):'https://college-food-court-api.onrender.com/api');}
function currentTab(){var h=String(location.hash||'#dashboard').replace('#','').toLowerCase();return titles[h]?h:'dashboard';}
function userInfo(){try{return JSON.parse(sessionStorage.getItem('foodCourtUser')||'{}')}catch(e){return{}}}
function setActive(tab){
 document.querySelectorAll('[data-admin-tab]').forEach(function(a){a.classList.toggle('active',a.getAttribute('data-admin-tab')===tab)});
 var title=document.getElementById('admin-workspace-page-title');if(title)title.textContent=titles[tab]||titles.dashboard;
}
function switchAdminTab(tab,updateHash){
 tab=titles[tab] ? tab : 'dashboard';
 var overview=document.getElementById('admin-dashboard-overview');
 var sections=document.querySelectorAll('[id^="section-"]');
 sections.forEach(function(sec){sec.classList.add('hidden');});
 if(overview) overview.classList.toggle('hidden',tab!=='dashboard');
 if(tab!=='dashboard'){
   var target=document.getElementById('section-'+tab);
   if(target) target.classList.remove('hidden');
   if(typeof window.switchTab==='function') window.switchTab(tab);
 }
 setActive(tab);
 if(updateHash!==false){
   var next='#'+tab;
   if(location.hash!==next) history.pushState({adminTab:tab},'',next);
 }
 if(tab==='dashboard') window.scrollTo({top:0,behavior:'smooth'});
 else {
   var sec=document.getElementById('section-'+tab);
   if(sec) setTimeout(function(){sec.scrollIntoView({behavior:'smooth',block:'start'});},40);
 }
}
function openNotif(open){
 var drawer=document.getElementById('admin-notification-drawer'),back=document.getElementById('admin-notification-backdrop');if(!drawer||!back)return;
 drawer.classList.toggle('open',!!open);back.classList.toggle('hidden',!open);drawer.setAttribute('aria-hidden',String(!open));
 if(open)loadNotifications();
}
function formatNotifTime(v){if(!v)return '';var d=new Date(String(v).includes('T')?v:String(v).replace(' ','T')+'Z');if(Number.isNaN(d.getTime()))return String(v);return new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit',hour12:true}).format(d);}
async function refreshUnread(){
 try{var r=await fetch(apiBase()+'/notifications/unread-count',{credentials:'include'});var d=await r.json();var b=document.getElementById('admin-notification-badge');if(!b)return;var n=Number(d.unread_count||0);b.textContent=n>99?'99+':String(n);b.classList.toggle('hidden',n===0);}catch(e){}
}
async function loadNotifications(){
 var list=document.getElementById('admin-notification-list');if(!list)return;
 try{var r=await fetch(apiBase()+'/notifications?limit=50',{credentials:'include'});var d=await r.json();
  if(!r.ok||!d.success)throw new Error(d.message||'Failed');
  var items=Array.isArray(d.notifications)?d.notifications:[];
  list.innerHTML=items.length?items.map(function(n){return '<article class="admin-notification-item '+(!n.is_read?'unread':'')+'" data-notification-id="'+n.id+'"><strong>'+escapeHtml(n.title||'Notification')+'</strong><p>'+escapeHtml(n.message||'')+'</p><time>'+formatNotifTime(n.created_at)+'</time></article>';}).join(''):'<div class="admin-notification-empty">No notifications yet.</div>';
  list.querySelectorAll('[data-notification-id]').forEach(function(el){el.addEventListener('click',async function(){var id=el.getAttribute('data-notification-id');if(el.classList.contains('unread')){try{await fetch(apiBase()+'/notifications/'+id+'/read',{method:'PUT',credentials:'include'});}catch(e){}el.classList.remove('unread');refreshUnread();}})});
  refreshUnread();
 }catch(e){list.innerHTML='<div class="admin-notification-empty">Unable to load notifications. Please refresh.</div>';}
}
function escapeHtml(v){return String(v??'').replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]});}
async function logout(){
 if(!confirm('Are you sure you want to sign out?'))return;
 try{await fetch(apiBase()+'/auth/logout',{method:'POST',credentials:'include'});}catch(e){}
 try{sessionStorage.removeItem('foodCourtUser');localStorage.removeItem('foodCourtUser');}catch(e){}
 location.replace('login.html');
}
function init(){
 document.body.classList.add('admin-workspace-page');
 var u=userInfo(),name=u.full_name||u.name||u.email||'Administrator',initial=(String(name).trim().charAt(0)||'A').toUpperCase();
 var nameEl=document.getElementById('admin-sidebar-name');if(nameEl)nameEl.textContent=name;
 ['admin-sidebar-avatar','admin-top-avatar'].forEach(function(id){var el=document.getElementById(id);if(el)el.textContent=initial});
 document.querySelectorAll('[data-admin-tab]').forEach(function(a){
   a.addEventListener('click',function(e){
     e.preventDefault();
     e.stopPropagation();
     switchAdminTab(a.getAttribute('data-admin-tab'),true);
     var p=document.getElementById('admin-mobile-workspace-panel');if(p)p.classList.remove('open');
     var m=document.getElementById('admin-mobile-workspace-menu');if(m)m.setAttribute('aria-expanded','false');
   });
 });
 window.addEventListener('hashchange',function(){switchAdminTab(currentTab(),false);});
 var m=document.getElementById('admin-mobile-workspace-menu'),p=document.getElementById('admin-mobile-workspace-panel');
 if(m&&p){m.addEventListener('click',function(){var open=p.classList.toggle('open');m.setAttribute('aria-expanded',String(open));});document.addEventListener('click',function(e){if(!m.contains(e.target)&&!p.contains(e.target))p.classList.remove('open')});}
 var logoutBtn=document.getElementById('admin-workspace-logout');if(logoutBtn)logoutBtn.addEventListener('click',logout);
 var trigger=document.getElementById('admin-notification-trigger'),close=document.getElementById('admin-notification-close'),back=document.getElementById('admin-notification-backdrop'),mark=document.getElementById('admin-mark-all-read');
 if(trigger)trigger.addEventListener('click',function(){openNotif(true)});if(close)close.addEventListener('click',function(){openNotif(false)});if(back)back.addEventListener('click',function(){openNotif(false)});
 if(mark)mark.addEventListener('click',async function(){try{await fetch(apiBase()+'/notifications/read-all',{method:'PUT',credentials:'include'});await loadNotifications();}catch(e){}});
 var initialTab=currentTab();switchAdminTab(initialTab,false);refreshUnread();setInterval(refreshUnread,30000);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();