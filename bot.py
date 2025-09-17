import config
import logging
import jdatetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, ContextTypes, CommandHandler, MessageHandler, filters, ConversationHandler

logger = logging.getLogger(__name__)

class Bot:
    def __init__(self):
        self.FREQUENCY_MAP = {
        "daily": "روزانه",
        "weekly": "هفتگی",
        "monthly": "ماهانه"
        }
        (
            self.MAIN_MENU,              # The main menu with 3 buttons

            # States for the "Live Price" flow
            self.GETTING_LIVE_PRICE,     # Waiting for currency name
            self.AFTER_PRICE_RESULT,     # Showing the result with "check again/back" buttons

            # States for the "Price Alert" flow
            self.GETTING_ALERT_CURRENCY, # Waiting for currency name for an alert
            self.GETTING_TARGET_PRICE,   # Waiting for target price to be received for alert
            self.GETTING_ALERT_CONDITION,# Select alert condition (price increase/decrease)
            self.MANAGING_ALERTS,        # Alarm management menu (list/add/delete)

            # States for the "Subscription" flow
            self.GETTING_SUB_CURRENCY,   # Waiting for currency name for a new subscription
            self.GETTING_SUB_FREQUENCY,  # Waiting for the frequency (daily/weekly)
            self.MANAGING_SUBSCRIPTIONS  # Managing existing subscriptions
        ) = range(10)
        
        # --- Conversation Handler ---
        self.conv_handler = ConversationHandler(
            # How does the conversation start?
            entry_points=[CommandHandler('start', self.start_command)],
            
            # What happens in each state?
            states={
                # State 1: Main Menu
                # After the /start command, the bot is in this state, waiting for a button press.
                self.MAIN_MENU: [
                    CallbackQueryHandler(self.live_price_flow_start, pattern='^live_price$'),
                    CallbackQueryHandler(self.price_alert_flow_start, pattern='^price_alert$'),
                    CallbackQueryHandler(self.price_subscription_flow_start, pattern='^price_subscription$'),
                ],
                
                # States for the "Live Price" Flow
                self.GETTING_LIVE_PRICE: [
                    MessageHandler(filters.TEXT & (~filters.COMMAND), self.live_price_get_currency)
                ],
                self.AFTER_PRICE_RESULT: [
                CallbackQueryHandler(self.live_price_check_another, pattern='^live_price_again$'),
                CallbackQueryHandler(self.live_price_back_to_menu, pattern='^main_menu$'),
                ],

                # States for the "Price Alert" Flow
                self.GETTING_ALERT_CURRENCY: [
                    CallbackQueryHandler(self.price_alert_flow_start, pattern='^price_alert$'),
                    MessageHandler(filters.TEXT & (~filters.COMMAND), self.price_alert_get_currency)
                ],
                self.GETTING_ALERT_CONDITION: [
                    CallbackQueryHandler(self.price_alert_get_condition, pattern='^(gte|lte)$'),
                    CallbackQueryHandler(self.price_alert_flow_start, pattern='^price_alert$'),
                ],
                self.GETTING_TARGET_PRICE: [
                    CallbackQueryHandler(self.price_alert_flow_start, pattern='^price_alert$'),
                    MessageHandler(filters.TEXT & (~filters.COMMAND), self.price_alert_get_target_price)
                ],
                self.MANAGING_ALERTS: [
                    # Handler for the "Add New Alert" button
                    CallbackQueryHandler(self.start_new_alert_flow, pattern='^new_alert$'),
                    
                    # Handler for "Cancel" buttons
                    # Pattern looks for anything that starts with "cancel_alert_"
                    CallbackQueryHandler(self.cancel_alert, pattern='^cancel_alert_'),
                    
                    # Handler for the return to main menu button
                    CallbackQueryHandler(self.start_command, pattern='^main_menu$')
                ],
                # States for the "Price Subscription" Flow
                self.GETTING_SUB_CURRENCY: [
                    CallbackQueryHandler(self.price_subscription_flow_start, pattern='^price_subscription$'),
                    MessageHandler(filters.TEXT & (~filters.COMMAND), self.price_subscription_get_currency)
                ],
                self.GETTING_SUB_FREQUENCY: [
                    CallbackQueryHandler(self.price_subscription_get_frequency)
                ],
                self.MANAGING_SUBSCRIPTIONS: [
                # Handler for the "Add New Subscription" button
                CallbackQueryHandler(self.start_new_subscription_flow, pattern='^new_sub$'),
                
                # Handler for "Unsubscribe" buttons
                # Pattern looks for anything that starts with "cancel_sub_"
                CallbackQueryHandler(self.cancel_subscription, pattern='^cancel_sub_'),
                
                # Handler for the return to main menu button
                CallbackQueryHandler(self.start_command, pattern='^main_menu$')
                ]
            },
            
            # What happens if the user wants to exit?
            fallbacks=[
                CommandHandler('start', self.start_command), # Pressing /start again resets everything
                CommandHandler('cancel', self.cancel_command)
            ],
            
            per_user=True,
            persistent=True,
            name="main_conversation"
        )
    
    # We also need a method to return the handler to main.py
    def get_conv_handler(self):
        return self.conv_handler
    
    """---------- Start Handler ----------"""
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        message = """
    سلام! من دستیار شما برای اطلاع از قیمت لحظه‌ای ارزهای دیجیتال هستم. 🤖

    قابلیت‌های من:
    - نمایش قیمت لحظه‌ای ارز دیجیتال.
    - اعلام قیمت به‌صورت دوره‌ای (روزانه، هفتگی، ماهانه).
    - ایجاد هشدار قیمت.

    برای شروع، یکی از گزینه‌های زیر را انتخاب کنید:
    """

        user = update.effective_user
        logger.info("User %s (%s) started the conversation.", user.first_name, user.id)

        keyboard = [
            [InlineKeyboardButton("📈 قیمت لحظه‌ای ارز دیجیتال", callback_data="live_price")],
            [InlineKeyboardButton("🔔 اعلام قیمت به‌صورت دوره‌ای", callback_data="price_subscription")],
            [InlineKeyboardButton("🎯 ایجاد هشدار قیمت", callback_data="price_alert")]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # If it had been run with the /start command
        if update.message:
            await update.message.reply_text(message, reply_markup=reply_markup)
        # If it had been executed with the return button
        elif update.callback_query:
            await update.callback_query.edit_message_text(message, reply_markup=reply_markup)
        
        # Add or update user information in the database.
        db_manager = context.application.db_manager
        await db_manager.add_or_update_user(update.effective_user)
        return self.MAIN_MENU
    
    """---------- Service 1 : Live Price ----------"""
    async def live_price_flow_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles the 'Live Price' button press."""
        await update.callback_query.answer()

        message = "کافیه اسم به انگلیسی یا فارسی و یا نماد ارز مورد نظرت رو برام بفرستی. مثلاً: بیتکوین یا Bitcoin یا BTC"
        keyboard = [
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(text=message, reply_markup=reply_markup)

        return self.GETTING_LIVE_PRICE

    async def live_price_get_currency(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles the user's currency input for a live price check."""
        user_input = update.message.text
        db_manager = context.application.db_manager
        currency_data = await db_manager.get_currency_info(user_input)

        if currency_data:
            utc_last_update = currency_data['last_update']
            jalali_time = jdatetime.datetime.fromgregorian(datetime=utc_last_update)
            formatted_jalali_time = jalali_time.strftime('%Y/%m/%d - ساعت %H:%M')

            response_message = f"نماد: {currency_data['symbol']}\n"
            response_message += f"نام به انگلیسی: {currency_data['en_base_asset']}\n"
            response_message += f"نام به فارسی: {currency_data['fa_symbol']}\n"
            response_message += f"قیمت: {currency_data['price']} تومان\n"
            response_message += f"تغییرات در ۲۴ ساعت گذشته: {currency_data['change_24h']}\n"
            response_message += f"حجم معاملات در ۲۴ ساعت گذشته: {currency_data['volume_24h']}\n"
            response_message += f"آخرین به‌روزرسانی: {formatted_jalali_time}\n"
        
            keyboard = [
                [InlineKeyboardButton("🔍 بررسی یک ارز دیگر", callback_data="live_price_again")],
                [InlineKeyboardButton("⬅️ بازگشت به منوی اصلی", callback_data="main_menu")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(response_message, reply_markup=reply_markup)

            return self.AFTER_PRICE_RESULT
        else:
            response_message = f"متاسفانه واحد پول '{user_input}' پیدا نشد. لطفا دوباره امتحان کنید."
            await update.message.reply_text(response_message)
            return self.GETTING_LIVE_PRICE
    
    async def live_price_check_another(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """After displaying the price, it requests the next currency by sending a new message."""
        query = update.callback_query
        await query.answer()
        
        # Removing the previous message buttons (price result)
        await query.edit_message_reply_markup(reply_markup=None)

        # Sending the new currency request message in a new message.
        message = "کافیه اسم به انگلیسی یا فارسی و یا نماد ارز مورد نظرت رو برام بفرستی."
        await query.message.reply_text(text=message)
        
        # Returning the user to the stage of receiving the currency name.
        return self.GETTING_LIVE_PRICE

    async def live_price_back_to_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """After displaying the price, it displays the main menu by sending a new message."""
        query = update.callback_query
        await query.answer()
        
        # Removing the buttons from the previous message (price result).
        await query.edit_message_reply_markup(reply_markup=None)

        # Sending the main menu in a new message (instead of calling start_command)
        message = """
    سلام! من دستیار شما برای اطلاع از قیمت لحظه‌ای ارزهای دیجیتال هستم. 🤖

    قابلیت‌های من:
    - نمایش قیمت لحظه‌ای ارز دیجیتال.
    - اعلام قیمت به‌صورت دوره‌ای (روزانه، هفتگی، ماهانه).
    - ایجاد هشدار قیمت.

    برای شروع، یکی از گزینه‌های زیر را انتخاب کنید:
    """
        keyboard = [
            [InlineKeyboardButton("📈 قیمت لحظه‌ای ارز دیجیتال", callback_data="live_price")],
            [InlineKeyboardButton("🔔 اعلام قیمت به‌صورت دوره‌ای", callback_data="price_subscription")],
            [InlineKeyboardButton("🎯 ایجاد هشدار قیمت", callback_data="price_alert")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.reply_text(message, reply_markup=reply_markup)

        # We take the user to the main menu state.
        return self.MAIN_MENU
    
    """---------- Service 2 : Price Subscription ----------"""
    async def price_subscription_flow_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handles the 'Price Subscription' button press."""
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        db_manager = context.application.db_manager
        subscriptions = await db_manager.get_user_subscriptions(user_id)

        if subscriptions:
            message = "شما اشتراک‌های زیر را دارید. می‌توانید آنها را لغو کنید یا اشتراک جدیدی اضافه کنید."
            keyboard = []
            for sub in subscriptions:
                button_text = f"🗑️ لغو {sub['symbol']} ({self.FREQUENCY_MAP[sub['frequency']]})"
                callback_data = f"cancel_sub_{sub['_id']}" # Use the unique DB ID
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

            keyboard.append([InlineKeyboardButton("➕ افزدون اشتراک جدید", callback_data="new_sub")])
            keyboard.append([InlineKeyboardButton("⬅️ بازگشت به منو", callback_data="main_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text=message, reply_markup=reply_markup)
            
            return self.MANAGING_SUBSCRIPTIONS
        else:
            message = "لطفاً نام ارز مورد نظرت به انگلیسی، فارسی یا نماد آن را برای ایجاد اشتراک وارد کن:"
            
            keyboard = [
                [InlineKeyboardButton("⬅️ بازگشت", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(text=message, reply_markup=reply_markup)

            return self.GETTING_SUB_CURRENCY

    async def price_subscription_get_currency(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_input = update.message.text
        db_manager = context.application.db_manager
        currency_data = await db_manager.get_currency_info(user_input)

        if currency_data:
            context.user_data['sub_currency'] = user_input
            keyboard = [
                [
                InlineKeyboardButton("روزانه", callback_data="daily"),
                InlineKeyboardButton("هفتگی", callback_data="weekly"),
                InlineKeyboardButton("ماهانه", callback_data="monthly")
                ],
                [InlineKeyboardButton("⬅️ بازگشت", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = f"عالی! لطفاً دوره‌ی ارسال قیمت برای «{currency_data['fa_symbol']}» را انتخاب کنید:"
            await update.message.reply_text(message, reply_markup=reply_markup)
            return self.GETTING_SUB_FREQUENCY
        else:
            response_message = f"متاسفانه واحد پول '{user_input}' پیدا نشد. لطفا دوباره امتحان کنید."
            await update.message.reply_text(response_message)
            return await self.start_command(update, context)

    async def price_subscription_get_frequency(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        chosen_currency = context.user_data.get('sub_currency')
        chosen_frequency = query.data
        user_id = update.effective_user.id
        if not chosen_currency:
            error_message = "فکر کنم خطایی رخ داد! لطفا یک بار دیگه نام ارز مورد نظر را وارد کنید..."
            await query.edit_message_text(error_message)
            return self.GETTING_SUB_CURRENCY
        db_manager = context.application.db_manager
        await db_manager.add_or_update_subscription(
            user_id=user_id,
            symbol=chosen_currency,
            frequency=chosen_frequency
        )
        persian_frequency = self.FREQUENCY_MAP.get(chosen_frequency, chosen_frequency)
        confirmation_message = f"اشتراک شما برای دریافت قیمت {chosen_currency} به صورت {persian_frequency} با موفقیت ثبت شد."
        await query.answer(confirmation_message, show_alert=False)

        return await self.price_subscription_flow_start(update, context)

    async def start_new_subscription_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Redirects the user from the administration menu to the beginning of the new subscription registration process."""
        query = update.callback_query
        await query.answer()

        message = "لطفاً نام ارز مورد نظر برای اشتراک جدید را وارد کنید:"
        
        keyboard = [
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="price_subscription")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=message, reply_markup=reply_markup)

        # Sending the user to the "Get currency name for subscription" stage.
        return self.GETTING_SUB_CURRENCY

    async def cancel_subscription(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        یک اشتراک مشخص را بر اساس ID آن از دیتابیس حذف می‌کند.
        """
        query = update.callback_query
        await query.answer()
        
        # Extracting the subscription ID from callback_data
        # The callback_data looks like this: "cancel_sub_60b8d..."
        subscription_id_str = query.data.replace('cancel_sub_', '')
        
        # Delete subscription from database
        db_manager = context.application.db_manager
        success = await db_manager.delete_subscription_by_id(subscription_id_str)

        if success:
            await query.edit_message_text("اشتراک با موفقیت حذف شد. در حال بازسازی لیست...")
            # Returning the user to the beginning of the subscription flowchart.
            # The price_subscription_flow_start function checks itself and rebuilds the admin menu.
            return await self.price_subscription_flow_start(update, context)
        else:
            await query.edit_message_text("خطایی در حذف اشتراک رخ داد. لطفاً دوباره تلاش کنید.")
            return self.MANAGING_SUBSCRIPTIONS
    
    """---------- Service 3 : Price Alert ----------"""
    async def price_alert_flow_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE, send_new_message: bool = False):
        """Handles the 'Price Alert' button press."""
        query = update.callback_query
        if query:
            await query.answer()

        user_id = update.effective_user.id
        db_manager = context.application.db_manager
        check_subs = await db_manager.get_user_price_alert(user_id)
        if check_subs:
            message = "شما اعلان‌های زیر را دارید. می‌توانید آنها را لغو کنید یا اشتراک جدیدی اضافه کنید."
            keyboard = []
            for sub in check_subs:
                button_text = ""
                callback_data = ""
                button_text = f"🗑️ لغو {sub['symbol']} با قیمت ({sub['target_price']})"
                callback_data = f"cancel_alert_{sub['_id']}" # Use the unique DB ID
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            keyboard.append([InlineKeyboardButton("➕ افزدون اعلان جدید", callback_data="new_alert")])
            keyboard.append([InlineKeyboardButton("⬅️ بازگشت به منو", callback_data="main_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Edit the message if it came from a button.
            if query and not send_new_message:
                await query.edit_message_text(text=message, reply_markup=reply_markup)
            # Otherwise (e.g. after registering an alert), send a new message.
            else:
                await context.bot.send_message(chat_id=user_id, text=message, reply_markup=reply_markup)

            return self.MANAGING_ALERTS
        else:
            message = "لطفاً نام ارز مورد نظرت به انگلیسی، فارسی یا نماد آن را برای ایجاد اشتراک وارد کن:"
            keyboard = [
                [InlineKeyboardButton("⬅️ بازگشت", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text=message, reply_markup=reply_markup)

            return self.GETTING_ALERT_CURRENCY
    
    async def price_alert_get_currency(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_input = update.message.text
        db_manager = context.application.db_manager
        check_existence = await db_manager.get_currency_info(user_input)
        if check_existence:
            context.user_data['alert_currency'] = check_existence['symbol']
            message = f"عالی! برای ارز «{check_existence['fa_symbol']}» می‌خواهید در چه حالتی به شما اطلاع داده شود؟"
            keyboard = [
            [
                InlineKeyboardButton("📈 افزایش قیمت به", callback_data="gte"),
                InlineKeyboardButton("📉 کاهش قیمت به", callback_data="lte")
            ],
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="price_alert")]
        ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            sent_message = await update.message.reply_text(text=message, reply_markup=reply_markup)

            context.user_data['message_to_edit'] = sent_message.message_id
            return self.GETTING_ALERT_CONDITION
        else:
            response_message = f"متاسفانه واحد پول '{user_input}' پیدا نشد. لطفا دوباره امتحان کنید."
            await update.message.reply_text(response_message)
            return await self.start_command(update, context)
        
    async def price_alert_get_condition(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Receives a price increase or decrease condition from the user."""
        query = update.callback_query
        await query.answer()
        
        # Storing the selected condition ("gte" or "lte") in memory.
        context.user_data['alert_condition'] = query.data

        message = "بسیار خب، لطفاً قیمت هدف خود را (به تومان) وارد کنید:"
        keyboard = [
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="price_alert")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text=message, reply_markup=reply_markup)
        
        # Sending the bot to the "Receive target price" state.
        return self.GETTING_TARGET_PRICE
    
    async def price_alert_get_target_price(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chosen_currency = context.user_data.get('alert_currency')
        chosen_condition = context.user_data.get('alert_condition')
        target_price_str = update.message.text
        user_id = update.effective_user.id
        message_id_to_edit = context.user_data.get('message_to_edit')

        try:
            # Convert the input to a number
            target_price = float(target_price_str)
        except ValueError:
            await update.message.reply_text("لطفا برای اطلاع از قیمت، عدد صحیح را وارد کنید.")
            # Stay in the same state to let them try again
            return self.GETTING_TARGET_PRICE
    
        if not all([chosen_currency, user_id, message_id_to_edit, chosen_condition]):
            await update.message.reply_text("خطایی رخ داده. لطفا دوباره بات را /start کنید.")
            return ConversationHandler.END
        db_manager = context.application.db_manager
        await db_manager.set_price_alert(
            user_id=user_id,
            symbol=chosen_currency,
            target_price=target_price,
            condition=chosen_condition
        )

        confirmation_message = f"اعلان با موفقیت ثبت شد. {chosen_currency} به محض رسیدن به {target_price} اطلاع داده خواهد شد."
        
        # Use context.bot.edit_message_text with the saved IDs
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=message_id_to_edit,
            text=confirmation_message
        )
            
        # Clean up the context
        context.user_data.pop('message_to_edit', None)
        context.user_data.pop('alert_currency', None)

        await self.price_alert_flow_start(update, context, send_new_message=True)

        return self.MANAGING_ALERTS
    
    async def start_new_alert_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if query:
            await query.answer()
        user_id = update.effective_user.id
        message = "لطفاً نام ارز مورد نظر را برای تعریف اعلان جدید وارد کنید:"
        
        keyboard = [
            [InlineKeyboardButton("⬅️ بازگشت", callback_data="price_alert")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=message, reply_markup=reply_markup)

        return self.GETTING_ALERT_CURRENCY
    
    async def cancel_alert(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        alert_id_str = query.data.replace('cancel_alert_', '')
        
        # Delete subscription from database
        db_manager = context.application.db_manager
        success = await db_manager.delete_price_alert(alert_id_str)

        if success:
            await query.edit_message_text("اعلان با موفقیت حذف شد. در حال بازسازی لیست...")

            return await self.price_alert_flow_start(update, context)
        else:
            await query.edit_message_text("خطایی در حذف اشتراک رخ داد. لطفاً دوباره تلاش کنید.")
            return self.MANAGING_ALERTS

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancels and ends the conversation."""
        user = update.effective_user
        logger.info("User %s canceled the conversation.", user.first_name)
        await update.message.reply_text(
            'باشه! هر وقت آماده بودی، دوباره با /start شروع کن.'
        )
        # Ending the conversation
        return ConversationHandler.END

    async def run_async(self):
        """Configures handlers and starts bot polling."""
        logger.info("Configuring bot handlers...")

        self.app.add_handler(self.conv_handler)

        logger.info("Bot is starting to poll...")

        await self.app.run_polling()