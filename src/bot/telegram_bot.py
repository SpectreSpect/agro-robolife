import asyncio
import logging
import tempfile
import os
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
import pytz

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
        # Хранилище для соответствия индекс -> имя файла (для callback_data)
        self.file_index_cache = {}
        # Хранилище для текущей страницы пользователя
        self.user_page = {}
        # Количество файлов на странице
        self.files_per_page = 5

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start - приветствие с кнопками управления"""
        user = update.effective_user

        welcome_text = f"""
🌾 *Добро пожаловать в систему обработки сельскохозяйственных данных!*

Привет, {user.first_name}! 👋

Я помогу вам управлять Excel файлами для автоматической генерации отчетов.

*Что я умею:*
📁 Загружать файлы в систему
🗑️ Удалять файлы
📅 Показывать расписание генерации отчетов

*Как использовать:*
1️⃣ Отправьте Excel файлы (.xlsx, .xls)
2️⃣ Файлы автоматически загрузятся в систему
3️⃣ Администратор настроит расписание генерации
4️⃣ Отчеты будут создаваться автоматически

*Поддерживаемые файлы:*
• Таблица_для_дневного_отчета_*.xlsx
• Оперативная_отчетность_*.xlsx
• Любые другие Excel файлы (.xlsx, .xls)

*Команды:*
/files - Список загруженных файлов
/schedule - Расписание генерации
/help - Подробная справка

Готов к работе! 🚀
        """

        keyboard = [
            [InlineKeyboardButton("📁 Список файлов", callback_data="show_files")],
            [InlineKeyboardButton("📅 Расписание", callback_data="show_schedule")],
            [InlineKeyboardButton("❓ Помощь", callback_data="show_help")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            welcome_text, parse_mode="Markdown", reply_markup=reply_markup
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help - справка по использованию"""
        help_text = """
❓ *Помощь по использованию бота*

*Основные функции:*
• Загрузка файлов в систему для обработки
• Просмотр списка загруженных файлов
• Удаление файлов из системы
• Просмотр расписания автоматической генерации отчетов

*Поддерживаемые форматы:*
• Дневные отчеты: `Таблица_для_дневного_отчета_*.xlsx`
• Оперативная отчетность: `Оперативная_отчетность_*.xlsx`
• Другие Excel файлы: `.xlsx`, `.xls`

*Как работает система:*
1. Вы загружаете Excel файлы через бота
2. Файлы сохраняются в общей папке системы
3. Администратор настраивает расписание генерации
4. Система автоматически создает отчеты по расписанию
5. Готовые отчеты отправляются на email

*Команды:*
/start - Главное меню
/files - Список загруженных файлов
/schedule - Расписание генерации отчетов
/help - Эта справка

*Загрузка файлов:*
Просто отправьте Excel файл боту, он автоматически загрузится в систему.

*Управление файлами:*
Используйте команду /files для просмотра и удаления файлов.

*Расписание:*
Команда /schedule покажет, когда будет следующая генерация отчета.
        """

        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def files_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /files - показать список загруженных файлов"""
        user_id = update.effective_user.id
        # Сбрасываем на первую страницу при новом запросе
        self.user_page[user_id] = 0
        await self._show_files_page(update.message, user_id)

    async def _show_files_page(self, message, user_id: int, edit_mode: bool = False):
        """Внутренняя функция для отображения страницы со списком файлов"""
        try:
            files_list = await self.bot_manager.get_files_list()

            if files_list is None:
                text = "❌ Ошибка при получении списка файлов."
                if edit_mode:
                    await message.edit_text(text)
                else:
                    await message.reply_text(text)
                return

            if not files_list:
                text = "📁 *Список файлов пуст*\n\n" \
                       "Отправьте Excel файлы боту для загрузки в систему."
                if edit_mode:
                    await message.edit_text(text, parse_mode="Markdown")
                else:
                    await message.reply_text(text, parse_mode="Markdown")
                return

            # Получаем текущую страницу
            current_page = self.user_page.get(user_id, 0)
            total_files = len(files_list)
            total_pages = (total_files + self.files_per_page - 1) // self.files_per_page
            
            # Проверяем границы
            if current_page < 0:
                current_page = 0
            if current_page >= total_pages:
                current_page = total_pages - 1
            
            self.user_page[user_id] = current_page
            
            # Вычисляем диапазон файлов для текущей страницы
            start_idx = current_page * self.files_per_page
            end_idx = min(start_idx + self.files_per_page, total_files)
            
            # Формируем текст
            text = f"📁 *Загруженные файлы ({total_files})*\n"
            text += f"_Страница {current_page + 1} из {total_pages}_\n\n"
            
            # Сохраняем соответствие индекс -> имя файла для этого пользователя
            if user_id not in self.file_index_cache:
                self.file_index_cache[user_id] = {}
            
            keyboard = []
            
            # Показываем файлы текущей страницы
            for i in range(start_idx, end_idx):
                file = files_list[i]
                file_num = i + 1  # Номер файла (начиная с 1)
                
                # Форматируем размер файла
                size_kb = file['size'] / 1024
                if size_kb < 1024:
                    size_str = f"{size_kb:.1f} KB"
                else:
                    size_str = f"{size_kb/1024:.1f} MB"
                
                # Форматируем дату
                modified_dt = datetime.fromisoformat(file['modified'].replace('Z', '+00:00'))
                date_str = modified_dt.strftime("%d.%m.%Y %H:%M")
                
                text += f"{file_num}. `{file['name']}`\n"
                text += f"   📊 Размер: {size_str}\n"
                text += f"   📅 Изменен: {date_str}\n\n"
                
                # Сохраняем имя файла по индексу
                self.file_index_cache[user_id][file_num] = file['name']
                
                # Кнопка удаления с индексом
                keyboard.append([
                    InlineKeyboardButton(
                        f"🗑️ {file_num}. {file['name'][:25]}...", 
                        callback_data=f"delete_file:{file_num}"
                    )
                ])
            
            # Добавляем кнопки навигации
            nav_buttons = []
            if current_page > 0:
                nav_buttons.append(
                    InlineKeyboardButton("◀️ Назад", callback_data="files_prev")
                )
            if current_page < total_pages - 1:
                nav_buttons.append(
                    InlineKeyboardButton("Вперёд ▶️", callback_data="files_next")
                )
            
            if nav_buttons:
                keyboard.append(nav_buttons)
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if edit_mode:
                await message.edit_text(text, parse_mode="Markdown", reply_markup=reply_markup)
            else:
                await message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

        except Exception as e:
            logger.error(f"Ошибка при получении списка файлов: {e}")
            text = "❌ Ошибка при получении списка файлов."
            if edit_mode:
                await message.edit_text(text)
            else:
                await message.reply_text(text)

    async def schedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /schedule - показать расписание генерации"""
        try:
            countdown = await self.bot_manager.get_schedule_countdown()
            schedule_info = await self.bot_manager.get_schedule_info()

            if countdown is None or schedule_info is None:
                await update.message.reply_text("❌ Ошибка при получении информации о расписании.")
                return

            if not countdown.get("active", False):
                await update.message.reply_text(
                    "📅 *Расписание генерации*\n\n"
                    "❌ Расписание не установлено\n\n"
                    "Администратор может настроить автоматическую генерацию отчетов через веб-интерфейс.",
                    parse_mode="Markdown"
                )
                return

            # Формируем информацию о расписании
            text = "📅 *Расписание генерации отчетов*\n\n"
            
            # Московский часовой пояс
            moscow_tz = pytz.timezone('Europe/Moscow')
            
            schedule_type = countdown.get("type")
            
            if schedule_type == "one_time":
                text += "🔄 Тип: Разовая генерация\n"
                scheduled_time = countdown.get("scheduled_time")
                if scheduled_time:
                    try:
                        # Парсим дату, убираем 'Z' и добавляем timezone
                        if 'T' in scheduled_time:
                            dt_utc = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                        else:
                            # Если формат без T, пробуем другой парсинг
                            dt_utc = datetime.fromisoformat(scheduled_time)
                        # Конвертируем в московское время
                        dt_moscow = dt_utc.astimezone(moscow_tz)
                        text += f"📆 Запланировано: {dt_moscow.strftime('%d.%m.%Y %H:%M')} МСК\n"
                    except Exception as e:
                        logger.error(f"Ошибка парсинга scheduled_time '{scheduled_time}': {e}")
                        text += f"📆 Запланировано: {scheduled_time}\n"
                
                # Проверяем статус задачи
                if countdown.get("expired"):
                    if countdown.get("is_enabled"):
                        text += "⚠️ Время выполнения прошло (задача ещё активна)\n"
                    else:
                        text += "✅ Задача выполнена\n"
                elif not countdown.get("is_enabled"):
                    text += "❌ Задача отключена\n"
            elif schedule_type == "periodic":
                text += "🔄 Тип: Периодическая генерация\n"
                periodic_time = countdown.get("periodic_time")
                if periodic_time:
                    # Парсим UTC время и конвертируем в МСК
                    try:
                        utc_hour, utc_minute = map(int, periodic_time.split(":"))
                        # Создаем время в UTC
                        utc_time = datetime.now(pytz.utc).replace(hour=utc_hour, minute=utc_minute, second=0, microsecond=0)
                        # Конвертируем в московское время
                        msk_time = utc_time.astimezone(moscow_tz)
                        text += f"⏰ Время: {msk_time.strftime('%H:%M')} МСК (ежедневно)\n"
                    except:
                        text += f"⏰ Время: {periodic_time} UTC (ежедневно)\n"
            
            # Email получателя
            if schedule_info.get("recipient_email"):
                text += f"📧 Email: {schedule_info['recipient_email']}\n"
            
            # Обратный отсчёт
            seconds_left = countdown.get("seconds_left", 0)
            if seconds_left > 0:
                hours = seconds_left // 3600
                minutes = (seconds_left % 3600) // 60
                text += f"\n⏳ До генерации: {int(hours)} ч. {int(minutes)} мин.\n"
            
            # Последний запуск
            if schedule_info.get("last_run"):
                try:
                    last_run_utc = datetime.fromisoformat(schedule_info["last_run"].replace('Z', '+00:00'))
                    last_run_moscow = last_run_utc.astimezone(moscow_tz)
                    text += f"✅ Последний запуск: {last_run_moscow.strftime('%d.%m.%Y %H:%M')} МСК\n"
                except Exception as e:
                    logger.error(f"Ошибка парсинга last_run: {e}")

            logger.info(f"Отправляем сообщение о расписании: {repr(text)}")
            await update.message.reply_text(text, parse_mode="Markdown")
            logger.info("Сообщение отправлено успешно")

        except Exception as e:
            logger.error(f"Ошибка при получении расписания: {e}", exc_info=True)
            await update.message.reply_text("❌ Ошибка при получении расписания.")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка загруженного документа - сразу загружаем в shared_files"""
        document = update.message.document

        if not document.file_name.lower().endswith((".xlsx", ".xls")):
            await update.message.reply_text(
                "❌ Поддерживаются только Excel файлы (.xlsx, .xls)"
            )
            return

        try:
            # Скачиваем файл во временную директорию
            file = await context.bot.get_file(document.file_id)

            with tempfile.NamedTemporaryFile(
                delete=False, suffix=f"_{document.file_name}"
            ) as tmp_file:
                await file.download_to_drive(tmp_file.name)
                tmp_path = tmp_file.name

            # Загружаем файл в shared_files через API
            success = await self.bot_manager.upload_file_to_shared(
                tmp_path, document.file_name
            )

            # Удаляем временный файл
            try:
                os.unlink(tmp_path)
            except:
                pass

            if success:
                # Получаем обновленный список файлов
                files_list = await self.bot_manager.get_files_list()
                files_count = len(files_list) if files_list else 0

                keyboard = [
                    [InlineKeyboardButton("📁 Список файлов", callback_data="show_files")],
                    [InlineKeyboardButton("📅 Расписание", callback_data="show_schedule")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_text(
                    f"✅ Файл *{document.file_name}* загружен в систему!\n\n"
                    f"📁 Всего файлов в системе: {files_count}\n\n"
                    f"Файл будет обработан автоматически согласно расписанию.",
                parse_mode="Markdown",
                reply_markup=reply_markup,
            )
            else:
                await update.message.reply_text("❌ Ошибка при загрузке файла в систему.")

        except Exception as e:
            logger.error(f"Ошибка при загрузке файла: {e}")
            await update.message.reply_text("❌ Ошибка при загрузке файла.")

    async def handle_callback_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Обработка callback кнопок"""
        query = update.callback_query
        await query.answer()

        if query.data == "show_files":
            await self.show_files_callback(query)

        elif query.data == "show_schedule":
            await self.show_schedule_callback(query)

        elif query.data == "show_help":
            await self.show_help_callback(query)

        elif query.data == "files_prev":
            await self.files_prev_callback(query)

        elif query.data == "files_next":
            await self.files_next_callback(query)

        elif query.data.startswith("delete_file:"):
            file_index = query.data.split(":", 1)[1]
            await self.delete_file_callback(query, file_index)

    async def show_files_callback(self, query):
        """Callback для показа списка файлов"""
        user_id = query.from_user.id
        # Сбрасываем на первую страницу
        self.user_page[user_id] = 0
        await self._show_files_page(query.message, user_id, edit_mode=True)

    async def files_prev_callback(self, query):
        """Callback для перехода на предыдущую страницу"""
        user_id = query.from_user.id
        current_page = self.user_page.get(user_id, 0)
        if current_page > 0:
            self.user_page[user_id] = current_page - 1
        await self._show_files_page(query.message, user_id, edit_mode=True)

    async def files_next_callback(self, query):
        """Callback для перехода на следующую страницу"""
        user_id = query.from_user.id
        current_page = self.user_page.get(user_id, 0)
        self.user_page[user_id] = current_page + 1
        await self._show_files_page(query.message, user_id, edit_mode=True)

    async def show_schedule_callback(self, query):
        """Callback для показа расписания"""
        try:
            countdown = await self.bot_manager.get_schedule_countdown()
            schedule_info = await self.bot_manager.get_schedule_info()

            if countdown is None or schedule_info is None:
                await query.edit_message_text("❌ Ошибка при получении информации о расписании.")
                return

            if not countdown.get("active", False):
                await query.edit_message_text(
                    "📅 *Расписание генерации*\n\n"
                    "❌ Расписание не установлено\n\n"
                    "Администратор может настроить автоматическую генерацию отчетов через веб-интерфейс.",
                    parse_mode="Markdown"
                )
                return

            # Формируем информацию о расписании
            text = "📅 *Расписание генерации отчетов*\n\n"
            
            # Московский часовой пояс
            moscow_tz = pytz.timezone('Europe/Moscow')
            
            schedule_type = countdown.get("type")
            if schedule_type == "one_time":
                text += "🔄 Тип: Разовая генерация\n"
                scheduled_time = countdown.get("scheduled_time")
                if scheduled_time:
                    try:
                        # Парсим дату, убираем 'Z' и добавляем timezone
                        if 'T' in scheduled_time:
                            dt_utc = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
                        else:
                            # Если формат без T, пробуем другой парсинг
                            dt_utc = datetime.fromisoformat(scheduled_time)
                        # Конвертируем в московское время
                        dt_moscow = dt_utc.astimezone(moscow_tz)
                        text += f"📆 Запланировано: {dt_moscow.strftime('%d.%m.%Y %H:%M')} МСК\n"
                    except Exception as e:
                        logger.error(f"Ошибка парсинга scheduled_time '{scheduled_time}': {e}")
                        text += f"📆 Запланировано: {scheduled_time}\n"
                
                # Проверяем статус задачи
                if countdown.get("expired"):
                    if countdown.get("is_enabled"):
                        text += "⚠️ Время выполнения прошло (задача ещё активна)\n"
                    else:
                        text += "✅ Задача выполнена\n"
                elif not countdown.get("is_enabled"):
                    text += "❌ Задача отключена\n"
            elif schedule_type == "periodic":
                text += "🔄 Тип: Периодическая генерация\n"
                periodic_time = countdown.get("periodic_time")
                if periodic_time:
                    # Парсим UTC время и конвертируем в МСК
                    try:
                        utc_hour, utc_minute = map(int, periodic_time.split(":"))
                        # Создаем время в UTC
                        utc_time = datetime.now(pytz.utc).replace(hour=utc_hour, minute=utc_minute, second=0, microsecond=0)
                        # Конвертируем в московское время
                        msk_time = utc_time.astimezone(moscow_tz)
                        text += f"⏰ Время: {msk_time.strftime('%H:%M')} МСК (ежедневно)\n"
                    except:
                        text += f"⏰ Время: {periodic_time} UTC (ежедневно)\n"
            
            # Email получателя
            if schedule_info.get("recipient_email"):
                text += f"📧 Email: {schedule_info['recipient_email']}\n"
            
            # Обратный отсчёт
            seconds_left = countdown.get("seconds_left", 0)
            if seconds_left > 0:
                hours = seconds_left // 3600
                minutes = (seconds_left % 3600) // 60
                text += f"\n⏳ До генерации: {int(hours)} ч. {int(minutes)} мин.\n"
            
            # Последний запуск
            if schedule_info.get("last_run"):
                try:
                    last_run_utc = datetime.fromisoformat(schedule_info["last_run"].replace('Z', '+00:00'))
                    last_run_moscow = last_run_utc.astimezone(moscow_tz)
                    text += f"✅ Последний запуск: {last_run_moscow.strftime('%d.%m.%Y %H:%M')} МСК\n"
                except Exception as e:
                    logger.error(f"Ошибка парсинга last_run: {e}")

            logger.info(f"Отправляем сообщение о расписании (callback): {text}")
            await query.edit_message_text(text, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Ошибка при получении расписания: {e}", exc_info=True)
            await query.edit_message_text("❌ Ошибка при получении расписания.")

    async def show_help_callback(self, query):
        """Callback для показа справки"""
        help_text = """
❓ *Помощь по использованию бота*

*Основные функции:*
• Загрузка файлов в систему для обработки
• Просмотр списка загруженных файлов
• Удаление файлов из системы
• Просмотр расписания автоматической генерации отчетов

*Поддерживаемые форматы:*
• Дневные отчеты: `Таблица_для_дневного_отчета_*.xlsx`
• Оперативная отчетность: `Оперативная_отчетность_*.xlsx`
• Другие Excel файлы: `.xlsx`, `.xls`

*Как работает система:*
1. Вы загружаете Excel файлы через бота
2. Файлы сохраняются в общей папке системы
3. Администратор настраивает расписание генерации
4. Система автоматически создает отчеты по расписанию
5. Готовые отчеты отправляются на email

*Команды:*
/start - Главное меню
/files - Список загруженных файлов
/schedule - Расписание генерации отчетов
/help - Эта справка
        """

        await query.edit_message_text(help_text, parse_mode="Markdown")

    async def delete_file_callback(self, query, file_index: str):
        """Callback для удаления файла"""
        try:
            user_id = query.from_user.id
            file_idx = int(file_index)
            
            # Получаем имя файла из кеша
            if user_id not in self.file_index_cache or file_idx not in self.file_index_cache[user_id]:
                await query.answer("❌ Файл не найден. Обновите список файлов.", show_alert=True)
                return

            filename = self.file_index_cache[user_id][file_idx]
            
            success = await self.bot_manager.delete_file_from_shared(filename)

            if success:
                await query.answer(f"✅ Файл удален")
                
                # Проверяем, не стала ли текущая страница пустой
                files_list = await self.bot_manager.get_files_list()
                if files_list:
                    current_page = self.user_page.get(user_id, 0)
                    total_files = len(files_list)
                    total_pages = (total_files + self.files_per_page - 1) // self.files_per_page
                    
                    # Если текущая страница стала больше максимальной, переходим на предыдущую
                    if current_page >= total_pages and current_page > 0:
                        self.user_page[user_id] = total_pages - 1
                
                # Показываем обновленный список файлов (текущую или предыдущую страницу)
                await self._show_files_page(query.message, user_id, edit_mode=True)
            else:
                await query.answer("❌ Ошибка при удалении файла", show_alert=True)

        except ValueError:
            await query.answer("❌ Некорректный индекс файла", show_alert=True)
        except Exception as e:
            logger.error(f"Ошибка при удалении файла: {e}")
            await query.answer("❌ Ошибка при удалении файла", show_alert=True)

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

        # Регистрируем команды
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("files", self.files_command))
        self.application.add_handler(CommandHandler("schedule", self.schedule_command))
        
        # Обработчик документов
        self.application.add_handler(
            MessageHandler(filters.Document.ALL, self.handle_document)
        )
        
        # Обработчик callback кнопок
        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))

        logger.info("Запуск Telegram бота...")
        print("Telegram бот запущен!")
        print("Отправьте /start в Telegram для начала работы")
        print("\nДоступные команды:")
        print("  /start - Главное меню")
        print("  /files - Список загруженных файлов")
        print("  /schedule - Расписание генерации")
        print("  /help - Справка")

        self.application.run_polling()

        return True

    async def stop_bot(self):

        if self.application:
            await self.application.stop()
        await self.bot_manager.close()


telegram_bot = AgroTelegramBot()
