"""Production entrypoint with the independent period-display UI layer."""

import wsgi as base

app = base.app


def _inject_period_display(response):
    # Only touch the main HTML document. API/JSON responses remain untouched.
    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type:
        return response
    try:
        body = response.get_data(as_text=True)
        marker = "</body>"
        script = '<script src="/static/period-display.js?v=1" defer></script>'
        if script not in body and marker in body:
            body = body.replace(marker, script + marker, 1)
            response.set_data(body)
    except Exception:
        # Never prevent the application from serving the page because the
        # optional display enhancement failed.
        pass
    return response


app.after_request(_inject_period_display)
