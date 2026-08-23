"""Idempotently repair indexes after legacy database/schema upgrades."""
from sqlalchemy import inspect

from smartpricing.app_factory import create_app
from smartpricing.extensions import db


def main():
    app = create_app()
    with app.app_context():
        inspector = inspect(db.engine)
        existing = {
            index["name"]
            for table in inspector.get_table_names()
            for index in inspector.get_indexes(table)
        }
        for index in db.metadata.indexes:
            if index.name in existing:
                continue
            index.create(bind=db.engine, checkfirst=True)
        db.session.commit()
        print("Index repair complete")


if __name__ == "__main__":
    main()
