(function(){
'use strict';
var titles={
 'dashboard.html':'Dashboard',
 'manage-orders.html':'Manage Orders',
 'update-menu.html':'Update Menu',
 'morning-survey.html':'Morning Survey',
 'sales-analytics.html':'Sales Analytics',
 'workers.html':'Workers'
};
function pageName(){return (decodeURIComponent(location.pathname).replace(/\\/g,'/').split('/').pop()||'dashboard.html').toLowerCase();}
function userInfo(){try{return JSON.parse(sessionStorage.getItem('foodCourtUser')||'{}')}catch(e){return{}}}
function componentUrl(file){return new URL('../../components/'+file,document.baseURI).href}
function build(){
 document.body.classList.add('customer-workspace-page','vendor-workspace-page');
 var page=pageName(),u=userInfo(),name=u.full_name||u.name||'Vendor',shop=u.shop_name||u.shop||'Vendor',initial=(String(name).trim().charAt(0)||'V').toUpperCase();
 var t=document.getElementById('vendor-workspace-page-title');if(t)t.textContent=titles[page]||'Vendor Workspace';
 var s=document.getElementById('vendor-sidebar-shop-name');if(s)s.textContent=shop;
 var st=document.getElementById('vendor-sidebar-user-type');if(st)st.textContent='Vendor';
 var role=document.getElementById('vendor-workspace-role');if(role)role.textContent=shop+' Vendor';
 ['vendor-sidebar-avatar','vendor-top-avatar'].forEach(function(id){var e=document.getElementById(id);if(e)e.textContent=initial});
 document.querySelectorAll('[data-vendor-link]').forEach(function(a){a.classList.toggle('active',a.getAttribute('data-vendor-link')===page)});
 var top=document.getElementById('vendor-top-avatar');
 if(top){top.title=shop+' Vendor';top.style.cursor='default'}
 var logout=document.getElementById('vendor-workspace-logout');
 if(logout)logout.addEventListener('click',function(){if(typeof handleVendorLogout==='function')handleVendorLogout();});
 var notify=document.getElementById('vendor-sidebar-notifications');
 if(notify)notify.addEventListener('click',function(e){e.preventDefault();if(typeof toggleVendorNotifDrawer==='function')toggleVendorNotifDrawer(true)});
 var menu=document.getElementById('mobile-workspace-menu'),panel=document.getElementById('mobile-workspace-panel');
 if(menu&&panel){
  var close=function(){panel.classList.remove('open');menu.setAttribute('aria-expanded','false')};
  menu.addEventListener('click',function(){var open=panel.classList.toggle('open');menu.setAttribute('aria-expanded',String(open))});
  panel.querySelectorAll('a').forEach(function(a){a.addEventListener('click',function(e){if(a.getAttribute('href')==='#vendor-notifications'){e.preventDefault();if(typeof toggleVendorNotifDrawer==='function')toggleVendorNotifDrawer(true)}close()})});
  document.addEventListener('click',function(e){if(!menu.contains(e.target)&&!panel.contains(e.target))close()});
 }
}
async function load(){
 var target=document.getElementById('vendor-workspace-container');if(!target)return;
 try{
  var responses=await Promise.all([
   fetch(componentUrl('vendor-sidebar.html'),{cache:'force-cache'}),
   fetch(componentUrl('vendor-navbar.html'),{cache:'force-cache'}),
   fetch(componentUrl('vendor-notifications.html'),{cache:'force-cache'})
  ]);
  if(responses.some(function(r){return !r.ok}))throw new Error('Vendor workspace components failed to load');
  var html=await Promise.all(responses.map(function(r){return r.text()}));
  target.innerHTML=html[0]+html[1]+html[2];
  build();
  var notificationScript=document.createElement('script'); notificationScript.src=new URL('../../js/vendor/vendor-notifications.js',document.baseURI).href; notificationScript.defer=false; document.body.appendChild(notificationScript);
 }catch(e){console.error('[Vendor Workspace]',e);target.innerHTML='<div class="p-4 text-center text-rose-600 text-xs font-bold">Unable to load vendor navigation.</div>'}
}
window.vendorWorkspaceReady=load();
})();