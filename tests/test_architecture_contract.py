from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_no_application_module_imports_wsgi_as_owner():
    roots=[ROOT/'smartpricing',ROOT/'tests',ROOT/'app.py',ROOT/'api_routes.py',ROOT/'production.py',ROOT/'wsgi_ui.py']
    files=[]
    for root in roots:
        if root.is_dir(): files.extend(root.rglob('*.py'))
        elif root.exists(): files.append(root)
    offenders=[]
    for path in files:
        text=path.read_text(encoding='utf-8')
        if 'from wsgi import' in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, offenders


def test_factory_is_the_single_web_app_constructor():
    source=(ROOT/'smartpricing/app_factory.py').read_text(encoding='utf-8')
    assert 'def create_app()' in source
    assert 'Flask(' in source
    for path in (ROOT/'smartpricing/routes').glob('*.py'):
        assert 'Flask(' not in path.read_text(encoding='utf-8')
