import asyncio
import logging
from typing import Dict, List, Optional, Any
import httpx
from pathlib import Path
import tempfile
import os

from .config import config

logger = logging.getLogger(__name__)


class BotManager:
    """Менеджер для взаимодействия Telegram бота с FastAPI сервером"""

    def __init__(self):
        self.fastapi_url = config.fastapi_url
        self.http_client = httpx.AsyncClient(timeout=600.0)

    async def check_fastapi_health(self) -> bool:
        """Проверка доступности FastAPI сервера"""
        try:
            response = await self.http_client.get(f"{self.fastapi_url}/")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"FastAPI недоступен: {e}")
            return False

    async def get_files_list(self) -> Optional[List[Dict[str, Any]]]:
        """Получить список файлов из shared_files"""
        try:
            response = await self.http_client.get(f"{self.fastapi_url}/api/files")

            if response.status_code == 200:
                result = response.json()
                return result.get("files", [])
            else:
                logger.error(f"Ошибка получения списка файлов: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Ошибка при получении списка файлов: {e}")
            return None

    async def upload_file_to_shared(self, file_path: str, filename: str) -> bool:
        """Загрузить файл в shared_files через API"""
        try:
            with open(file_path, "rb") as f:
                files = [
                    (
                        "files",
                        (
                            filename,
                            f.read(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        ),
                    )
                ]

            response = await self.http_client.post(
                f"{self.fastapi_url}/api/files/upload", files=files
            )

            if response.status_code == 200:
                logger.info(f"Файл {filename} загружен в shared_files")
                return True
            else:
                logger.error(f"Ошибка загрузки файла: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Ошибка при загрузке файла: {e}")
            return False

    async def delete_file_from_shared(self, filename: str) -> bool:
        """Удалить файл из shared_files через API"""
        try:
            response = await self.http_client.delete(
                f"{self.fastapi_url}/api/files/{filename}"
            )

            if response.status_code == 200:
                logger.info(f"Файл {filename} удален из shared_files")
                return True
            else:
                logger.error(f"Ошибка удаления файла: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Ошибка при удалении файла: {e}")
            return False

    async def get_schedule_countdown(self) -> Optional[Dict[str, Any]]:
        """Получить информацию о расписании и обратный отсчёт"""
        try:
            response = await self.http_client.get(
                f"{self.fastapi_url}/api/schedule/countdown"
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка получения расписания: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Ошибка при получении расписания: {e}")
            return None

    async def get_schedule_info(self) -> Optional[Dict[str, Any]]:
        """Получить полную информацию о расписании"""
        try:
            response = await self.http_client.get(
                f"{self.fastapi_url}/api/schedule"
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка получения информации о расписании: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Ошибка при получении информации о расписании: {e}")
            return None

    async def close(self):
        """Закрыть HTTP клиент"""
        await self.http_client.aclose()


bot_manager = BotManager()
