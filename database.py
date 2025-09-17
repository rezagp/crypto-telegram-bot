from datetime import datetime, timezone
from bson import ObjectId
from pymongo.errors import PyMongoError
import logging
import re

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db):
        self.db = db
        self.prices = self.db.prices
        self.users = self.db.users
        self.subscriptions = self.db.subscriptions
        self.alerts = self.db.alerts
    
    """---------- Get Base Currency Information ----------"""
    async def update_prices(self, api_response: dict):
        currency_list = api_response.get("result", {}).get("markets", [])
        
        for currency in currency_list:
            price_value = currency.get("price")
            if price_value is None:
                # If the price is not available, log a warning and move on to the next currency.
                logger.warning(f"Price for currency {currency.get('symbol')} is None. Skipping update for this item.")
                continue
            try:
                await self.prices.update_one(
                    { "_id": currency["symbol"] },
                    { "$set": { 
                        "symbol" : currency["base_asset"],
                        "fa_symbol" : currency["fa_base_asset"],
                        "en_base_asset" : currency["en_base_asset"],
                        "price" : float(currency["price"]),
                        "change_24h" : currency["change_24h"],
                        "volume_24h" : currency["volume_24h"],
                        "last_update" : datetime.now(timezone.utc)
                            } },
                    upsert=True
                )
            except (ValueError, TypeError) as e:
                logger.error(f"Could not process currency {currency.get('symbol')} due to invalid data: {e}")

    """---------- Add User ----------"""
    async def add_or_update_user(self, user_data: dict):
            await self.users.update_one(
                {"_id": user_data.id},
                {"$set": {
                    "first_name": user_data.first_name,
                    "last_name": user_data.last_name,
                    "username": user_data.username,
                    "last_seen": datetime.now(timezone.utc)
                },
                "$setOnInsert": {
                    "join_date": datetime.now(timezone.utc)
                }},
                upsert=True
            )

    """---------- Service 1 : Live Price ----------"""
    async def get_currency_info(self, targeted_currency: str):
        try:
            normalized_input = re.sub('[\s\u200c]+', '', targeted_currency)
            regex_pattern = '[\s\u200c]*'.join(list(normalized_input))
            query = {
                "$or": [
                    { "symbol" : {"$regex": f"^{targeted_currency}$", "$options": "i"} },
                    { "en_base_asset" : {"$regex": f"^{targeted_currency}$", "$options": "i"} },
                    { "fa_symbol" : { "$regex": f"^{regex_pattern}$", "$options": "i" } }
                ]
            }
            result = await self.prices.find_one(query, { "_id": 0 })
            return result
        except PyMongoError as e:
            logger.error(f"Database error while fetching currency info: {e}")
            return None

    """---------- Service 2 : Price Subscription ----------"""
    async def add_or_update_subscription(self, user_id, symbol, frequency):
        await self.subscriptions.update_one(
            {
                "user_id": user_id,
                "symbol": symbol
            },
            {
                "$set": {
                    "frequency": frequency,
                    "last_update": datetime.now(timezone.utc)
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "symbol": symbol,
                    "join_date": datetime.now(timezone.utc)
                }
            },
            upsert=True
        )

    async def get_subscriptions_by_frequency(self, frequency: str):
        try:
            cursor = self.subscriptions.find({"frequency": frequency})
            return await cursor.to_list(length=None)
        except PyMongoError as e:
            logger.error(f"Database error while fetching currency info: {e}")
            return []
        
    async def get_user_subscriptions(self, user_id):
        """Returns a list of all subscriptions for a given user."""
        return await self.subscriptions.find({"user_id": user_id}).to_list(length=100)
    
    async def delete_subscription_by_id(self, subscription_id_str: str):
        """
        Deletes a subscription from the database using its _id.
        """
        try:
            # Convert a string ID to a Mongo ObjectId object
            obj_id = ObjectId(subscription_id_str)
            
            result = await self.subscriptions.delete_one({"_id": obj_id})
            
            # If a document is deleted, the operation was successful.
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting subscription by ID: {e}")
            return False
    
    """---------- Service 3 : Price Alert ----------"""
    async def set_price_alert(self, user_id, symbol, target_price, condition: str):
        await self.alerts.update_one(
            { 
                "user_id" : user_id,
                "symbol" : symbol
            },
            {
                "$set" : {
                    "target_price" : float(target_price),
                    "status": "active",
                    "condition": condition,
                    "last_update": datetime.now(timezone.utc)
                },
                "$setOnInsert" : {
                    "user_id" : user_id,
                    "symbol" : symbol,
                    "join_date": datetime.now(timezone.utc)
                }
            },
            upsert=True
        )
    
    async def find_triggered_alerts(self):
        """
        Finds all active alerts where the target price has been met.
        """
        pipeline = [
            # Stage 1: Only look at active alerts
            {
                "$match": { "status": "active" }
            },
            # Stage 2: Join with the prices collection
            {
                "$lookup": {
                    "from": "prices",
                    "localField": "symbol",
                    "foreignField": "_id",
                    "as": "price_info"
                }
            },
            # Stage 3: Unwind the price_info array
            {
                "$unwind": "$price_info"
            },
            # Stage 4: Filter for alerts that have been triggered
            {
            "$match": {
                "$expr": {
                    "$or": [
                        # Case 1: Alert is for price increase (gte) and condition is met
                        {
                            "$and": [
                                { "$eq": ["$condition", "gte"] },
                                { "$gte": ["$price_info.price", "$target_price"] }
                            ]
                        },
                        # Case 2: Alert is for price decrease (lte) and condition is met
                        {
                            "$and": [
                                { "$eq": ["$condition", "lte"] },
                                { "$lte": ["$price_info.price", "$target_price"] }
                                ]
                            }
                        ]
                    }
                }
            }
        ]

        cursor = await self.alerts.aggregate(pipeline)
        triggered_alerts = await cursor.to_list(length=None)

        return triggered_alerts
    
    async def get_user_price_alert(self, user_id):
        return await self.alerts.find({"user_id": user_id}).to_list(length=100)
    
    async def delete_price_alert(self, alert_id_str: str):
        try:
            obj_id = ObjectId(alert_id_str)
            
            result = await self.alerts.delete_one({"_id": obj_id})
            
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting subscription by ID: {e}")
            return False

    async def update_alert_status(self, alert_id, new_status: str):
        """
        Updates the status of a specific alert (e.g. from 'active' to 'triggered').
        """
        try:
            result = await self.alerts.update_one(
                {"_id": alert_id},
                {"$set": {"status": new_status}}
            )
            # Returns True if a document has changed.
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"Failed to update alert status for {alert_id}: {e}")
            return False