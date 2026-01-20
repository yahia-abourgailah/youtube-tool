
import sqlalchemy
from sqlalchemy import text

# Connect to MySQL server (no database selected)
engine = sqlalchemy.create_engine('mysql+pymysql://root:root@localhost:3306')

with engine.connect() as conn:
    conn.execute(text("CREATE DATABASE IF NOT EXISTS egyptian_audio_db"))
    print("Database egyptian_audio_db created or already exists.")
