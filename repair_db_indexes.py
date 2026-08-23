"""Repair PostgreSQL index-name collisions before the one-time bootstrap.

Safe properties:
- never drops tables or rows;
- current-schema indexes with a model-owned name may be dropped because bootstrap recreates them;
- indexes belonging to legacy tables are renamed and therefore preserved;
- rerunning is safe.
"""

from sqlalchemy import text

from smartpricing.app_factory import create_app
from smartpricing.extensions import db


def quote_ident(value):
    return '"' + value.replace('"', '""') + '"'


def repair():
    metadata_index_names = {
        index.name: index.table.name
        for table in db.metadata.tables.values()
        for index in table.indexes
        if index.name
    }
    if not metadata_index_names:
        return 0

    rows = db.session.execute(text("""
        SELECT schemaname, tablename, indexname
        FROM pg_indexes
        WHERE schemaname = current_schema()
    """)).mappings().all()
    by_name = {}
    for row in rows:
        by_name.setdefault(row["indexname"], []).append(row)

    repaired = 0
    for index_name, expected_table in metadata_index_names.items():
        for row in by_name.get(index_name, []):
            actual_table = row["tablename"]
            if actual_table == expected_table:
                db.session.execute(text(f"DROP INDEX IF EXISTS {quote_ident(index_name)}"))
                repaired += 1
                continue

            if actual_table.startswith("legacy_v1_"):
                base = f"legacy_v1_{index_name}"
                new_name = base
                suffix = 2
                occupied = {r["indexname"] for values in by_name.values() for r in values}
                while new_name in occupied:
                    new_name = f"{base}_{suffix}"
                    suffix += 1
                db.session.execute(text(
                    f"ALTER INDEX {quote_ident(index_name)} RENAME TO {quote_ident(new_name)}"
                ))
                repaired += 1

    db.session.commit()
    return repaired


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        count = repair()
        print(f"Index collision repair completed: {count} index(es) repaired.", flush=True)
