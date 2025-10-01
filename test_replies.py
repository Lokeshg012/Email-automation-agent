# test_replies.py

import logging
# We import the main function from mail_service.py
from mail_service import check_and_update_replies

# Set up basic logging to see the detailed output from the agent
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_reply_checker_agent():
    """
    Directly calls the agent to check for and process new email replies.
    """
    logger.info("--- 🤖 TRIGGERING THE REPLY CHECKING AGENT ---")
    
    # This function handles logging in, finding replies, and updating the DB
    replies_found = check_and_update_replies()
    
    if replies_found > 0:
        logger.info(f"✅ AGENT RUN COMPLETE: Processed {replies_found} new reply/replies.")
    else:
        logger.info("✅ AGENT RUN COMPLETE: No new replies found from known contacts.")


if __name__ == "__main__":
    run_reply_checker_agent()
    
