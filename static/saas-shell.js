(() => {'use strict';
const $=id=>document.getElementById(id);
function updateThemeIcon(){const i=$('theme-toggle')?.querySelector('i');if(i)i.className=document.documentElement.classList.contains('dark')?'fa-solid fa-sun':'fa-solid fa-moon'}
async function init(){const saved=localStorage.getItem('theme');if(saved==='dark')document.documentElement.classList.add('dark');$('theme-toggle')?.addEventListener('click',()=>{const dark=document.documentElement.classList.toggle('dark');localStorage.setItem('theme',dark?'dark':'light');updateThemeIcon()});$('fullscreen-toggle')?.addEventListener('click',()=>{if(!document.fullscreenElement)document.documentElement.requestFullscreen?.().catch(()=>{});else document.exitFullscreen?.()});$('sidebar-toggle')?.addEventListener('click',()=>$('app-sidebar')?.classList.toggle('open'));updateThemeIcon();}
window.saasToast=(message)=>{const c=$('toast-container');if(!c)return;const n=document.createElement('div');n.className='saas-toast';n.textContent=message;c.appendChild(n);setTimeout(()=>n.remove(),3200)};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();