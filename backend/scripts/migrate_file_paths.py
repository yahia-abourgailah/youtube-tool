"""
Migration script to update file paths in the database.
Updates all AudioChunk file_path references from old location to new location.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import models, database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLD_BASE_PATH = "/Users/ahmedwasfy/Documents/egyptian-dataset-audio/backend/data/"
NEW_BASE_PATH = "/Volumes/T7/projects/egyptian-dataset-audio/backend/data/"

def update_file_paths():
    """Update all file paths in the database from old location to new location."""
    db = database.SessionLocal()
    try:
        # Get all audio chunks
        chunks = db.query(models.AudioChunk).all()
        
        logger.info(f"Found {len(chunks)} audio chunks in database")
        
        updated_count = 0
        skipped_count = 0
        
        for chunk in chunks:
            if chunk.file_path and chunk.file_path.startswith(OLD_BASE_PATH):
                # Replace old base path with new base path
                old_path = chunk.file_path
                chunk.file_path = chunk.file_path.replace(OLD_BASE_PATH, NEW_BASE_PATH, 1)
                updated_count += 1
                
                if updated_count <= 5:  # Show first 5 updates
                    logger.info(f"Updated: {old_path}")
                    logger.info(f"     To: {chunk.file_path}")
            else:
                skipped_count += 1
        
        # Commit all changes
        db.commit()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Migration Summary:")
        logger.info(f"  Total chunks: {len(chunks)}")
        logger.info(f"  Updated: {updated_count}")
        logger.info(f"  Skipped (already correct or different path): {skipped_count}")
        logger.info(f"{'='*60}")
        
        # Verify a few updated paths
        if updated_count > 0:
            logger.info("\nVerifying updated paths (first 3):")
            updated_chunks = db.query(models.AudioChunk).filter(
                models.AudioChunk.file_path.like(f"{NEW_BASE_PATH}%")
            ).limit(3).all()
            
            for chunk in updated_chunks:
                file_exists = os.path.exists(chunk.file_path)
                status = "✓ EXISTS" if file_exists else "✗ NOT FOUND"
                logger.info(f"  {status}: {chunk.file_path}")
        
        return updated_count, skipped_count
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating file paths: {str(e)}", exc_info=True)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    logger.info(f"Starting file path migration...")
    logger.info(f"Old base path: {OLD_BASE_PATH}")
    logger.info(f"New base path: {NEW_BASE_PATH}")
    logger.info(f"")
    
    updated, skipped = update_file_paths()
    
    logger.info(f"\nMigration completed successfully!")
    logger.info(f"Updated {updated} file paths")
