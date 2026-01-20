#!/usr/bin/env python3
"""
Script to add performance indexes to the database.
This script creates indexes on foreign keys and frequently queried columns
to significantly improve query performance, especially for the migration script.

Indexes to create:
- audio_chunks.video_id (foreign key join)
- videos.channel_id (foreign key join)
- activity_logs.video_id (foreign key join)
- activity_logs.channel_id (foreign key join)
- Optional: composite indexes for common query patterns
"""
import sys
import os

try:
    import pymysql
    from dotenv import load_dotenv
except ImportError as e:
    print(f"ERROR: Missing required package. Install with: pip3 install --user pymysql python-dotenv")
    print(f"Details: {e}")
    sys.exit(1)

# Load environment variables from .env file
load_dotenv()

# Database configuration - reads from environment variables or uses defaults
MYSQL_CONFIG = {
    'host': os.getenv('MYSQL_HOST', os.getenv('DB_HOST', '127.0.0.1')),
    'user': os.getenv('MYSQL_USER', os.getenv('DB_USER', 'root')),
    'password': os.getenv('MYSQL_PASSWORD', os.getenv('DB_PASSWORD', 'root')),
    'database': os.getenv('MYSQL_DATABASE', os.getenv('DB_NAME', 'egyptian_audio_db')),
    'port': int(os.getenv('MYSQL_PORT', os.getenv('DB_PORT', 3306)))
}

# Index definitions: (table, column(s), index_name, is_unique)
INDEXES = [
    # Foreign key indexes (critical for JOIN performance)
    ('audio_chunks', 'video_id', 'idx_audio_chunks_video_id', False),
    ('videos', 'channel_id', 'idx_videos_channel_id', False),
    ('activity_logs', 'video_id', 'idx_activity_logs_video_id', False),
    ('activity_logs', 'channel_id', 'idx_activity_logs_channel_id', False),
    
    # Status indexes (for filtering queries)
    ('videos', 'status', 'idx_videos_status', False),
    ('channels', 'status', 'idx_channels_status', False),
    ('jobs', 'status', 'idx_jobs_status', False),
    ('activity_logs', 'level', 'idx_activity_logs_level', False),
    
    # Composite indexes for common query patterns
    ('videos', ['channel_id', 'status'], 'idx_videos_channel_status', False),
    ('audio_chunks', ['video_id', 'created_at'], 'idx_audio_chunks_video_created', False),
    ('activity_logs', ['video_id', 'created_at'], 'idx_activity_logs_video_created', False),
    ('activity_logs', ['channel_id', 'created_at'], 'idx_activity_logs_channel_created', False),
]

def index_exists(cursor, table_name, index_name):
    """Check if an index already exists."""
    query = """
        SELECT COUNT(*) as count
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
        AND table_name = %s
        AND index_name = %s
    """
    cursor.execute(query, (table_name, index_name))
    result = cursor.fetchone()
    return result['count'] > 0

def create_index(cursor, table_name, columns, index_name, is_unique=False):
    """Create an index on a table."""
    if index_exists(cursor, table_name, index_name):
        return False, "already exists"
    
    # Handle single column vs composite index
    if isinstance(columns, list):
        columns_str = ', '.join(f'`{col}`' for col in columns)
    else:
        columns_str = f'`{columns}`'
    
    unique_keyword = 'UNIQUE' if is_unique else ''
    query = f"CREATE {unique_keyword} INDEX `{index_name}` ON `{table_name}` ({columns_str})"
    
    try:
        cursor.execute(query)
        return True, "created"
    except Exception as e:
        return False, str(e)

def add_indexes(dry_run=False):
    """Main function to add indexes."""
    print(f"Connecting to MySQL database: {MYSQL_CONFIG['database']}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE INDEX CREATION'}")
    print("=" * 60)
    
    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        print("\nChecking existing indexes and creating new ones...\n")
        
        stats = {
            'total': len(INDEXES),
            'created': 0,
            'skipped': 0,
            'errors': 0
        }
        
        for idx, (table, columns, index_name, is_unique) in enumerate(INDEXES, 1):
            columns_display = columns if isinstance(columns, str) else ', '.join(columns)
            unique_display = 'UNIQUE ' if is_unique else ''
            
            print(f"[{idx}/{stats['total']}] {unique_display}INDEX `{index_name}` on `{table}` ({columns_display})")
            
            if not dry_run:
                # Check if index exists
                if index_exists(cursor, table, index_name):
                    print(f"  ✓ Already exists, skipping")
                    stats['skipped'] += 1
                    continue
                
                # Create index
                success, message = create_index(cursor, table, columns, index_name, is_unique)
                
                if success:
                    print(f"  ✓ Created successfully")
                    stats['created'] += 1
                    conn.commit()
                else:
                    if "already exists" in message:
                        print(f"  ⊙ Already exists (race condition), skipping")
                        stats['skipped'] += 1
                    else:
                        print(f"  ✗ ERROR: {message}")
                        stats['errors'] += 1
            else:
                # Dry run - just check if it would be created
                if index_exists(cursor, table, index_name):
                    print(f"  [DRY RUN] Would skip (already exists)")
                    stats['skipped'] += 1
                else:
                    print(f"  [DRY RUN] Would create")
                    stats['created'] += 1
        
        # Print statistics
        print("\n" + "=" * 60)
        print("INDEX CREATION STATISTICS:")
        print(f"  Total indexes: {stats['total']}")
        print(f"  {'Would create' if dry_run else 'Created'}: {stats['created']}")
        print(f"  Skipped (already exist): {stats['skipped']}")
        print(f"  Errors: {stats['errors']}")
        print("=" * 60)
        
        if dry_run:
            print("\nThis was a DRY RUN. No indexes were created.")
            print("Run without --dry-run to create the indexes.")
        else:
            print("\n✓ Index creation completed!")
            print("\nNote: For large tables, index creation may take some time.")
            print("The connection may appear to hang, but indexes are being created in the background.")
        
        cursor.close()
        conn.close()
        
    except pymysql.Error as e:
        print(f"\n✗ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Add performance indexes to the database')
    parser.add_argument('--dry-run', action='store_true',
                       help='Check what indexes would be created without creating them')
    
    args = parser.parse_args()
    
    add_indexes(dry_run=args.dry_run)

