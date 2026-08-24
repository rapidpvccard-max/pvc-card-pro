import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Database URL configuration (Supports SQLite & Supabase PostgreSQL)
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./app.db").strip()

# SQLAlchemy requires 'postgresql://' instead of legacy 'postgres://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 15}
    )
    # Enable WAL mode for SQLite
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            conn.execute(text("PRAGMA synchronous=NORMAL;"))
    except Exception as e:
        print(f"[SQLite PRAGMA Warning] {e}")
else:
    # Production PostgreSQL / Supabase Configuration with auto-fallback
    try:
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,      # Automatically reconnects if connection goes idle
            pool_size=10,            # Efficient connection pooling
            max_overflow=20,
            pool_recycle=300
        )
        # Test connection
        with engine.connect() as conn:
            pass
    except Exception as e:
        print(f"[Warning] Failed to connect to PostgreSQL/Supabase ({e}). Falling back to local SQLite database (app.db).")
        DATABASE_URL = "sqlite:///./app.db"
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False, "timeout": 15}
        )
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("PRAGMA journal_mode=WAL;"))
                conn.execute(text("PRAGMA synchronous=NORMAL;"))
        except Exception:
            pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
