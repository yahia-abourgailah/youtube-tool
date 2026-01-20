#!/usr/bin/env python3
"""
Simple migration script using only stdlib sqlite3 and pymysql.
Run with: python3 simple_migrate.py
"""
import sqlite3
import sys
import os

# Add pymysql to path if installed via pip
try:
    import pymysql
except ImportError:
    print("ERROR: pymysql not found. Install with: pip3 install --user pymysql")
    sys.exit(1)

SQLITE_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sql_app.db")
MYSQL_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': 'root',
    'database': 'egyptian_audio_db',
    'port': 3306
}

def main():
    print(f"Connecting to SQLite: {SQLITE_DB}")
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_conn.row_factory = sqlite3.Row
    
    print(f"Connecting to MySQL: {MYSQL_CONFIG['database']}")
    mysql_conn = pymysql.connect(**MYSQL_CONFIG)
    
    tables = ["channels", "videos", "audio_chunks", "jobs", "activity_logs"]
    
    try:
        with mysql_conn.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            for table in tables:
                print(f"\n=== Migrating {table} ===")
                
                # Get data from SQLite
                try:
                    rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
                except sqlite3.OperationalError as e:
                    print(f"  Skipping {table}: {e}")
                    continue
                
                if not rows:
                    print(f"  No data in {table}")
                    continue
                
                print(f"  Found {len(rows)} rows")
                
                # Get column names
                columns = list(rows[0].keys())
                placeholders = ', '.join(['%s'] * len(columns))
                col_names = ', '.join([f'`{c}`' for c in columns])
                sql = f"INSERT INTO `{table}` ({col_names}) VALUES ({placeholders})"
                
                # Convert rows to tuples
                data = [tuple(row[c] for c in columns) for row in rows]
                
                # Insert in batches
                batch_size = 1000
                for i in range(0, len(data), batch_size):
                    batch = data[i:i+batch_size]
                    cursor.executemany(sql, batch)
                    mysql_conn.commit()
                    print(f"  Inserted {min(i+batch_size, len(data))}/{len(data)}")
            
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            print("\n✓ Migration completed successfully!")
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        mysql_conn.rollback()
        raise
    finally:
        sqlite_conn.close()
        mysql_conn.close()

if __name__ == "__main__":
    main()
