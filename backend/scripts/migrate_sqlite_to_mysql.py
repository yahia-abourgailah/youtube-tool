
import os
import sys
import time
from sqlalchemy import create_engine, MetaData, Table, select, insert, text

# Add parent dir to path to find app if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql_app.db")
SQLITE_URL = f"sqlite:///{SQLITE_DB_PATH}"
MYSQL_URL = "mysql+pymysql://root:root@127.0.0.1:3306/egyptian_audio_db"

def migrate_data():
    print(f"Source (SQLite): {SQLITE_URL}")
    print(f"Target (MySQL): {MYSQL_URL}")

    # Create engines
    source_engine = create_engine(SQLITE_URL)
    target_engine = create_engine(MYSQL_URL)
    
    # Pre-connect to verify
    print("Connecting to Source...")
    source_conn = source_engine.connect()
    print("Connected to Source.")

    print("Connecting to Target...")
    target_conn = target_engine.connect()
    print("Connected to Target.")
    
    source_meta = MetaData()
    target_meta = MetaData()

    print("Reflecting Source tables...")
    source_meta.reflect(bind=source_engine)
    print("Reflected Source.")

    print("Reflecting Target tables...")
    target_meta.reflect(bind=target_engine)
    print("Reflected Target.")

    # Tables to migrate in order of dependency
    tables_to_migrate = [
        "channels",
        "videos",
        "audio_chunks",
        "jobs",
        "activity_logs"
    ]

    target_conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
    
    try:
        # Don't use a single huge transaction if it locks too much, but for data consistency it's better
        # Let's try per-table transactions if the huge one failed, or just stick to one.
        # The previous fail was likely just slow reflection or connection timeout.
        
        for table_name in tables_to_migrate:
            print(f"Migrating table: {table_name}")
            
            if table_name not in source_meta.tables:
                print(f"  Skipping {table_name} (not found in source)")
                continue
                
            source_table = source_meta.tables[table_name]
            target_table = target_meta.tables.get(table_name)
            
            if target_table is None:
                print(f"  Skipping {table_name} (not found in target)")
                continue
            
            # Count rows first
            count_query = select(text(f"count(*) from {table_name}"))
            # For sqlite, standard count(*) works
            # Using core select count
            try:
                row_count = source_conn.execute(select(source_table.c.id)).rowcount 
                # rowcount isn't always reliable in select, use count(*)
                row_count = source_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                print(f"  Source has {row_count} rows.")
            except:
                print("  Could not count rows, proceeding with migration...")
                row_count = "unknown"

            # Select all from source using yield_per to stream
            sel = select(source_table)
            # SQLite driver might fetch all anyway, but let's try
            result = source_conn.execution_options(stream_results=True).execute(sel)
            
            chunk = []
            CHUNK_SIZE = 1000
            total_inserted = 0
            
            processed_keys = None

            for row in result:
                if processed_keys is None:
                    processed_keys = result.keys()

                row_dict = dict(zip(processed_keys, row))
                chunk.append(row_dict)
                
                if len(chunk) >= CHUNK_SIZE:
                    target_conn.execute(insert(target_table), chunk)
                    target_conn.commit() # Commit every chunk to see progress
                    total_inserted += len(chunk)
                    print(f"  Inserted {total_inserted} / {row_count}")
                    chunk = []
            
            if chunk:
                target_conn.execute(insert(target_table), chunk)
                target_conn.commit()
                total_inserted += len(chunk)
                print(f"  Inserted {total_inserted} / {row_count}")

        print("Migration completed successfully.")

    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        target_conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        source_conn.close()
        target_conn.close()

if __name__ == "__main__":
    migrate_data()
