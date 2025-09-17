import os
import logging
from dotenv import load_dotenv

import pymongo
from pymongo.asynchronous.mongo_client import AsyncMongoClient
from telegram.ext import Application, PicklePersistence, PersistenceInput

import config
from database import Database
from data_collector import Collector
from bot import Bot

logger = logging.getLogger(__name__)

"""---------- Define functions for startup and shutdown ----------"""

async def post_init(app: Application):
    """Things to do after the bot is initially prepared."""
    logger.info("Bot is initialized. Setting up database and services...")
    
    # Connecting to the database and pinging
    mongo_uri = os.getenv("MONGO_URI")
    db_name = os.getenv("DB_NAME")
    app.mongo_client = AsyncMongoClient(
        mongo_uri,
        server_api=pymongo.server_api.ServerApi(version="1", strict=True, deprecation_errors=True)
    )
    await app.mongo_client.admin.command('ping')
    logger.info("Successfully connected and pinged MongoDB!")

    db = app.mongo_client[db_name]
    app.db_manager = Database(db)
    
    # Construction and commissioning of the collector
    wallex_api_key = os.getenv("WALLEX_API_KEY")
    collector = Collector(api_key=wallex_api_key, db_manager=app.db_manager, app=app)
    collector.start_scheduler()
    app.bot_data['collector'] = collector
    logger.info("Background services started.")

async def post_stop(app: Application):
    """Things to do before the bot completely shuts down."""
    logger.info("Application is shutting down...")
    if hasattr(app, 'collector'):
        app.collector.stop_scheduler()
    if hasattr(app, 'mongo_client'):
        await app.mongo_client.close()
        logger.info("MongoDB connection closed.")


def main():
    """The main starting point of the program."""
    logger.info("Application starting up...")
    load_dotenv()
    
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    
    persistence_input = PersistenceInput(
        user_data=True,
        chat_data=True,
        bot_data=False,
        # conversations=True  # In this version of the library, it is done automatically
    )
    persistence = PicklePersistence(
        filepath="bot_data.pickle",
        store_data=persistence_input
    )

    # Building an application and registering startup and shutdown functions
    application = (
        Application.builder()
        .token(telegram_token)
        .persistence(persistence)
        .post_init(post_init)
        .post_stop(post_stop)
        .build()
    )

    # Creating a bot instance and adding handlers
    telegram_bot = Bot() 
    application.add_handler(telegram_bot.get_conv_handler())

    # Running the Bot
    application.run_polling()


if __name__ == "__main__":
    main()