(function(){
  'use strict';
  if (document.body.classList.contains('invoice-mode')) return;
  if (document.getElementById('sp-sidebar')) return;
  const path=location.pathname;
  const isDaily=path==='/daily' || path==='/';
  const items=[
    {label:'דוח לפי תקופה',icon:'fa-chart-column',href:'/',key:'period'},
    {label:'דיווח יומי',icon:'fa-pen-to-square',href:'/daily',key:'daily'},
    {label:'מחירון',icon:'fa-tags',action:'price',key:'price'},
    {label:'אנליטיקה ודאשבורד',icon:'fa-chart-pie',action:'dashboard',key:'dashboard'},
    {label:'תבניות וסלים',icon:'fa-layer-group',action:'templates',key:'templates'}
  ];
  const active=path==='/'?'period':path==='/daily'?'daily':path.includes('period-report')?'period':'';
  const el=(tag,cls,html)=>{const e=document.createElement(tag);e.className=cls||'';e.innerHTML=html||'';return e};
  const sidebar=el('aside','sp-sidebar');sidebar.id='sp-sidebar';
  sidebar.innerHTML='<div class="sp-brand"><div class="sp-brand-title"><i class="fa-solid fa-chart-line"></i> Smart Pricing</div><div class="sp-brand-sub">ניהול חיובים חכם</div></div>';
  const nav=el('nav','sp-nav');
  items.forEach(it=>{const a=el(it.href?'a':'button',''+(it.key===active?'active':''),`<i class="fa-solid ${it.icon}"></i><span>${it.label}</span>`);if(it.href)a.href=it.href;else a.type='button';a.dataset.navAction=it.action||'';nav.appendChild(a);});
  const divider=el('div','sp-divider');nav.appendChild(divider);
  const admin=el('button','','<i class="fa-solid fa-gear"></i><span>הגדרות וניהול</span>');admin.type='button';admin.dataset.navAction='admin';nav.appendChild(admin);sidebar.appendChild(nav);
  const footer=el('div','sp-footer');footer.innerHTML='<a href="/logout" style="color:#fca5a5"><i class="fa-solid fa-right-from-bracket"></i><span>יציאה</span></a>';sidebar.appendChild(footer);document.body.prepend(sidebar);
  const mobile=el('nav','sp-mobile-nav');
  items.slice(0,5).forEach(it=>{const b=el('button',it.key===active?'active':'',`<i class="fa-solid ${it.icon}"></i><span>${it.label.split(' ')[0]}</span>`);b.type='button';b.dataset.href=it.href||'';b.dataset.navAction=it.action||'';mobile.appendChild(b);});document.body.appendChild(mobile);
  const shift=()=>{const app=document.querySelector('.app-ui');if(app&&!app.classList.contains('sp-content-shift'))app.classList.add('sp-content-shift');const main=document.querySelector('main');if(main&&window.innerWidth>1023)main.style.maxWidth='none';};
  shift();window.addEventListener('resize',shift);
  function run(action){
    if(action==='price'){if(!isDaily){location.href='/daily#price-list';return;}const p=document.getElementById('right-panel');if(p)p.scrollIntoView({behavior:'smooth',block:'start'});return;}
    if(action==='dashboard'){if(!isDaily){location.href='/daily#dashboard';return;}if(typeof window.openDashboard==='function')window.openDashboard();return;}
    if(action==='templates'){if(!isDaily){location.href='/daily#templates';return;}if(typeof window.openTemplatesModal==='function')window.openTemplatesModal();return;}
    if(action==='admin'){if(!isDaily){location.href='/daily#admin';return;}if(typeof window.openAdminPanel==='function')window.openAdminPanel();return;}
  }
  document.querySelectorAll('[data-nav-action]').forEach(x=>x.addEventListener('click',()=>run(x.dataset.navAction)));
  if(isDaily&&location.hash){setTimeout(()=>{const h=location.hash.slice(1);if(h==='price-list'){document.getElementById('right-panel')?.scrollIntoView({behavior:'smooth'});return;}if(h==='dashboard'&&typeof window.openDashboard==='function')window.openDashboard();if(h==='templates'&&typeof window.openTemplatesModal==='function')window.openTemplatesModal();if(h==='admin'&&typeof window.openAdminPanel==='function')window.openAdminPanel();},250);}
})();
