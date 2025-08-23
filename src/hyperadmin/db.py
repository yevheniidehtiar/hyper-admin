from sqlmodel import SQLModel, Session


def create_db_and_tables(engine):
    """
    Creates the database and all tables.
    """
    SQLModel.metadata.create_all(engine)
