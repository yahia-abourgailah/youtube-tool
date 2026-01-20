"""
Quick script to update existing channels with their names from YouTube.
This version only fetches the channel name without iterating through all videos.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import models, database
from pytubefix import Channel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_channel_names_fast():
    """Update all channels that don't have names - fast version."""
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
                c = Channel(channel.url)
                
                # Just get the channel name without iterating videos
                try:
                    channel_name = c.channel_name
                    if channel_name:
                        channel.name = channel_name
                        db.commit()
                        logger.info(f"Updated channel {channel.id} with name: {channel_name}")
                    else:
                        logger.warning(f"Channel name is empty for channel {channel.id}")
                except Exception as name_err:
                    logger.error(f"Could not fetch channel name for {channel.id}: {str(name_err)}")
                    
            except Exception as e:
                logger.error(f"Error updating channel {channel.id}: {str(e)}")
                db.rollback()
                continue
        
        logger.info("Finished updating channel names")
        
    finally:
        db.close()

if __name__ == "__main__":
    update_channel_names_fast()
