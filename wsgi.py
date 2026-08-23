from app import app


class UXInjectionMiddleware:
    """Inject a presentation-only navigation shell into HTML responses."""

    UX_HTML = r'''<style>
:root{--ux-primary:#4f46e5;--ux-primary-2:#6366f1;--ux-ink:#0f172a;--ux-muted:#64748b;--ux-border:#e2e8f0}
#ux-shell{position:fixed;inset:0 0 0 auto;width:248px;background:rgba(255,255,255,.97);border-left:1px solid var(--ux-border);box-shadow:0 10px 40px rgba(15,23,42,.08);z-index:40;display:flex;flex-direction:column;direction:rtl;font-family:Heebo,system-ui,sans-serif}
#ux-shell .ux-brand{padding:22px 18px 18px;border-bottom:1px solid var(--ux-border)}
#ux-shell .ux-brand-row{display:flex;align-items:center;gap:11px}
#ux-shell .ux-logo{width:42px;height:42px;border-radius:12px;background:linear-gradient(135deg,var(--ux-primary-2),var(--ux-primary));color:#fff;display:grid;place-items:center;box-shadow:0 8px 18px rgba(79,70,229,.25)}
#ux-shell .ux-title{font-size:16px;font-weight:800;color:var(--ux-ink);line-height:1.15}
#ux-shell .ux-subtitle{font-size:11px;color:var(--ux-muted);margin-top:3px}
#ux-shell .ux-user{margin-top:14px;padding:9px 10px;background:#f8fafc;border:1px solid var(--ux-border);border-radius:10px;font-size:12px;color:#475569;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#ux-shell .ux-section{padding:16px 12px 5px;color:#94a3b8;font-size:10px;font-weight:800;letter-spacing:.04em}
#ux-shell .ux-nav{padding:0 10px;display:flex;flex-direction:column;gap:4px}
#ux-shell .ux-nav button,#ux-shell .ux-nav a{appearance:none;border:0;background:transparent;width:100%;text-decoration:none;color:#475569;padding:11px 12px;border-radius:10px;display:flex;align-items:center;gap:10px;font:600 13px Heebo,system-ui,sans-serif;cursor:pointer;text-align:right;transition:.16s ease}
#ux-shell .ux-nav button:hover,#ux-shell .ux-nav a:hover{background:#f1f5f9;color:var(--ux-primary)}
#ux-shell .ux-nav .active{background:#eef2ff;color:#4338ca;box-shadow:inset -3px 0 0 var(--ux-primary)}
#ux-shell .ux-nav i{width:20px;text-align:center;font-size:15px;color:#94a3b8}
#ux-shell .ux-nav .active i,#ux-shell .ux-nav button:hover i{color:var(--ux-primary)}
#ux-shell .ux-spacer{flex:1}
#ux-shell .ux-footer{padding:12px;border-top:1px solid var(--ux-border)}
#ux-shell .ux-logout{color:#dc2626!important;background:#fff1f2!important}
#ux-shell .ux-logout:hover{background:#ffe4e6!important}
#ux-mobile-nav{display:none}
#ux-shell .ux-admin{display:none}
body.ux-ready .app-ui>header{display:none!important}
body.ux-ready .app-ui>main{margin-left:0!important;margin-right:0!important;max-width:none!important;padding:24px 276px 32px 28px!important}
body.ux-ready .app-ui>main>div{max-width:1500px;margin:0 auto}
body.ux-ready #right-panel>div{top:24px!important;height:calc(100vh - 56px)!important}
body.ux-ready #left-panel,body.ux-ready #right-panel{min-width:0}
body.ux-ready .bg-white.rounded-2xl{box-shadow:0 8px 30px rgba(15,23,42,.045)}
@media(max-width:900px){
 #ux-shell{display:none}
 #ux-mobile-nav{position:fixed;display:flex;left:10px;right:10px;bottom:10px;height:62px;background:rgba(255,255,255,.97);border:1px solid var(--ux-border);box-shadow:0 10px 35px rgba(15,23,42,.15);border-radius:18px;z-index:45;direction:rtl;padding:5px;gap:3px}
 #ux-mobile-nav button,#ux-mobile-nav a{flex:1;border:0;background:transparent;text-decoration:none;color:#64748b;border-radius:13px;font:600 10px Heebo,system-ui,sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;cursor:pointer}
 #ux-mobile-nav i{font-size:17px}
 #ux-mobile-nav .active{background:#eef2ff;color:#4338ca}
 body.ux-ready .app-ui>main{padding:16px 12px 90px!important}
 body.ux-ready #right-panel>div{height:auto!important;position:static!important}
 body.ux-ready #right-panel{order:2}
 body.ux-ready #left-panel{order:1}
}
</style>
<nav id="ux-shell" aria-label="ניווט ראשי">
  <div class="ux-brand">
    <div class="ux-brand-row"><div class="ux-logo"><i class="fa-solid fa-chart-line"></i></div><div><div class="ux-title">Smart Pricing</div><div class="ux-subtitle">ניהול חיובים חכם</div></div></div>
    <div id="ux-user" class="ux-user">טוען משתמש...</div>
  </div>
  <div class="ux-section">ניווט</div>
  <div class="ux-nav">
    <button id="ux-daily" class="active" onclick="UX.goDaily()"><i class="fa-solid fa-clipboard-list"></i><span>דיווח יומי</span></button>
    <button id="ux-pricing" onclick="UX.goPricing()"><i class="fa-solid fa-tags"></i><span>מחירון</span></button>
    <button id="ux-dashboard" onclick="UX.dashboard()"><i class="fa-solid fa-chart-pie"></i><span>אנליטיקה ודאשבורד</span></button>
    <button id="ux-templates" onclick="UX.templates()"><i class="fa-solid fa-layer-group"></i><span>תבניות וסלים</span></button>
  </div>
  <div class="ux-section ux-admin-section">ניהול</div>
  <div class="ux-nav">
    <button id="ux-admin" class="ux-admin" onclick="UX.admin()"><i class="fa-solid fa-gear"></i><span>ניהול מערכת</span></button>
  </div>
  <div class="ux-spacer"></div>
  <div class="ux-footer"><div class="ux-nav"><a class="ux-logout" href="/logout"><i class="fa-solid fa-right-from-bracket"></i><span>יציאה מהמערכת</span></a></div></div>
</nav>
<nav id="ux-mobile-nav" aria-label="ניווט מהיר">
  <button id="uxm-daily" class="active" onclick="UX.goDaily()"><i class="fa-solid fa-clipboard-list"></i><span>יומי</span></button>
  <button id="uxm-pricing" onclick="UX.goPricing()"><i class="fa-solid fa-tags"></i><span>מחירון</span></button>
  <button id="uxm-dashboard" onclick="UX.dashboard()"><i class="fa-solid fa-chart-pie"></i><span>דאשבורד</span></button>
  <button id="uxm-admin" class="ux-admin" onclick="UX.admin()"><i class="fa-solid fa-gear"></i><span>ניהול</span></button>
  <a href="/logout"><i class="fa-solid fa-right-from-bracket"></i><span>יציאה</span></a>
</nav>
<script>
(function(){
  const UX={
    active(name){document.querySelectorAll('#ux-shell .ux-nav button,#ux-mobile-nav button').forEach(b=>b.classList.remove('active'));['ux-'+name,'uxm-'+name].forEach(id=>{const e=document.getElementById(id);if(e)e.classList.add('active')});},
    goDaily(){this.active('daily');const el=document.getElementById('left-panel');if(el)el.scrollIntoView({behavior:'smooth',block:'start'});},
    goPricing(){this.active('pricing');const el=document.getElementById('right-panel');if(el)el.scrollIntoView({behavior:'smooth',block:'start'});},
    dashboard(){this.active('dashboard');if(typeof openDashboard==='function')openDashboard();},
    templates(){this.active('templates');if(typeof openTemplatesModal==='function')openTemplatesModal();},
    admin(){this.active('admin');if(typeof openAdminPanel==='function')openAdminPanel();}
  };
  window.UX=UX;
  function syncUser(){
    const b=document.getElementById('user-badge'),u=document.getElementById('ux-user');
    if(b&&u)u.textContent=b.textContent;
    const originalAdmin=document.getElementById('admin-panel-btn');
    const isAdmin=originalAdmin && !originalAdmin.classList.contains('hidden');
    document.querySelectorAll('.ux-admin').forEach(e=>e.style.display=isAdmin?'flex':'none');
    document.querySelectorAll('.ux-admin-section').forEach(e=>e.style.display=isAdmin?'block':'none');
  }
  window.addEventListener('load',function(){document.body.classList.add('ux-ready');syncUser();setTimeout(syncUser,500);setTimeout(syncUser,1500);});
  const observer=new MutationObserver(syncUser);observer.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['class']});
})();
</script>'''

    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        captured = {}

        def capture(status, headers, exc_info=None):
            captured['status'] = status
            captured['headers'] = headers
            captured['exc_info'] = exc_info
            return lambda data: None

        body_parts = self.application(environ, capture)
        body = b''.join(body_parts)
        for part in body_parts:
            try:
                part.close()
            except AttributeError:
                pass

        headers = captured.get('headers', [])
        content_type = next((v for k, v in headers if k.lower() == 'content-type'), '')
        status = captured.get('status', '200 OK')

        if 'text/html' in content_type and b'</body>' in body and environ.get('REQUEST_METHOD') != 'HEAD':
            body = body.replace(b'</body>', self.UX_HTML.encode('utf-8') + b'</body>', 1)
            headers = [(k, v) for k, v in headers if k.lower() != 'content-length']
            headers.append(('Content-Length', str(len(body))))

        start_response(status, headers, captured.get('exc_info'))
        return [body]


app = UXInjectionMiddleware(app)
__all__ = ["app"]
