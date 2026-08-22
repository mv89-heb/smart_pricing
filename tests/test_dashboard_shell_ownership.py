from pathlib import Path


def test_dashboard_does_not_duplicate_global_shell_navigation_or_controls():
    html = Path("static/dashboard.html").read_text(encoding="utf-8")

    # Navigation, theme, and fullscreen belong to module-shell.js.
    assert 'href="/static/dashboard.html"' not in html
    assert 'href="/periodic-report"' not in html
    assert 'onclick="toggleDark()"' not in html
    assert 'onclick="toggleFullscreen()"' not in html
    assert 'function toggleDark(' not in html
    assert 'function toggleFullscreen(' not in html


def test_dashboard_keeps_only_dashboard_specific_actions():
    html = Path("static/dashboard.html").read_text(encoding="utf-8")

    assert 'onclick="compare()"' in html
    assert 'onclick="lockPeriod()"' in html
    assert 'onclick="unlockPeriod()"' in html
    assert '/api/report/period?' in html
