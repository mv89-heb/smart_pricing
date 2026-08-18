"""Production entrypoint with optional period-report UI injection."""

import wsgi as base

app = base.app


def _inject_period_report(response):
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return response
    try:
        body = response.get_data(as_text=True)
        marker = "</body>"
        script = '<script src="/static/period-report-loader.js?v=1" defer></script>'
        if script not in body and marker in body:
            body = body.replace(marker, script + marker, 1)
            response.set_data(body)
            response.headers["Cache-Control"] = "no-store, max-age=0"
    except Exception:
        pass
    return response


app.after_request(_inject_period_report)
