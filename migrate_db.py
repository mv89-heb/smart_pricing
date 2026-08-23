"""One-time database bootstrap/recovery command for deployments.

Run this as a Render pre-deploy command or from the Render shell:
    python migrate_db.py
"""

from smartpricing.app_factory import create_app
from smartpricing.db_setup import bootstrap


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        print("Starting Smart Pricing database bootstrap/migration...", flush=True)
        bootstrap()
        print("Database bootstrap/migration completed successfully.", flush=True)
