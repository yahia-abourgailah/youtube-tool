
print("Start of script")
import sys
print("Imported sys")
import os
print("Imported os")

try:
    print("Importing sqlalchemy...")
    from sqlalchemy import create_engine, MetaData, select, insert, text
    print("Imported sqlalchemy")
except ImportError as e:
    print(f"Failed to import sqlalchemy: {e}")

try:
    print("Importing pymysql...")
    import pymysql
    print("Imported pymysql")
except ImportError as e:
    print(f"Failed to import pymysql: {e}")

# Configuration
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql_app.db")
SQLITE_URL = f"sqlite:///{SQLITE_DB_PATH}"
MYSQL_URL = "mysql+pymysql://root:root@127.0.0.1:3306/egyptian_audio_db"

def debug_run():
    print("In debug_run")
    print(f"SQLite URL: {SQLITE_URL}")
    print(f"MySQL URL: {MYSQL_URL}")
    
    print("Creating SQLite engine...")
    source_engine = create_engine(SQLITE_URL)
    print("Created SQLite engine")
    
    print("Connecting to SQLite...")
    with source_engine.connect() as conn:
        print("Connected to SQLite")
        res = conn.execute(text("SELECT 1")).scalar()
        print(f"Select 1 result: {res}")
        
    print("Creating MySQL engine...")
    target_engine = create_engine(MYSQL_URL)
    print("Created MySQL engine")
    
    print("Connecting to MySQL...")
    try:
        with target_engine.connect() as conn:
            print("Connected to MySQL")
            res = conn.execute(text("SELECT 1")).scalar()
            print(f"Select 1 result: {res}")
    except Exception as e:
        print(f"MySQL Connection failed: {e}")

if __name__ == "__main__":
    debug_run()
