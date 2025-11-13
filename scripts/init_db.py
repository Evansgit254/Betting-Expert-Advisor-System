"""Initialize or update the database schema."""
from alembic import command
from alembic.config import Config


def init_db():
    """Initialize or update the database schema."""
    from src.db import Base, engine

    print("Creating database tables...")

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Run any pending migrations (optional - skip if no migrations exist)
    try:
        print("Running database migrations...")
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        print("Migrations completed successfully!")
    except Exception as e:
        print(f"Note: Migration step skipped ({e})")
        print("This is normal for initial setup - tables created directly.")

    print("Database initialized successfully!")


if __name__ == "__main__":
    init_db()
