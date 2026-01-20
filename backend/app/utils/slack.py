"""
Slack notification utility for sending alerts and error messages.
"""
import os
import requests
import logging

logger = logging.getLogger(__name__)

def notify_slack(message: str) -> bool:
    """
    Send a notification to Slack via webhook.
    
    Args:
        message: The message to send to Slack
        
    Returns:
        True if notification was sent successfully, False otherwise
    """
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    
    # If webhook URL is not configured, skip silently
    if not webhook_url:
        logger.debug("SLACK_WEBHOOK_URL not configured, skipping notification")
        return False
    
    try:
        payload = {
            "text": message
        }
        headers = {
            "Content-Type": "application/json"
        }
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=5)
        
        if response.status_code == 200:
            logger.info("Slack notification sent successfully")
            return True
        else:
            logger.warning(f"Slack notification failed with status {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending Slack notification: {str(e)}")
        return False
