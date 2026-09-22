(function(){
'use strict';
var titles={
 'dashboard.html':'Dashboard',
 'manage-orders.html':'Manage Orders',
 'update-menu.html':'Update Menu',
 'morning-survey.html':'Morning Survey',
 'sales-analytics.html':'Sales Analytics',
 'workers.html':'Workers',
 'profile.html':'Profile'
};
function pageName(){return (decodeURIComponent(location.pathname).replace(/\\/g,'/').split('/').pop()||'dashboard.html').toLowerCase();}
function userInfo(){try{return JSON.parse(sessionStorage.getItem('foodCourtUser')||'{}')}catch(e){return{}}}
function componentUrl(file){
 return new URL('../../components/'+file,document.baseURI).href+'?v=20260922';
}
function fallbackSidebar(){return '<aside class="customer-workspace-sidebar vendor-workspace-sidebar" aria-label="Vendor navigation"><div class="customer-workspace-brand"><div class="customer-workspace-brand-mark"><i class="fa-solid fa-store"></i></div><div><strong>KPRIET</strong><span>Vendor Workspace</span></div></div><nav class="customer-workspace-nav"><a href="dashboard.html" data-vendor-link="dashboard.html"><i class="fa-solid fa-table-cells-large"></i><span>Dashboard</span></a><a href="manage-orders.html" data-vendor-link="manage-orders.html"><i class="fa-solid fa-list-check"></i><span>Manage Orders</span></a><a href="update-menu.html" data-vendor-link="update-menu.html"><i class="fa-solid fa-utensils"></i><span>Update Menu</span></a><a href="morning-survey.html" data-vendor-link="morning-survey.html"><i class="fa-solid fa-sun"></i><span>Food Survey</span></a><a href="sales-analytics.html" data-vendor-link="sales-analytics.html"><i class="fa-solid fa-chart-line"></i><span>Sales Analytics</span></a><a href="workers.html" data-vendor-link="workers.html"><i class="fa-solid fa-users-gear"></i><span>Workers</span></a><a href="profile.html" data-vendor-link="profile.html"><i class="fa-solid fa-user"></i><span>Profile</span></a><a href="#vendor-notifications" id="vendor-sidebar-notifications"><i class="fa-regular fa-bell"></i><span>Notifications</span></a></nav><div class="customer-workspace-user"><div class="customer-workspace-avatar" id="vendor-sidebar-avatar">V</div><div><strong id="vendor-sidebar-shop-name">Vendor</strong><span id="vendor-sidebar-user-type">Vendor</span></div><button class="customer-workspace-logout" id="vendor-workspace-logout" title="Logout"><i class="fa-solid fa-arrow-right-from-bracket"></i></button></div></aside>';}
function fallbackNavbar(){return '<header class="customer-workspace-header vendor-workspace-header"><div><span class="customer-workspace-header-label">Vendor workspace</span><h2 id="vendor-workspace-page-title">Vendor Dashboard</h2><button type="button" id="mobile-workspace-menu" class="student-mobile-menu-toggle" aria-label="Open vendor dashboard menu" aria-expanded="false"><span></span><span></span><span></span></button><nav id="mobile-workspace-panel" class="mobile-workspace-panel"><a href="dashboard.html">Dashboard</a><a href="manage-orders.html">Manage Orders</a><a href="update-menu.html">Update Menu</a><a href="morning-survey.html">Food Survey</a><a href="sales-analytics.html">Sales Analytics</a><a href="workers.html">Workers</a><a href="#vendor-notifications">Notifications</a></nav></div><div class="customer-workspace-actions"><button class="customer-workspace-notification notification-bell-trigger" id="vendor-top-notifications" title="Notifications" aria-label="Notifications"><i class="fa-regular fa-bell"></i><span id="vendor-notif-badge" class="notification-badge hidden">0</span></button><span class="customer-workspace-role" id="vendor-workspace-role">Vendor</span><button type="button" class="customer-workspace-top-avatar" id="vendor-top-avatar" title="Open Profile" aria-label="Open Vendor Profile">V</button></div></header>';}
function fallbackNotifications(){return '<div id="vendor-notification-backdrop" class="fixed inset-0 bg-slate-900/40 hidden z-[9998]"></div><aside id="vendor-notification-drawer" class="fixed top-0 right-0 h-full w-full max-w-md bg-white shadow-2xl z-[9999] translate-x-full transition-transform"><div class="p-4 border-b flex items-center justify-between"><strong>Notifications</strong><button type="button" onclick="toggleVendorNotifDrawer(false)">Close</button></div><div id="vendor-notification-list" class="p-4"></div></aside>';}
function build(){
 document.body.classList.add('customer-workspace-page','vendor-workspace-page');
 var page=pageName(),u=userInfo(),name=u.full_name||u.name||'Vendor',shop=u.shop_name||u.shop||'Vendor',initial=(String(name).trim().charAt(0)||'V').toUpperCase();
 var t=document.getElementById('vendor-workspace-page-title'); if(t)t.textContent=titles[page]||'Vendor Workspace';
 var s=document.getElementById('vendor-sidebar-shop-name'); if(s)s.textContent=shop;
 var st=document.getElementById('vendor-sidebar-user-type'); if(st)st.textContent='Vendor';
 var role=document.getElementById('vendor-workspace-role'); if(role)role.textContent=shop+' Vendor';
 ['vendor-sidebar-avatar','vendor-top-avatar'].forEach(function(id){var e=document.getElementById(id);if(e)e.textContent=initial;});
 document.querySelectorAll('[data-vendor-link]').forEach(function(a){a.classList.toggle('active',a.getAttribute('data-vendor-link')===page);});
 var top=document.getElementById('vendor-top-avatar');
 if(top){top.onclick=function(){location.href='profile.html';};}
 document.querySelectorAll('a[data-vendor-link="profile.html"]').forEach(function(link){link.onclick=function(){location.href='profile.html';};});
 var logout=document.getElementById('vendor-workspace-logout');
 if(logout)logout.onclick=async function(e){
  if(e)e.preventDefault();
  if(!confirm('Are you sure you want to sign out?'))return;
  logout.disabled=true;
  try{
   var base=window.FOOD_COURT_API_BASE||(typeof window.getApiUrl==='function'?window.getApiUrl(''):'https://college-food-court-api.onrender.com/api');
   var api=String(base).replace(/\/$/,'');
   await fetch(api+'/auth/logout',{method:'POST',credentials:'include'});
  }catch(err){console.debug('[Vendor Workspace] Logout request:',err);}
  try{sessionStorage.removeItem('foodCourtUser');localStorage.removeItem('foodCourtUser');}catch(err){}
  location.replace('login.html');
 };
 var notify=document.getElementById('vendor-sidebar-notifications');
 if(notify)notify.onclick=function(e){e.preventDefault();if(typeof window.toggleVendorNotifDrawer==='function')window.toggleVendorNotifDrawer(true);};
 var topNotify=document.getElementById('vendor-top-notifications');
 if(topNotify)topNotify.onclick=function(e){e.preventDefault();if(typeof window.toggleVendorNotifDrawer==='function')window.toggleVendorNotifDrawer(true);};
 document.querySelectorAll('#mobile-workspace-panel a[href="#vendor-notifications"]').forEach(function(link){link.onclick=function(e){e.preventDefault();if(typeof window.toggleVendorNotifDrawer==='function')window.toggleVendorNotifDrawer(true);};});
 var menu=document.getElementById('mobile-workspace-menu'),panel=document.getElementById('mobile-workspace-panel');
 if(menu&&panel){menu.onclick=function(e){e.preventDefault();var open=panel.classList.toggle('open');menu.setAttribute('aria-expanded',String(open));};}
}
async function load(){
 var target=document.getElementById('vendor-workspace-container');
 if(!target){console.error('[Vendor Workspace] Missing vendor-workspace-container');return;}
 /* Render a built-in shell first so the vendor navigation is never blank while components load. */
 target.innerHTML=[fallbackSidebar(),fallbackNavbar(),fallbackNotifications()].join('');
 document.body.classList.add('customer-workspace-page','vendor-workspace-page');
 build();
 try{
  var files=['vendor-sidebar.html','vendor-navbar.html','vendor-notifications.html'];
  var responses=await Promise.all(files.map(function(file){return fetch(componentUrl(file),{cache:'no-store',credentials:'same-origin'});}));
  if(responses.every(function(r){return r.ok;})){
   var html=await Promise.all(responses.map(function(r){return r.text();}));
   if(html.length===3 && html.every(Boolean)){
    target.innerHTML=html.join('');
    build();
   }
  }
 }catch(e){console.warn('[Vendor Workspace] Shared component fetch failed; keeping built-in navigation.',e);}
 var notificationScript=document.createElement('script');
 notificationScript.src=new URL('../../js/vendor/vendor-notifications.js',document.baseURI).href+'?v=20260922';
 notificationScript.defer=false;
 document.body.appendChild(notificationScript);
}
window.vendorWorkspaceReady=load();
})();