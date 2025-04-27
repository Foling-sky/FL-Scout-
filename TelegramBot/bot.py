import os
import logging
import asyncio
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, ContextTypes, ConversationHandler, filters
)
from database import Database
from task_processor import TaskProcessor
from file_monitor import FileMonitor
from datetime import datetime, time
import telegram

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

KEYWORDS, PRICE_FILTER, PRICE_MIN = range(3)

class FLNotifyBot:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.db = Database()
        self.task_processor = TaskProcessor(self.db)
        self.file_monitor = FileMonitor(self.check_for_updates)
        self.monitoring_active = False
        
    async def check_for_updates(self):
        logger.info("Проверка обновлений в файле заказов")
        users = self.db.get_users_with_notifications()
        
        if not users:
            logger.info("Нет пользователей с включенными уведомлениями")
            return
            
        logger.info(f"Найдено {len(users)} пользователей с включенными уведомлениями")
            
        for user in users:
            user_id = user.get('user_id')
            logger.info(f"Проверка уведомлений для пользователя {user_id}")
            notifications = self.task_processor.get_notifications_for_user(user_id)
            
            if not notifications:
                logger.info(f"Нет новых уведомлений для пользователя {user_id}")
                continue
                
            logger.info(f"Найдено {len(notifications)} новых уведомлений для пользователя {user_id}")
            
            is_first_time = user.get('last_sent_id') is None or user.get('last_sent_id') == ''
            if is_first_time and notifications:
                last_task_id = notifications[-1]['task_id']
                self.db.update_last_sent_id(user_id, last_task_id)
                logger.info(f"Инициализирован последний ID заказа для пользователя {user_id}: {last_task_id}")
                continue
            
            last_task_id = None
            
            for notification in notifications:
                try:
                    task_id = notification['task_id']
                    last_task_id = task_id
                    
                    await self.send_task_notification(user_id, notification)
                    logger.info(f"Отправлено уведомление {task_id} для пользователя {user_id}")
                    
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
            
            if last_task_id:
                self.db.update_last_sent_id(user_id, last_task_id)
                logger.info(f"Обновлен последний ID заказа для пользователя {user_id}: {last_task_id}")
    
    async def send_task_notification(self, user_id: int, notification: Dict[str, Any]):
        price_info = notification['price_text']
        if 'По договоренности' in price_info and notification.get('price', 0) == 0:
            price_display = "💰 Цена: По договоренности"
        else:
            price = notification.get('price', 0)
            price_display = f"💰 Цена: {price_info} ({price} руб.)" if price > 0 else f"💰 Цена: {price_info}"
            
        message = (
            f"📌 {notification['ai_description']}\n\n"
            f"{price_display}\n"
            f"📅 Дата публикации: {notification['publication_date']}\n"
            f"🔗 [Перейти к заказу]({notification['url']})"
        )
        
        try:
            await self.application.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
            logger.info(f"Отправлено уведомление для пользователя {user_id}, задача: {notification['task_id']}")
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")
    
    async def send_daily_report(self):
        logger.info("Отправка ежедневного отчета")
        users = self.db.get_users_with_notifications()
        
        if not users:
            logger.info("Нет пользователей с включенными уведомлениями для отправки ежедневного отчета")
            return
        
        today = datetime.now()
        message = (
            f"🔔 *ЕЖЕДНЕВНЫЙ ОТЧЕТ* 🔔\n\n"
            f"📊 ═════════════════════ 📊\n"
            f"📌 *ЗАКАЗЫ ЗА ПРЕДЫДУЩИЙ ДЕНЬ*\n"
            f"📅 Дата: {today.strftime('%d.%m.%Y')}\n"
            f"═══════════════════════════\n\n"
            f"🔍 *НОВЫЕ ЗАКАЗЫ СЕГОДНЯ* 🔍\n"
            f"═══════════════════════════"
        )
        
        for user in users:
            user_id = user.get('user_id')
            try:
                await self.application.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='Markdown'
                )
                logger.info(f"Отправлен ежедневный отчет пользователю {user_id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке ежедневного отчета пользователю {user_id}: {e}")
            
            await asyncio.sleep(0.5)
    
    async def _send_daily_report_job(self, context):
        await self.send_daily_report()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name
        
        if not self.db.user_exists(user_id):
            self.db.add_user(user_id)
        
        settings = self.db.get_user_settings(user_id)
        notifications_enabled = settings.get('notifications_enabled', 0) == 1
        
        keyboard = [
            [InlineKeyboardButton("🔍 Изменить ключевые слова", callback_data="set_keywords")],
            [InlineKeyboardButton("💰 Настроить фильтр по цене", callback_data="set_price_filter")]
        ]
        
        if notifications_enabled:
            keyboard.append([InlineKeyboardButton("🔕 Выключить авторассылку", callback_data="toggle_notifications_off")])
        else:
            keyboard.append([InlineKeyboardButton("🔔 Включить авторассылку", callback_data="toggle_notifications_on")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"Привет, {username}! Я бот для уведомлений о заказах с FL.ru.\n\n"
            "Я буду отправлять тебе уведомления о новых заказах, "
            "которые соответствуют твоим настройкам фильтрации.\n\n"
            "Настрой свои предпочтения с помощью кнопок ниже:",
            reply_markup=reply_markup
        )
        
        if not self.monitoring_active:
            latest_id = self.task_processor.get_latest_task_id()
            if latest_id:
                self.db.update_last_sent_id(user_id, latest_id)
                logger.info(f"Инициализирован последний ID заказа для пользователя {user_id}: {latest_id}")
    
    async def menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = query.from_user.id
        
        settings = self.db.get_user_settings(user_id)
        notifications_enabled = settings.get('notifications_enabled', 0) == 1
        
        keyboard = [
            [InlineKeyboardButton("🔍 Изменить ключевые слова", callback_data="set_keywords")],
            [InlineKeyboardButton("💰 Настроить фильтр по цене", callback_data="set_price_filter")]
        ]
        
        if notifications_enabled:
            keyboard.append([InlineKeyboardButton("🔕 Выключить авторассылку", callback_data="toggle_notifications_off")])
        else:
            keyboard.append([InlineKeyboardButton("🔔 Включить авторассылку", callback_data="toggle_notifications_on")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        keywords_text = ", ".join(settings.get('keywords', [])) or "не указаны"
        
        price_filters = settings.get('price_filters', ['any'])
        price_texts = []
        
        if 'any' in price_filters:
            price_texts.append("Любая цена")
        if 'negotiated' in price_filters:
            price_texts.append("По договоренности")
        if 'min_price' in price_filters:
            price_texts.append(f"От {settings.get('price_min', 0)} рублей")
        
        if not price_texts:
            price_text = "Не настроен"
        else:
            price_text = ", ".join(price_texts)
        
        message_text = (
            "📋 Ваши текущие настройки:\n\n"
            f"🔑 Ключевые слова: {keywords_text}\n"
            f"💰 Фильтр по цене: {price_text}\n"
            f"🔔 Авторассылка: {'Включена' if notifications_enabled else 'Выключена'}\n\n"
            "Выберите действие:"
        )
        
        await query.answer()
        
        current_text = query.message.text if query.message.text else ""
        current_markup = query.message.reply_markup.to_dict() if query.message.reply_markup else None
        new_markup = reply_markup.to_dict()
        
        if current_text != message_text or current_markup != new_markup:
            try:
                await query.edit_message_text(text=message_text, reply_markup=reply_markup)
            except telegram.error.BadRequest as e:
                if "Message is not modified" in str(e):
                    logger.info(f"Сообщение уже имеет актуальное содержимое для пользователя {user_id}")
                else:
                    logger.error(f"Ошибка при обновлении сообщения: {e}")
                    raise
    
    async def set_keywords_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        settings = self.db.get_user_settings(user_id)
        
        current_keywords = ", ".join(settings.get('keywords', [])) or "не указаны"
        
        await query.edit_message_text(
            f"Текущие ключевые слова: {current_keywords}\n\n"
            "Отправьте новые ключевые слова через запятую.\n"
            "Например: python, разработка, парсинг\n\n"
            "Или отправьте /cancel для отмены."
        )
        
        return KEYWORDS
    
    async def set_keywords_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        
        keywords = [keyword.strip() for keyword in text.split(',') if keyword.strip()]
        
        self.db.update_keywords(user_id, keywords)
        
        keyboard = [[InlineKeyboardButton("◀️ Вернуться в меню", callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        keywords_text = ", ".join(keywords) or "не указаны"
        
        await update.message.reply_text(
            f"✅ Ключевые слова обновлены: {keywords_text}",
            reply_markup=reply_markup
        )
        
        return ConversationHandler.END
    
    async def set_price_filter_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        settings = self.db.get_user_settings(user_id)
        price_filters = settings.get('price_filters', ['any'])
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔸 Любая цена" if 'any' in price_filters else "Любая цена", 
                    callback_data="price_toggle_any"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔸 По договоренности" if 'negotiated' in price_filters else "По договоренности", 
                    callback_data="price_toggle_negotiated"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔸 От суммы..." if 'min_price' in price_filters else "От суммы...", 
                    callback_data="price_toggle_min"
                )
            ],
            [InlineKeyboardButton("💾 Сохранить", callback_data="price_save")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        context.user_data['price_filters'] = price_filters.copy()
        context.user_data['price_min'] = settings.get('price_min', 0)
        
        await query.edit_message_text(
            "Выберите фильтры по цене (можно выбрать несколько):",
            reply_markup=reply_markup
        )
        
        return PRICE_FILTER
    
    async def set_price_filter_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        callback_data = query.data
        
        price_filters = context.user_data.get('price_filters', ['any'])
        
        if callback_data == "price_toggle_any":
            if 'any' in price_filters:
                price_filters.remove('any')
                if not price_filters:
                    price_filters.append('any')
            else:
                price_filters = ['any']
                
        elif callback_data == "price_toggle_negotiated":
            if 'negotiated' in price_filters:
                price_filters.remove('negotiated')
                if not price_filters:
                    price_filters.append('any')
            else:
                if 'any' in price_filters:
                    price_filters.remove('any')
                price_filters.append('negotiated')
                
        elif callback_data == "price_toggle_min":
            context.user_data['price_filters'] = price_filters
            await query.edit_message_text(
                "Введите минимальную сумму в рублях (только число):\n"
                "Например: 5000\n\n"
                "Или отправьте /cancel для отмены."
            )
            return PRICE_MIN
            
        elif callback_data == "price_save":
            self.db.update_price_filters(user_id, price_filters, context.user_data.get('price_min', 0))
            
            filter_names = []
            if 'any' in price_filters:
                filter_names.append("Любая цена")
            if 'negotiated' in price_filters:
                filter_names.append("По договоренности")
            if 'min_price' in price_filters:
                filter_names.append(f"От {context.user_data.get('price_min', 0)} рублей")
                
            message = f"✅ Установлены фильтры: {', '.join(filter_names)}"
            
            keyboard = [[InlineKeyboardButton("◀️ Вернуться в меню", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                message,
                reply_markup=reply_markup
            )
            
            return ConversationHandler.END
            
        elif callback_data == "menu":
            await self.menu(update, context)
            return ConversationHandler.END
        
        context.user_data['price_filters'] = price_filters
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "🔸 Любая цена" if 'any' in price_filters else "Любая цена", 
                    callback_data="price_toggle_any"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔸 По договоренности" if 'negotiated' in price_filters else "По договоренности", 
                    callback_data="price_toggle_negotiated"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔸 От суммы..." if 'min_price' in price_filters else "От суммы...", 
                    callback_data="price_toggle_min"
                )
            ],
            [InlineKeyboardButton("💾 Сохранить", callback_data="price_save")],
            [InlineKeyboardButton("◀️ Назад", callback_data="menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Выберите фильтры по цене (можно выбрать несколько):",
            reply_markup=reply_markup
        )
        
        return PRICE_FILTER
    
    async def set_price_min_done(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        
        try:
            price_min = int(text)
            if price_min < 0:
                raise ValueError("Цена должна быть положительным числом")
            
            price_filters = context.user_data.get('price_filters', [])
            
            if 'any' in price_filters:
                price_filters.remove('any')
            if 'min_price' not in price_filters:
                price_filters.append('min_price')
                
            if not price_filters:
                price_filters.append('min_price')
                
            context.user_data['price_min'] = price_min
            
            self.db.update_price_filters(user_id, price_filters, price_min)
            
            filter_names = []
            if 'any' in price_filters:
                filter_names.append("Любая цена")
            if 'negotiated' in price_filters:
                filter_names.append("По договоренности")
            if 'min_price' in price_filters:
                filter_names.append(f"От {price_min} рублей")
                
            message = f"✅ Установлены фильтры: {', '.join(filter_names)}"
            
            keyboard = [[InlineKeyboardButton("◀️ Вернуться в меню", callback_data="menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                reply_markup=reply_markup
            )
            
            return ConversationHandler.END
        
        except ValueError:
            await update.message.reply_text(
                "❌ Пожалуйста, введите корректное число.\n"
                "Например: 5000\n\n"
                "Или отправьте /cancel для отмены."
            )
            
            return PRICE_MIN
    
    async def toggle_notifications(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        callback_data = query.data
        
        enable = callback_data == "toggle_notifications_on"
        
        self.db.toggle_notifications(user_id, enable)
        
        if enable:
            latest_id = self.task_processor.get_latest_task_id()
            if latest_id:
                self.db.update_last_sent_id(user_id, latest_id)
                logger.info(f"Инициализирован последний ID заказа для пользователя {user_id}: {latest_id}")
                
            if not self.monitoring_active:
                self.file_monitor.start()
                self.monitoring_active = True
                logger.info("Мониторинг файла запущен")
        
        try:
            await self.menu(update, context)
        except telegram.error.BadRequest as e:
            if "Message is not modified" in str(e):
                logger.info(f"Сообщение уже имеет актуальное содержимое для пользователя {user_id}")
            else:
                logger.error(f"Ошибка при обновлении сообщения: {e}")
    
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [[InlineKeyboardButton("◀️ Вернуться в меню", callback_data="menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "❌ Действие отменено.",
            reply_markup=reply_markup
        )
        
        return ConversationHandler.END
    
    def run(self):
        application = Application.builder().token(self.token).build()
        self.application = application
        
        keywords_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.set_keywords_start, pattern="^set_keywords$")],
            states={
                KEYWORDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_keywords_done)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )
        
        price_filter_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.set_price_filter_start, pattern="^set_price_filter$")],
            states={
                PRICE_FILTER: [CallbackQueryHandler(self.set_price_filter_done, pattern="^price_")],
                PRICE_MIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.set_price_min_done)]
            },
            fallbacks=[CommandHandler("cancel", self.cancel)]
        )
        
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("menu", self.start))
        application.add_handler(keywords_handler)
        application.add_handler(price_filter_handler)
        application.add_handler(CallbackQueryHandler(self.toggle_notifications, pattern="^toggle_notifications_"))
        application.add_handler(CallbackQueryHandler(self.menu, pattern="^menu$"))
        
        users_with_notifications = self.db.get_users_with_notifications()
        if users_with_notifications:
            logger.info(f"Обнаружено {len(users_with_notifications)} пользователей с включенными уведомлениями")
            self.file_monitor.start()
            self.monitoring_active = True
            logger.info("Мониторинг файла запущен автоматически")
        else:
            logger.info("Нет пользователей с включенными уведомлениями, мониторинг файла не запущен")
        
        target_time = time(0, 0, 0)
        application.job_queue.run_daily(
            self._send_daily_report_job,
            time=target_time
        )
        logger.info("Запланирована отправка ежедневного отчета в 00:00")
        
        logger.info("Бот запущен")
        application.run_polling()

    def update_price_filter(self, user_id: int, price_filter: str, price_min: int = 0) -> None:
        price_filters = [price_filter] if price_filter else ['any']
        self.db.update_price_filters(user_id, price_filters, price_min)

if __name__ == "__main__":
    bot = FLNotifyBot()
    bot.run() 