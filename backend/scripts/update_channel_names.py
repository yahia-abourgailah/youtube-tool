"""
Script to update existing channels with their names from YouTube.
Run this once to populate channel names for existing channels in the database.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import models, database
from app.utils import youtube
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_channel_names():
    """Update all channels that don't have names."""
    db = database.SessionLocal()
    try:
        # Get all channels without names
        channels = db.query(models.Channel).filter(
            (models.Channel.name == None) | (models.Channel.name == '')
        ).all()
        
        logger.info(f"Found {len(channels)} channels without names")
        
        for channel in channels:
            try:
                logger.info(f"Fetching name for channel {channel.id}: {channel.url}")
                videos, channel_name = youtube.get_channel_videos(channel.url)
                
                if channel_name:
                    channel.name = channel_name
                    db.commit()
                    logger.info(f"Updated channel {channel.id} with name: {channel_name}")
                else:
                    logger.warning(f"Could not fetch name for channel {channel.id}")
                    
            except Exception as e:
                logger.error(f"Error updating channel {channel.id}: {str(e)}")
                db.rollback()
                continue
        
        logger.info("Finished updating channel names")
        
    finally:
        db.close()

if __name__ == "__main__":
    update_channel_names()
