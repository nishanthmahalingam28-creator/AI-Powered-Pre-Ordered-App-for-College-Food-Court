(function(){
'use strict';

var links=[
  ['dashboard.html','Dashboard','fa-solid fa-grid-2'],
  ['menu.html','Order Food','fa-solid fa-utensils'],
  ['preorder.html','My Cart','fa-solid fa-basket-shopping'],
  ['orders.html','My Orders','fa-solid fa-receipt'],
  ['morning-survey.html','Morning Survey','fa-solid fa-sun'],
  ['expenses.html','Expenses','fa-solid fa-wallet'],
  ['income.html','Income','fa-solid fa-coins'],
  ['budgets.html','Budgets & Goals','fa-solid fa-chart-pie'],
  ['analytics.html','Analytics','fa-solid fa-chart-line'],
  ['assistant.html','AI Assistant','fa-solid fa-wand-magic-sparkles'],
  ['profile.html','Profile','fa-solid fa-user']
];

var titles={
 'dashboard.html':'Dashboard','menu.html':'Order Food','preorder.html':'My Cart','orders.html':'My Orders',
 'morning-survey.html':'Morning Survey','expenses.html':'Expenses','income.html':'Income',
 'budgets.html':'Budgets & Goals','analytics.html':'Analytics','assistant.html':'AI Assistant',
 'profile.html':'Profile'
};

function pageName(){
 var p=decodeURIComponent(location.pathname).replace(/\\/g,'/');
 return (p.split('/').pop()||'dashboard.html').toLowerCase();
}
function userInfo(){
 try{return JSON.parse(sessionStorage.getItem('foodCourtUser')||'{}')}catch(e){return {}}
}
function build(){
 var existingSidebar=document.querySelector('.student-sidebar');
 var existingHeader=document.querySelector('.student-topbar');
 if(existingSidebar) existingSidebar.remove();
 if(existingHeader) existingHeader.remove();

 var oldNav=document.getElementById('navbar-container');
 if(oldNav) oldNav.style.display='none';
 var oldFooter=document.getElementById('footer-container');
 if(oldFooter) oldFooter.style.display='none';

 var page=pageName(), user=userInfo();
 var name=user.full_name||user.name||'Student';
 var role=(user.customer_type||user.user_type||user.role||'Student');
 var initial=(name.trim().charAt(0)||'S').toUpperCase();

 var aside=document.createElement('aside');
 aside.className='customer-workspace-sidebar';
 aside.innerHTML=
  '<div class="customer-workspace-brand"><div class="customer-workspace-brand-mark"><i class="fa-solid fa-utensils"></i></div><div><strong>KPRIET</strong><span>Smart Food Court</span></div></div>'+
  '<nav class="customer-workspace-nav">'+
  links.map(function(item){return '<a href="'+item[0]+'" class="'+(item[0]===page?'active':'')+'"><i class="'+item[2]+'"></i><span>'+item[1]+'</span></a>';}).join('')+
  '</nav>'+
  '<div class="customer-workspace-user"><div class="customer-workspace-avatar">'+initial+'</div><div class="min-w-0"><strong>'+name+'</strong><span>'+role+'</span></div><button class="customer-workspace-logout" onclick="if(typeof handleCustomerLogout==='function'){handleCustomerLogout();}" title="Logout"><i class="fa-solid fa-arrow-right-from-bracket"></i></button></div>';

 var header=document.createElement('header');
 header.className='customer-workspace-header';
 header.innerHTML='<div><span class="customer-workspace-header-label">Student workspace</span><h2>'+ (titles[page]||'Student Workspace') +'</h2></div>'+
  '<div class="customer-workspace-actions"><button class="customer-workspace-notification notification-bell-trigger" title="Notifications"><i class="fa-regular fa-bell"></i><span class="notification-badge hidden">0</span></button><span class="customer-workspace-role" id="topbar-customer-type">'+role+'</span><div class="customer-workspace-top-avatar" id="topbar-avatar">'+initial+'</div></div>';

 document.body.classList.add('customer-workspace-page');
 document.body.prepend(aside);
 document.body.insertBefore(header,document.body.firstChild.nextSibling);

 var main=document.querySelector('main');
 if(main) main.classList.add('customer-workspace-main');

 document.querySelectorAll('a[href="dashboard.html"],a[href="menu.html"],a[href="orders.html"],a[href="preorder.html"],a[href="morning-survey.html"],a[href="expenses.html"],a[href="income.html"],a[href="budgets.html"],a[href="analytics.html"],a[href="assistant.html"],a[href="profile.html"]').forEach(function(a){
   a.addEventListener('click',function(){document.body.classList.add('customer-workspace-navigating');});
 });
}
if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',build); else build();
})();