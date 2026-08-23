from app import app, db, DailyEntry
from performance import ensure_indexes
from period_report import register_period_report

# One-time, idempotent startup optimization for the existing schema.
with app.app_context():
    ensure_indexes(db)

register_period_report(app, db, DailyEntry)

# Presentation-only navigation injection. It adds two static assets to HTML
# responses without reading or rewriting the response body, so it has minimal
# impact on data/API performance and leaves application logic untouched.
@app.after_request
def add_global_navigation(response):
    content_type = response.headers.get('Content-Type', '')
    if 'text/html' in content_type and response.status_code < 400:
        response.headers['Link'] = '</static/navigation.css>; rel=preload; as=style, </static/navigation.js>; rel=preload; as=script'
        response.set_data(
            response.get_data(as_text=True).replace(
                '</head>',
                '<link rel="stylesheet" href="/static/navigation.css"></head>',
                1,
            ).replace(
                '</body>',
                '<script src="/static/navigation.js" defer></script></body>',
                1,
            )
        )
    return response

__all__ = ["app"]
