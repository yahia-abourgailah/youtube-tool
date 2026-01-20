
import os
from sqlalchemy import create_engine
# Ensure we load models so Base knows about them
from app.models import Base
# Import config but don't use its engine to avoid side effects if any
from app.database import SQLALCHEMY_DATABASE_URL

print(f"Connecting to: {SQLALCHEMY_DATABASE_URL}")
engine = create_engine(SQLALCHEMY_DATABASE_URL)

def init_db():
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

if __name__ == "__main__":
    init_db()
