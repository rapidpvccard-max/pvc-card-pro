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

def ensure_database_schema(engine):
    try:
        from sqlalchemy import inspect, text
        import models
        models.Base.metadata.create_all(bind=engine)
        inspector = inspect(engine)
        
        schema_defs = {
            'users': [
                ('name', 'VARCHAR(255)'),
                ('hashed_password', 'VARCHAR(255)'),
                ('google_id', 'VARCHAR(255)'),
                ('avatar_url', 'VARCHAR(500)'),
                ('status', "VARCHAR(50) DEFAULT 'active'"),
                ('is_admin', 'BOOLEAN DEFAULT FALSE'),
                ('created_at', 'TIMESTAMP'),
                ('updated_at', 'TIMESTAMP'),
            ],
            'user_credits': [
                ('wallet_balance', 'FLOAT DEFAULT 0.0'),
                ('cost_per_card', 'FLOAT DEFAULT 0.95'),
                ('total_generated', 'INTEGER DEFAULT 0'),
                ('updated_at', 'TIMESTAMP'),
            ],
            'generation_history': [
                ('run_id', 'VARCHAR(255)'),
                ('document_type', "VARCHAR(50) DEFAULT 'aadhaar'"),
                ('status', 'VARCHAR(50)'),
                ('created_at', 'TIMESTAMP'),
                ('completed_at', 'TIMESTAMP'),
                ('card_count', 'INTEGER DEFAULT 1'),
            ],
            'orders': [
                ('provider_order_id', 'VARCHAR(255)'),
                ('provider_payment_id', 'VARCHAR(255)'),
                ('plan_id', 'INTEGER'),
                ('amount', 'FLOAT DEFAULT 0.0'),
                ('currency', "VARCHAR(10) DEFAULT 'USD'"),
                ('status', "VARCHAR(50) DEFAULT 'pending'"),
                ('created_at', 'TIMESTAMP'),
                ('updated_at', 'TIMESTAMP'),
            ],
            'credit_transactions': [
                ('amount', 'FLOAT DEFAULT 0.0'),
                ('transaction_type', 'VARCHAR(100)'),
                ('reference_id', 'VARCHAR(255)'),
                ('balance_after', 'FLOAT DEFAULT 0.0'),
                ('created_at', 'TIMESTAMP'),
            ],
            'admin_audit_logs': [
                ('admin_id', 'INTEGER'),
                ('action', 'VARCHAR(100)'),
                ('target_user_id', 'INTEGER'),
                ('details', 'TEXT'),
                ('created_at', 'TIMESTAMP'),
            ]
        }
        
        with engine.begin() as conn:
            for table_name, cols in schema_defs.items():
                if not inspector.has_table(table_name):
                    continue
                existing_cols = {c['name'].lower() for c in inspector.get_columns(table_name)}
                for col_name, col_type in cols:
                    if col_name.lower() not in existing_cols:
                        try:
                            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
                        except Exception as err:
                            print(f"[Schema Auto-Migration] Note on {table_name}.{col_name}: {err}")

            # Seed default plans if plans table is empty
            if inspector.has_table('plans'):
                count = conn.execute(text("SELECT COUNT(*) FROM plans;")).scalar()
                if count == 0:
                    conn.execute(text("""
                        INSERT INTO plans (id, name, price, credits, validity_days, active) VALUES
                        (1, 'Trial Pack', 20.0, 20, 365, TRUE),
                        (2, 'Starter Pack', 100.0, 100, 365, TRUE),
                        (3, 'Pro Pack', 200.0, 200, 365, TRUE),
                        (4, 'Business Pack', 300.0, 300, 365, TRUE)
                    """))
    except Exception as e:
        print(f"[Schema Auto-Migration Warning] {e}")
        print(f"[Schema Auto-Migration Warning] {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
