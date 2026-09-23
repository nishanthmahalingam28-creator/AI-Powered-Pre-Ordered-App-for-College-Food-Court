(function () {
'use strict';
function esc(v){return String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');}
function base(){return (window.FOOD_COURT_API_BASE||(typeof window.getApiUrl==='function'?window.getApiUrl(''):'/api')).replace(/\/+$/,'');}
function message(grid,title,detail,retry){if(!grid)return;grid.innerHTML='<div class="col-span-full bg-white rounded-2xl border border-slate-200 p-6 text-center"><i class="fa-solid fa-circle-info text-teal-600 text-xl mb-2"></i><p class="text-sm font-bold text-slate-700">'+esc(title)+'</p><p class="text-xs text-slate-400 mt-1">'+esc(detail||'')+'</p>'+(retry?'<button id="ai-engine-retry" class="mt-3 text-xs font-bold text-teal-700 hover:underline">Try again →</button>':'')+'</div>';var b=document.getElementById('ai-engine-retry');if(b)b.onclick=load;}
function loading(g){if(g)g.innerHTML='<div class="col-span-full bg-white rounded-2xl border border-slate-200 p-6 text-center"><i class="fa-solid fa-wand-magic-sparkles text-teal-600 text-xl mb-2"></i><p class="text-sm font-bold text-slate-700">Loading smart recommendations...</p><p class="text-xs text-slate-400 mt-1">Getting today\'s available food for you.</p></div>';}
async function req(url,ms){var c=new AbortController(),t=setTimeout(function(){c.abort()},ms);try{return await fetch(url,{credentials:'include',cache:'no-store',signal:c.signal});}finally{clearTimeout(t);}}
async function addAIItem(item,btn){
  if(!item||!item.id||!btn)return;
  var original=btn.innerHTML;
  btn.disabled=true;
  btn.textContent='Adding...';
  var b=base();
  try{
    var r=await fetch(b+'/cart',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      credentials:'include',
      body:JSON.stringify({item_id:Number(item.id),quantity:1})
    });
    var d=await r.json().catch(function(){return{};});
    if(r.status===401||r.status===403){
      alert('Please log in to add items to your cart.');
      btn.innerHTML=original;
      btn.disabled=false;
      return;
    }
    if(r.status===409&&d.conflict){
      var ok=confirm((d.message||'Your cart contains items from another stall.')+'\\n\\nWould you like to clear the existing cart and add this item?');
      if(!ok){btn.innerHTML=original;btn.disabled=false;return;}
      r=await fetch(b+'/cart',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        credentials:'include',
        body:JSON.stringify({item_id:Number(item.id),quantity:1,clear_conflicting_stall:true})
      });
      d=await r.json().catch(function(){return{};});
    }
    if(r.ok&&d.success){
      btn.innerHTML='<i class="fa-solid fa-check mr-1"></i> Added';
      btn.classList.add('bg-emerald-600');
      var badge=document.getElementById('cart-count');
      if(badge&&d.summary)badge.textContent=String(d.summary.total_items||0);
      setTimeout(function(){btn.innerHTML=original;btn.classList.remove('bg-emerald-600');btn.disabled=false;},1000);
    }else{
      alert((d&&d.message)||'Unable to add item to cart. Please try again.');
      btn.innerHTML=original;
      btn.disabled=false;
    }
  }catch(e){
    console.error('AI recommendation add-to-cart error:',e);
    alert('Could not connect to the server to update cart.');
    btn.innerHTML=original;
    btn.disabled=false;
  }
}
function render(data,g){var a=Array.isArray(data.recommendations)?data.recommendations:[];if(!a.length){message(g,'No recommendations available right now.','There are no available menu items at the moment.',true);return;}var h=document.getElementById('ai-section-heading');if(h&&data.heading)h.textContent=data.heading;g.innerHTML=a.map(function(x){var id=Number(x.id||x.item_id||0),p=Number(x.price||0),n=esc(x.name||x.item_name||'Food item'),s=esc(x.shop_name||'Food Court'),d=esc(x.description||x.category||'Available now'),r=esc(x.reason||x.ai_badge||'Available now');return '<div class="bg-white rounded-2xl p-5 border border-slate-100 shadow-sm flex flex-col justify-between"><div><div class="flex items-center justify-between gap-2 mb-2"><span class="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase bg-teal-50 text-teal-700">'+s+'</span><span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-800">'+r+'</span></div><h3 class="font-bold text-slate-800 text-base">'+n+'</h3><p class="text-xs text-slate-500 mt-1">'+d+'</p></div><div class="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between"><span class="text-base font-black text-slate-900">₹'+p.toFixed(2)+'</span><button type="button" class="bg-teal-700 text-white font-bold text-xs px-3.5 py-2 rounded-xl" data-ai-index="'+i+'" data-ai-id="'+id+'">Add</button></div></div>';}).join('');g.querySelectorAll('[data-ai-index]').forEach(function(b){b.onclick=function(){var i=Number(b.getAttribute('data-ai-index'));addAIItem(a[i],b);};});}
async function load(){var g=document.getElementById('ai-recommendations-grid');if(!g)return;loading(g);var b=base(),last=null;for(var i=0;i<2;i++){try{var r=await req(i===0?b+'/ai/recommendations?limit=6':b+'/recommendations?limit=6',i===0?20000:10000);var d=await r.json().catch(function(){return{};});if(r.ok&&d.success&&Array.isArray(d.recommendations)){render(d,g);return;}last=new Error((d&&d.message)||('HTTP '+r.status));}catch(e){last=e;}}message(g,'AI recommendations could not be loaded.',last&&last.name==='AbortError'?'The food service took too long to respond.':'The recommendation service could not return the menu.',true);}
function start(){load();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
window.reloadCustomerAI=load;
})();