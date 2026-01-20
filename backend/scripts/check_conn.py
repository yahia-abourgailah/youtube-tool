
import os
import sys
from sqlalchemy import create_engine, text

# Configuration
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql_app.db")
SQLITE_URL = f"sqlite:///{SQLITE_DB_PATH}"
MYSQL_URL = "mysql+pymysql://root:root@localhost:3306/egyptian_audio_db"

def check_connections():
    print(f"Checking SQLite: {SQLITE_URL}")
    try:
        e1 = create_engine(SQLITE_URL)
        with e1.connect() as c1:
            print("SQLite Connected. Version:", c1.execute(text("select sqlite_version()")).scalar())
    except Exception as e:
        print("SQLite Failed:", e)

    print(f"Checking MySQL: {MYSQL_URL}")
    try:
        e2 = create_engine(MYSQL_URL)
        with e2.connect() as c2:
            print("MySQL Connected. Version:", c2.execute(text("select version()")).scalar())
    except Exception as e:
        print("MySQL Failed:", e)

if __name__ == "__main__":
    check_connections()
