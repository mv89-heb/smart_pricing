web: playwright install chromium && gunicorn --workers 2 --threads 4 --timeout 120 --keep-alive 5 --access-logfile - --error-logfile - wsgi:app
