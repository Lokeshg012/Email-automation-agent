# test.py

import logging
# Assuming your file is named drip_logic.py and contains the drip_manager instance
from drip_logic import drip_manager

# Set up basic logging to see the output from the agent
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_the_agent():
    """
    Directly calls the agent to process all new contacts in the database.
    """
    logger.info("--- TRIGGERING THE 'process_initial_emails' AGENT ---")
    
    # This is the main call to your agent's logic
    drip_manager.process_initial_emails()
    
    logger.info("--- AGENT RUN COMPLETE ---")


if __name__ == "__main__":
    run_the_agent()