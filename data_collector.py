import config
import logging
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timezone
from telegram.error import Forbidden

logger = logging.getLogger(__name__)

class Collector:
    def __init__(self, api_key, db_manager, app):
        self.api_key = api_key
        self.db_manager = db_manager
        self.app = app
        self.scheduler = AsyncIOScheduler()
        logger.info(f"Collector initialized.")
    
    async def get_currency_price(self):
        """Fetches the latest prices from the API, updates the DB, and sends triggered alerts."""
        logger.info("Task started: Fetching currency prices...")
        headers = {'x-api-key': self.api_key}
        api_url = "https://api.wallex.ir/hector/web/v1/markets"

        try:
            async with httpx.AsyncClient() as client:
                api_response = await client.get(api_url, headers=headers)
            api_response.raise_for_status()

            await self.db_manager.update_prices(api_response.json())
            logger.info("Data fetched and saved to database successfully.")

            triggered_alerts = await self.db_manager.find_triggered_alerts()
            for alert in triggered_alerts:
                try:
                    message = f"🎯 هشدار قیمت!\n"
                    message += f"ارز {alert['symbol']} به قیمت هدف شما یعنی {alert['target_price']} رسید."
                    
                    await self.app.bot.send_message(chat_id=alert['user_id'], text=message)
                    
                    await self.db_manager.update_alert_status(alert['_id'], "triggered")
                
                # This error occurs if the user has blocked the bot.
                except Forbidden:
                    logger.warning(f"User {alert['user_id']} has blocked the bot. Deactivating their alerts.")

                except Exception as e:
                    logger.error(f"Failed to send alert to user {alert['user_id']}: {e}")

        except httpx.RequestError as e:
            logger.error(f"Failed to fetch data from API.", exc_info=True)
    
    async def send_updates_subscription(self, frequency):
        """Sends price updates to all users subscribed to a specific frequency."""
        logger.info(f"Running {frequency} subscription job...")
        
        subscriptions = await self.db_manager.get_subscriptions_by_frequency(frequency)
        if not subscriptions:
            logger.info(f"No {frequency} subscriptions to send.")
            return
        for sub in subscriptions:
            try:
                price_data = await self.db_manager.get_currency_info(sub['symbol'])
                if price_data:
                    message = f"🔔 آپدیت {frequency} برای {price_data['fa_symbol']}:\n"
                    message += f"قیمت: {price_data['price']} تومان"
                    
                    await self.app.bot.send_message(chat_id=sub['user_id'], text=message)
            except Exception as e:
                logger.error(f"Failed to send update to user {sub['user_id']}: {e}")

    async def send_all_updates(self):
        logger.info("Running the main daily update job...")
        # 1. Always send daily updates.
        await self.send_updates_subscription("daily")

        # 2. Check if today is Saturday (In Iran, the week starts on Saturday.) (day of week == 5 for Saturday in Python)
        today = datetime.now(timezone.utc)
        if today.weekday() == 5:
            await self.send_updates_subscription("weekly")
        
        # 3. Check if today is the first day of the month
        if today.day == 1:
            await self.send_updates_subscription("monthly")

    def start_scheduler(self):
        self.scheduler.add_job(self.get_currency_price, 'interval', minutes=1)

        self.scheduler.add_job(self.send_all_updates, 'cron', hour=9, minute=0)

        self.scheduler.start()
        logger.info("Background data collection scheduler has been started.")
    
    def stop_scheduler(self):
        if self.scheduler.running:
            logger.info("Shutting down the data collection scheduler...")
            self.scheduler.shutdown()
            logger.info("Scheduler has been shut down successfully.")