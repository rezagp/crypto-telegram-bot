import logging
import sys

"""---------- Logging Config ----------"""
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'), # Handler to write to file
        logging.StreamHandler(sys.stdout) # Handler for writing to the console
    ]
)
# This section is to reduce additional logs from other libraries.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)