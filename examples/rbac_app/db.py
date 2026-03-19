from sqlalchemy import create_engine

# Database setup
SQLITE_PATH = "rbac_app.db"
DATABASE_URL = f"sqlite:///{SQLITE_PATH}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
