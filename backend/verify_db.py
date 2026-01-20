
import sqlalchemy
from sqlalchemy import text, inspect

# Connect to MySQL database
engine = sqlalchemy.create_engine('mysql+pymysql://root:root@localhost:3306/egyptian_audio_db')

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
