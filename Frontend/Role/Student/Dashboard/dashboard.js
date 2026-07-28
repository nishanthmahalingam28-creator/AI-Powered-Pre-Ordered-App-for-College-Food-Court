const menu=document.querySelector('#menuGrid');
const cartButton=document.querySelector('#cartBtn');
const drawer=document.querySelector('#cartDrawer');
const overlay=document.querySelector('#overlay');
const closeCart=document.querySelector('#closeCart');
const items=[
  {name:'Masala Dosa',shop:'YPR Restaurant',price:70,cat:'South Indian',icon:'🥞',color:'#f7e3ab'},
  {name:'Paneer Rice Bowl',shop:'Royal Kitchen',price:110,cat:'Meals',icon:'🍛',color:'#edd9c8'},
  {name:'Veg Puff',shop:'Saaral Bakery',price:25,cat:'Snacks',icon:'🥐',color:'#f4dba8'},
  {name:'Cold Coffee',shop:'German Cafe',price:65,cat:'Beverages',icon:'🥤',color:'#d9e9d5'},
  {name:'Mini Meals',shop:'YPR Restaurant',price:95,cat:'Meals',icon:'🍱',color:'#e0e8ba'},
  {name:'Cheese Maggi',shop:'Mario',price:60,cat:'Snacks',icon:'🍜',color:'#f4ddc9'},
  {name:'Filter Coffee',shop:'Ganesh Cafe',price:15,cat:'Beverages',icon:'☕',color:'#d9d5c4'},
  {name:'Idli & Vada',shop:'YPR Restaurant',price:55,cat:'South Indian',icon:'🍽️',color:'#e8e5c2'}
];
let cart=[];let selected='All';let search='';
function render(){const filtered=items.filter(x=>(selected==='All'||x.cat===selected)&&`${x.name} ${x.shop}`.toLowerCase().includes(search));menu.innerHTML=filtered.map((x,i)=>`<article class="dish"><div class="dish-art" style="background:${x.color}"><small>${x.shop}</small><span>${x.icon}</span></div><div class="dish-info"><p>${x.cat}</p><h3>${x.name}</h3><div class="dish-bottom"><strong>₹${x.price}</strong><button class="add" data-index="${items.indexOf(x)}">+</button></div></div></article>`).join('');}
function openCart(show=true){drawer.classList.toggle('open',show);overlay.classList.toggle('visible',show);}
function refreshCart(){const total=cart.reduce((sum,item)=>sum+item.price,0);document.querySelector('#cartCount').textContent=cart.length;document.querySelector('#total').textContent=`₹${total}`;document.querySelector('#checkoutBtn').disabled=!cart.length;document.querySelector('#cartItems').innerHTML=cart.length?cart.map(item=>`<div class="cart-item"><div class="cart-emoji">${item.icon}</div><div><h3>${item.name}</h3><p>${item.shop}</p></div><span class="cart-price">₹${item.price}</span></div>`).join(''):'<p class="empty">Your cart is waiting for something delicious.</p>';}
menu.addEventListener('click',event=>{const index=event.target.dataset.index;if(index===undefined)return;cart.push(items[index]);refreshCart();});
cartButton.onclick=()=>openCart();closeCart.onclick=()=>openCart(false);overlay.onclick=()=>openCart(false);
document.querySelector('#filters').addEventListener('click',event=>{if(!event.target.dataset.category)return;selected=event.target.dataset.category;document.querySelectorAll('.filters button').forEach(button=>button.classList.toggle('active',button===event.target));render();});
document.querySelector('#search').addEventListener('input',event=>{search=event.target.value.toLowerCase();render();});
document.querySelector('#recommendBtn').onclick=()=>{cart.push(items[0],items[6]);refreshCart();openCart();};
document.querySelector('#checkoutBtn').onclick=()=>{document.querySelector('#otp').textContent=Math.floor(100000+Math.random()*900000);document.querySelector('#orderId').textContent=`Order #SC${Date.now().toString().slice(-6)}`;openCart(false);document.querySelector('#confirmation').showModal();cart=[];refreshCart();};
document.querySelector('#doneBtn').onclick=()=>document.querySelector('#confirmation').close();render();refreshCart();
