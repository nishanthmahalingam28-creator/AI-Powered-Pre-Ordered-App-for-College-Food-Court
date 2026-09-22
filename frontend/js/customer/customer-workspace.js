(function(){'use strict';
var titles={'dashboard.html':'Dashboard','menu.html':'Order Food','preorder.html':'My Cart','orders.html':'My Orders','morning-survey.html':'Morning Survey','expenses.html':'Expenses','budgets.html':'Food Budget','analytics.html':'Analytics','assistant.html':'AI Assistant','profile.html':'Profile','income.html':'Income'};
function pageName(){var p=decodeURIComponent(location.pathname).replace(/\\/g,'/');return(p.split('/').pop()||'dashboard.html').toLowerCase()}
function userInfo(){try{return JSON.parse(sessionStorage.getItem('foodCourtUser')||'{}')}catch(e){return{}}}
function componentUrl(){return new URL('../../components/customer-workspace.html',document.baseURI).href}
function build(){
  document.body.classList.add('customer-workspace-page');
  var page=pageName(),u=userInfo(),name=u.full_name||u.name||'Student',role=u.customer_type||u.user_type||u.role||'Student',initial=(String(name).trim().charAt(0)||'S').toUpperCase();
  var t=document.getElementById('customer-workspace-page-title');if(t)t.textContent=titles[page]||'Customer Workspace';
  var ne=document.getElementById('sidebar-user-name');if(ne)ne.textContent=name;
  var re=document.getElementById('sidebar-user-type');if(re)re.textContent=role;
  var tr=document.getElementById('topbar-customer-type');if(tr)tr.textContent=role;
  ['sidebar-avatar','topbar-avatar'].forEach(function(id){var e=document.getElementById(id);if(e)e.textContent=initial});
  var topAvatar=document.getElementById('topbar-avatar');
  if(topAvatar){topAvatar.style.cursor='pointer';topAvatar.setAttribute('role','button');topAvatar.setAttribute('tabindex','0');topAvatar.setAttribute('aria-label','Open profile');
    var openProfile=function(){location.href='profile.html'};topAvatar.addEventListener('click',openProfile);topAvatar.addEventListener('keydown',function(event){if(event.key==='Enter'||event.key===' '){event.preventDefault();openProfile()}})
  }
  document.querySelectorAll('[data-workspace-link]').forEach(function(a){a.classList.toggle('active',a.getAttribute('data-workspace-link')===page)});
  var m=document.querySelector('main');if(m)m.classList.add('customer-workspace-main');
  var l=document.getElementById('customer-workspace-logout');if(l)l.addEventListener('click',function(){if(typeof handleCustomerLogout==='function')handleCustomerLogout();else{try{sessionStorage.removeItem('foodCourtUser')}catch(e){}location.href='../../index.html'}});
  var menu=document.getElementById('mobile-workspace-menu'),panel=document.getElementById('mobile-workspace-panel');
  if(menu&&panel){
    var mobile=function(){return window.matchMedia('(max-width: 640px)').matches};
    var close=function(){panel.classList.remove('open');menu.setAttribute('aria-expanded','false')};
    menu.addEventListener('click',function(){if(!mobile()){close();return}var open=panel.classList.toggle('open');menu.setAttribute('aria-expanded',String(open))});
    panel.querySelectorAll('a').forEach(function(a){a.addEventListener('click',close)});
    document.addEventListener('click',function(e){if(!menu.contains(e.target)&&!panel.contains(e.target))close()});
    window.addEventListener('resize',function(){if(!mobile())close()});
  }
}
async function loadWorkspace(){
  var target=document.getElementById('customer-workspace-container');
  if(!target)return;
  try{
    var response=await fetch(componentUrl(),{cache:'force-cache'});
    if(!response.ok)throw new Error('Workspace component HTTP '+response.status);
    target.innerHTML=await response.text();
    build();
  }catch(error){
    console.error('[Customer Workspace] Failed to load shared workspace:',error);
    target.innerHTML='<div class="p-4 text-center text-rose-600 text-xs font-bold">Unable to load customer navigation.</div>';
  }
}
window.customerWorkspaceReady=loadWorkspace();
if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',function(){window.customerWorkspaceReady});}else{window.customerWorkspaceReady}
})();