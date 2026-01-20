
import sqlite3
import pymysql
import os

SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql_app.db")
MYSQL_HOST = "127.0.0.1"
MYSQL_USER = "root"
MYSQL_PASS = "root"
MYSQL_DB = "egyptian_audio_db"

def migrate():
    print("Connecting to SQLite...")
    sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()
    print("Connected to SQLite")
    
    print("Connecting to MySQL...")
    mysql_conn = pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASS,
        database=MYSQL_DB,
        cursorclass=pymysql.cursors.DictCursor
    )
    mysql_cur = mysql_conn.cursor()
    print("Connected to MySQL")

    tables = [
        "channels",
        "videos",
        "audio_chunks",
        "jobs",
        "activity_logs"
    ]

    try:
        mysql_cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        
        for table in tables:
            print(f"Migrating {table}...")
            
            # Fetch all from SQLite
            try:
                sqlite_cur.execute(f"SELECT * FROM {table}")
                rows = sqlite_cur.fetchall()
            except sqlite3.OperationalError:
                print(f"Table {table} not found in SQLite.")
                continue

            if not rows:
                print(f"No rows in {table}")
                continue
            
            print(f"Found {len(rows)} rows in {table}")
            
            # Get columns
            columns = rows[0].keys()
            cols_str = ", ".join([f"`{c}`" for c in columns])
            placeholders = ", ".join(["%s"] * len(columns))
            sql = f"INSERT INTO `{table}` ({cols_str}) VALUES ({placeholders})"
            
            data = []
            for row in rows:
                data.append([row[col] for col in columns])
            
            # Bulk insert
            try:
                mysql_cur.executemany(sql, data)
                mysql_conn.commit()
                print(f"Inserted {len(data)} rows into {table}")
            except Exception as e:
                print(f"Error inserting into {table}: {e}")

    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        mysql_cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        sqlite_conn.close()
        mysql_conn.close()
        print("Done.")

if __name__ == "__main__":
    migrate()
