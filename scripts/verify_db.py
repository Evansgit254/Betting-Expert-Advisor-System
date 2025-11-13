"""Verify database tables were created correctly."""
from sqlalchemy import inspect

try:
    from src.db import engine
except ModuleNotFoundError:  # pragma: no cover - fallback for direct execution
    import os
    import sys

    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    from src.db import engine


def verify_database():
    """Check that all expected tables exist in the database."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print(f"✅ Database file exists: {engine.url}")
    print(f"\n📊 Tables found ({len(tables)}):")

    for table in sorted(tables):
        columns = inspector.get_columns(table)
        print(f"\n  • {table}")
        print(f"    Columns: {len(columns)}")
        for col in columns[:5]:  # Show first 5 columns
            print(f"      - {col['name']}: {col['type']}")
        if len(columns) > 5:
            print(f"      ... and {len(columns) - 5} more columns")

    # Check expected tables
    expected_tables = [
        "bets",
        "model_metadata",
        "strategy_performance",
        "daily_stats",
        "alembic_version",
    ]
    missing = [t for t in expected_tables if t not in tables]

    if missing:
        print(f"\n⚠️  Missing expected tables: {missing}")
    else:
        print("\n✅ All expected tables present!")

    print("\n🎉 Database verification complete!")


if __name__ == "__main__":
    verify_database()
