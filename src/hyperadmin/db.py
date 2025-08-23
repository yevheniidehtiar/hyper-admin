from sqlmodel import Session, SQLModel, create_engine

sqlite_file_name = "db.sqlite3"
sqlite_url = f"sqlite:///{sqlite_file_name}"

engine = create_engine(sqlite_url, echo=True)


def get_session():
    """Returns a new database session."""
    with Session(engine) as session:
        yield session


def create_db_and_tables():
    """Creates the database and all tables."""
    SQLModel.metadata.create_all(engine)
