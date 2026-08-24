from flask import request

from app import app, db, DailyEntry, Product, ActivityLog, is_viewer
from performance import ensure_indexes
from period_report import register_period_report
from price_sync import register_price_sync
from product_identity import register_product_identity

with app.app_context():
    ensure_indexes(db)

register_period_report(app, db, DailyEntry, Product, ActivityLog)
register_price_sync(app, db, Product, DailyEntry, is_viewer)
register_product_identity(app, db, Product, DailyEntry)

@app.after_request
def add_global_navigation(response):
    content_type=response.headers.get('Content-Type','')
    # לא מזריקים תפריט (עם קישורי דשבורד/יציאה) למסך ההתחברות - המשתמש עוד לא מחובר
    if request.endpoint == 'login':
        return response
    if 'text/html' in content_type and response.status_code < 400:
        response.headers['Link']='</static/navigation.css>; rel=preload; as=style, </static/ux-refresh.css>; rel=preload; as=style, </static/navigation.js>; rel=preload; as=script'
        html=response.get_data(as_text=True)
        if 'navigation.css' not in html:
            html=html.replace('</head>','<link rel="stylesheet" href="/static/navigation.css"><link rel="stylesheet" href="/static/ux-refresh.css"></head>',1)
        if 'navigation.js' not in html:
            html=html.replace('</body>','<script src="/static/navigation.js" defer></script></body>',1)
        response.set_data(html)
    return response

__all__=['app']
