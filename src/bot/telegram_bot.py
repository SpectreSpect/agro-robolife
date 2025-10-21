import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from .config import config
from .bot_manager import bot_manager

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class AgroTelegramBot:

    def __init__(self):
        self.application = None
        self.bot_manager = bot_manager

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        user = update.effective_user

        welcome_text = f"""
🌾 *Добро пожаловать в систему обработки сельскохозяйственных данных!*

Привет, {user.first_name}! 👋

Я помогу вам обработать Excel файлы с данными о сельскохозяйственных операциях.

*Как использовать:*
1️⃣ Отправьте Excel файлы (дневные отчеты или оперативную отчетность)
2️⃣ Нажмите кнопку "Обработать файлы"
3️⃣ Получите готовый результат с формулами и сводными таблицами

*Поддерживаемые файлы:*
• Таблица_для_дневного_отчета_*.xlsx
• Оперативная_отчетность_*.xlsx
• Любые другие Excel файлы (.xlsx, .xls)

*Команды:*
/start - Начать работу
/help - Помощь
/history - История обработок
/status - Статус текущей задачи

Готов к работе! 🚀
        """

        keyboard = [
            [InlineKeyboardButton("📁 Загрузить файлы", callback_data="upload_files")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            welcome_text, parse_mode="Markdown", reply_markup=reply_markup
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        help_text = """
❓ *Помощь по использованию бота*

*Основные функции:*
• Загрузка Excel файлов с сельскохозяйственными данными
• Автоматическая обработка и структурирование данных
• Получение готового Excel файла с формулами

*Поддерживаемые форматы:*
• Дневные отчеты: `Таблица_для_дневного_отчета_*.xlsx`
• Оперативная отчетность: `Оперативная_отчетность_*.xlsx`
• Другие Excel файлы: `.xlsx`, `.xls`

*Процесс обработки:*
1. Отправьте один или несколько Excel файлов
2. Нажмите кнопку "Обработать файлы"
3. Дождитесь завершения обработки
4. Скачайте готовый результат

*Команды:*
/start - Начать работу
/help - Эта справка
/history - Показать историю обработок
/status - Статус текущей задачи

*Возможные проблемы:*
• Убедитесь, что FastAPI сервер запущен
• Проверьте формат файлов (только Excel)
• При ошибках попробуйте перезапустить бота
        """

        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        user_id = update.effective_user.id

        try:
            history = await self.bot_manager.get_history(user_id)

            if not history:
                await update.message.reply_text("📊 История обработок пуста.")
                return

            text = "📊 *История обработок:*\n\n"

            for i, job in enumerate(history[:5], 1):  # Показываем последние 5
                status_emoji = {
                    "completed": "✅",
                    "processing": "⏳",
                    "failed": "❌",
                    "pending": "⏸️",
                }.get(job["status"], "❓")

                text += f"{i}. {status_emoji} *Задача #{job['id']}*\n"
                text += f"   📅 {job['created_at'][:19]}\n"
                text += f"   📁 Файлов: {len(job.get('input_files', []))}\n"

                if job["status"] == "completed":
                    text += f"   📊 Записей: {job.get('records_count', 0)}\n"
                    text += f"   🏢 Подразделений: {job.get('departments_count', 0)}\n"
                elif job["status"] == "failed":
                    text += f"   ❌ Ошибка: {job.get('error_message', 'Неизвестная ошибка')}\n"

                text += "\n"

            await update.message.reply_text(text, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Ошибка при получении истории: {e}")
            await update.message.reply_text("❌ Ошибка при получении истории.")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        user_id = update.effective_user.id
        session = self.bot_manager.get_user_session(user_id)

        if not session["current_job_id"]:
            await update.message.reply_text("❌ Нет активных задач.")
            return

        try:
            job_status = await self.bot_manager.get_job_status(user_id)

            if not job_status:
                await update.message.reply_text("❌ Не удалось получить статус задачи.")
                return

            status_emoji = {
                "completed": "✅",
                "processing": "⏳",
                "failed": "❌",
                "pending": "⏸️",
            }.get(job_status["status"], "❓")

            text = f"{status_emoji} *Статус задачи #{job_status['id']}*\n\n"
            text += f"📅 Создана: {job_status['created_at'][:19]}\n"
            text += f"📁 Файлов: {len(job_status.get('input_files', []))}\n"

            if job_status["status"] == "completed":
                text += f"📊 Записей: {job_status.get('records_count', 0)}\n"
                text += f"🏢 Подразделений: {job_status.get('departments_count', 0)}\n"
                text += f"⚙️ Операций: {job_status.get('operations_count', 0)}\n"
                text += f"🌾 Культур: {job_status.get('crops_count', 0)}\n"
                text += "\n✅ *Обработка завершена!*"
            elif job_status["status"] == "processing":
                text += "\n⏳ *Обработка в процессе...*"
            elif job_status["status"] == "failed":
                text += f"\n❌ *Ошибка:* {job_status.get('error_message', 'Неизвестная ошибка')}"
            else:
                text += f"\n⏸️ *Статус:* {job_status['status']}"

            await update.message.reply_text(text, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Ошибка при получении статуса: {e}")
            await update.message.reply_text("❌ Ошибка при получении статуса.")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        user_id = update.effective_user.id
        document = update.message.document

        if not document.file_name.lower().endswith((".xlsx", ".xls")):
            await update.message.reply_text(
                "❌ Поддерживаются только Excel файлы (.xlsx, .xls)"
            )
            return

        try:

            file = await context.bot.get_file(document.file_id)

            with tempfile.NamedTemporaryFile(
                delete=False, suffix=f"_{document.file_name}"
            ) as tmp_file:
                await file.download_to_drive(tmp_file.name)

                self.bot_manager.add_file_to_session(
                    user_id, tmp_file.name, document.file_name
                )

            session = self.bot_manager.get_user_session(user_id)
            files_count = len(session["files"])

            keyboard = [
                [
                    InlineKeyboardButton(
                        "🔄 Обработать файлы", callback_data="process_files"
                    )
                ],
                [InlineKeyboardButton("🗑️ Очистить", callback_data="clear_files")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"✅ Файл *{document.file_name}* загружен!\n\n"
                f"📁 Всего файлов: {files_count}\n\n"
                f"Нажмите кнопку для обработки или загрузите еще файлы.",
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )

        except Exception as e:
            logger.error(f"Ошибка при загрузке файла: {e}")
            await update.message.reply_text("❌ Ошибка при загрузке файла.")

    async def handle_callback_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):

        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id

        if query.data == "upload_files":
            await query.edit_message_text(
                "📁 *Загрузка файлов*\n\n"
                "Отправьте Excel файлы для обработки.\n"
                "Поддерживаются форматы: .xlsx, .xls",
                parse_mode="Markdown",
            )

        elif query.data == "show_history":
            await self.history_command(update, context)

        elif query.data == "show_help":
            await self.help_command(update, context)

        elif query.data == "process_files":
            await self.process_files_callback(query, user_id)

        elif query.data == "clear_files":
            await self.clear_files_callback(query, user_id)

        elif query.data == "download_result":
            await self.download_result_callback(query, user_id)

    async def process_files_callback(self, query, user_id: int):

        session = self.bot_manager.get_user_session(user_id)

        if not session["files"]:
            await query.edit_message_text("❌ Нет файлов для обработки.")
            return

        try:

            await query.edit_message_text("📤 Загружаю файлы на сервер...")

            upload_result = await self.bot_manager.upload_files(user_id)

            if not upload_result:
                await query.edit_message_text("❌ Ошибка при загрузке файлов.")
                return

            await query.edit_message_text("⚙️ Запускаю обработку...")

            process_result = await self.bot_manager.process_files(user_id)

            if not process_result:
                await query.edit_message_text("❌ Ошибка при запуске обработки.")
                return

            keyboard = [
                [
                    InlineKeyboardButton(
                        "📥 Скачать результат", callback_data="download_result"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "✅ *Обработка запущена!*\n\n"
                f"📋 Задача: #{upload_result['job_id']}\n"
                f"📁 Файлов: {len(upload_result['files'])}\n\n"
                "Используйте кнопки для управления:",
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )

        except Exception as e:
            logger.error(f"Ошибка при обработке файлов: {e}")
            await query.edit_message_text("❌ Ошибка при обработке файлов.")

    async def clear_files_callback(self, query, user_id: int):

        await self.bot_manager.cleanup_user_files(user_id)
        self.bot_manager.clear_user_session(user_id)

        await query.edit_message_text("🗑️ Файлы очищены. Можете загружать новые.")

    async def download_result_callback(self, query, user_id: int):

        try:

            job_status = await self.bot_manager.get_job_status(user_id)

            if not job_status:
                await query.edit_message_text("❌ Не удалось получить статус задачи.")
                return

            if job_status["status"] != "completed":
                await query.edit_message_text(
                    f"⏳ Обработка еще не завершена.\n"
                    f"Статус: {job_status['status']}"
                )
                return

            await query.edit_message_text("📥 Скачиваю результат...")

            result_data = await self.bot_manager.download_result(user_id)

            if not result_data:
                await query.edit_message_text("❌ Ошибка при скачивании результата.")
                return

            session = self.bot_manager.get_user_session(user_id)
            job_id = session["current_job_id"]
            filename = f"processed_{job_id}.xlsx"

            await query.message.reply_document(
                document=result_data,
                filename=filename,
                caption=f"✅ *Обработка завершена!*\n\n"
                f"📊 Записей: {job_status.get('records_count', 0)}\n"
                f"🏢 Подразделений: {job_status.get('departments_count', 0)}\n"
                f"⚙️ Операций: {job_status.get('operations_count', 0)}\n"
                f"🌾 Культур: {job_status.get('crops_count', 0)}",
                parse_mode="Markdown",
            )

            self.bot_manager.clear_user_session(user_id)

        except Exception as e:
            logger.error(f"Ошибка при скачивании результата: {e}")
            await query.edit_message_text("❌ Ошибка при скачивании результата.")

    async def check_fastapi_connection(self) -> bool:

        return await self.bot_manager.check_fastapi_health()

    def start_bot(self):

        import requests

        try:
            response = requests.get(f"{config.fastapi_url}/", timeout=5)
            if response.status_code != 200:
                raise Exception("FastAPI недоступен")
        except Exception:
            logger.error("FastAPI сервер недоступен!")
            print("Ошибка: FastAPI сервер недоступен!")
            print("Убедитесь, что веб-сервер запущен:")
            print(
                "   cd src && uvicorn web.app:app --reload --host 127.0.0.1 --port 8000"
            )
            return False

        logger.info("FastAPI сервер доступен")

        self.application = Application.builder().token(config.telegram_token).build()

        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("history", self.history_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(
            MessageHandler(filters.Document.ALL, self.handle_document)
        )
        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))

        logger.info("Запуск Telegram бота...")
        print("Telegram бот запущен!")
        print("Отправьте /start в Telegram для начала работы")

        self.application.run_polling()

        return True

    async def stop_bot(self):

        if self.application:
            await self.application.stop()
        await self.bot_manager.close()


telegram_bot = AgroTelegramBot()
