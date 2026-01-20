#!/usr/bin/env python3
"""
Migration script to reorganize chunk files from flat structure to hierarchical:
- Old: data/{chunk_id}.wav
- New: data/channels/{channel_id}/videos/{video_id}/{chunk_id}.wav

This migration:
1. Queries all chunks from the database with their video and channel info
2. Creates the new directory structure
3. Moves files to the new locations
4. Updates the database with new file paths
"""
import sys
import os
import shutil
from pathlib import Path
from tqdm import tqdm

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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

# Base data directory
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'data')
DATA_DIR = os.path.abspath(DATA_DIR)

def get_chunks_with_video_info(cursor):
    """Get all chunks with their video and channel information."""
    query = """
        SELECT 
            ac.id,
            ac.chunk_id,
            ac.file_path,
            ac.video_id,
            v.video_id as video_identifier,
            v.channel_id,
            c.id as channel_identifier
        FROM audio_chunks ac
        JOIN videos v ON ac.video_id = v.id
        JOIN channels c ON v.channel_id = c.id
        ORDER BY ac.id
    """
    cursor.execute(query)
    return cursor.fetchall()

def create_new_path(channel_id, video_id, chunk_filename, data_dir):
    """Generate new file path in hierarchical structure."""
    new_dir = os.path.join(data_dir, 'channels', str(channel_id), 'videos', str(video_id))
    new_path = os.path.join(new_dir, chunk_filename)
    return new_path, new_dir

def migrate_chunks(dry_run=False):
    """Main migration function."""
    print(f"Connecting to MySQL database: {MYSQL_CONFIG['database']}")
    print(f"Data directory: {DATA_DIR}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE MIGRATION'}")
    print("=" * 60)
    
    if not os.path.exists(DATA_DIR):
        print(f"ERROR: Data directory does not exist: {DATA_DIR}")
        sys.exit(1)
    
    try:
        conn = pymysql.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Get all chunks with their video and channel info
        print("\nFetching chunks from database...")
        chunks = get_chunks_with_video_info(cursor)
        
        if not chunks:
            print("No chunks found in database.")
            return
        
        print(f"Found {len(chunks)} chunks to migrate")
        print("\nStarting migration...\n")
        
        stats = {
            'total': len(chunks),
            'moved': 0,
            'missing': 0,
            'errors': 0,
            'skipped': 0
        }
        
        for idx, chunk in tqdm(enumerate(chunks, 1), total=len(chunks), desc="Migrating chunks"):
            old_path = chunk['file_path']
            chunk_id = chunk['chunk_id']
            video_id = chunk['video_identifier']
            channel_id = chunk['channel_identifier']
            
            # Extract filename from old path
            chunk_filename = os.path.basename(old_path)
            
            # Generate new path
            new_path, new_dir = create_new_path(channel_id, video_id, chunk_filename, DATA_DIR)
            
            # Normalize old path to absolute for comparison and operations
            if not os.path.isabs(old_path):
                # Relative path - assume it's relative to data_dir
                old_path_abs = os.path.join(DATA_DIR, old_path)
            else:
                old_path_abs = old_path
            
            old_path_abs = os.path.abspath(old_path_abs)
            new_structure_prefix = os.path.abspath(os.path.join(DATA_DIR, 'channels'))
            
            # Check if already in new structure
            if old_path_abs.startswith(new_structure_prefix):
                print(f"[{idx}/{stats['total']}] SKIP: {chunk_id} - Already in new structure")
                stats['skipped'] += 1
                continue
            
            # Use normalized absolute path for file operations
            old_path = old_path_abs
            
            print(f"[{idx}/{stats['total']}] Processing: {chunk_id}")
            print(f"  Channel ID: {channel_id}, Video ID: {video_id}")
            print(f"  Old: {old_path}")
            print(f"  New: {new_path}")
            
            # Check if old file exists
            if not os.path.exists(old_path):
                print(f"  WARNING: Old file does not exist!")
                stats['missing'] += 1
                if not dry_run:
                    # Still update the path in database
                    cursor.execute(
                        "UPDATE audio_chunks SET file_path = %s WHERE id = %s",
                        (new_path, chunk['id'])
                    )
                continue
            
            # Check if new file already exists (might have been moved manually)
            if os.path.exists(new_path):
                print(f"  INFO: New file already exists, skipping move")
                if not dry_run:
                    cursor.execute(
                        "UPDATE audio_chunks SET file_path = %s WHERE id = %s",
                        (new_path, chunk['id'])
                    )
                    stats['moved'] += 1
                continue
            
            if not dry_run:
                try:
                    # Create directory if it doesn't exist
                    os.makedirs(new_dir, exist_ok=True)
                    
                    # Move file
                    shutil.move(old_path, new_path)
                    
                    # Update database
                    cursor.execute(
                        "UPDATE audio_chunks SET file_path = %s WHERE id = %s",
                        (new_path, chunk['id'])
                    )
                    
                    stats['moved'] += 1
                    print(f"  ✓ Moved successfully")
                except Exception as e:
                    stats['errors'] += 1
                    print(f"  ✗ ERROR: {e}")
            else:
                stats['moved'] += 1
                print(f"  [DRY RUN] Would move and update")
            
            # Commit every 100 chunks
            if not dry_run and idx % 100 == 0:
                conn.commit()
                print(f"\n  Committed {idx} chunks...\n")
        
        # Final commit
        if not dry_run:
            conn.commit()
        
        # Print statistics
        print("\n" + "=" * 60)
        print("MIGRATION STATISTICS:")
        print(f"  Total chunks: {stats['total']}")
        print(f"  Successfully migrated: {stats['moved']}")
        print(f"  Missing files: {stats['missing']}")
        print(f"  Errors: {stats['errors']}")
        print(f"  Skipped (already migrated): {stats['skipped']}")
        print("=" * 60)
        
        if dry_run:
            print("\nThis was a DRY RUN. No files were moved and no database was updated.")
            print("Run without --dry-run to perform the actual migration.")
        else:
            print("\n✓ Migration completed successfully!")
        
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
    
    parser = argparse.ArgumentParser(description='Migrate chunk files to hierarchical structure')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Run migration without making changes')
    parser.add_argument('--data-dir', type=str,
                       help='Override data directory path')
    
    args = parser.parse_args()
    
    if args.data_dir:
        DATA_DIR = os.path.abspath(args.data_dir)
    
    migrate_chunks(dry_run=args.dry_run)

