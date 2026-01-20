
import sqlalchemy
from sqlalchemy import text, inspect

import os
from dotenv import load_dotenv
load_dotenv()

# Connect to the database using the environment variable
db_url = os.getenv('DATABASE_URL')
if not db_url:
    print("DATABASE_URL not found in .env file.")
    exit(1)

engine = sqlalchemy.create_engine(db_url)

try:
    with engine.connect() as conn:
        print("Successfully connected to the database.")
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"Tables found: {tables}")
        
        if not tables:
             print("No tables found. Migration might have failed or database is empty.")
        else:
             print("Migration verification successful.")

except Exception as e:
    print(f"Connection failed: {e}")
