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

    def __init__(self):
        self.fastapi_url = config.fastapi_url
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
        self.http_client = httpx.AsyncClient(timeout=600.0)

    async def check_fastapi_health(self) -> bool:

        try:
            response = await self.http_client.get(f"{self.fastapi_url}/")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"FastAPI недоступен: {e}")
            return False

    def get_user_session(self, user_id: int) -> Dict[str, Any]:

        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                "files": [],
                "current_job_id": None,
                "state": "idle",
            }
        return self.user_sessions[user_id]

    def add_file_to_session(self, user_id: int, file_path: str, filename: str):

        session = self.get_user_session(user_id)
        session["files"].append({"path": file_path, "filename": filename})
        logger.info(f"Добавлен файл {filename} для пользователя {user_id}")

    def clear_user_session(self, user_id: int):

        if user_id in self.user_sessions:

            for file_info in self.user_sessions[user_id]["files"]:
                try:
                    os.unlink(file_info["path"])
                except:
                    pass
            del self.user_sessions[user_id]
            logger.info(f"Сессия пользователя {user_id} очищена")

    async def upload_files(self, user_id: int) -> Optional[Dict[str, Any]]:

        session = self.get_user_session(user_id)

        if not session["files"]:
            return None

        try:

            files = []
            for file_info in session["files"]:
                with open(file_info["path"], "rb") as f:
                    files.append(
                        (
                            "files",
                            (
                                file_info["filename"],
                                f.read(),
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            ),
                        )
                    )

            response = await self.http_client.post(
                f"{self.fastapi_url}/api/upload", files=files
            )

            if response.status_code == 200:
                result = response.json()
                session["current_job_id"] = result["job_id"]
                session["state"] = "uploaded"
                logger.info(
                    f"Файлы загружены для пользователя {user_id}, job_id: {result['job_id']}"
                )
                return result
            else:
                logger.error(f"Ошибка загрузки файлов: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Ошибка при загрузке файлов: {e}")
            return None

    async def process_files(self, user_id: int) -> Optional[Dict[str, Any]]:

        session = self.get_user_session(user_id)

        if not session["current_job_id"]:
            return None

        try:
            response = await self.http_client.post(
                f"{self.fastapi_url}/api/process/{session['current_job_id']}"
            )

            if response.status_code == 200:
                result = response.json()
                session["state"] = "processing"
                logger.info(f"Обработка запущена для пользователя {user_id}")
                return result
            else:
                logger.error(f"Ошибка запуска обработки: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Ошибка при запуске обработки: {e}")
            return None

    async def get_job_status(self, user_id: int) -> Optional[Dict[str, Any]]:

        session = self.get_user_session(user_id)

        if not session["current_job_id"]:
            return None

        try:
            response = await self.http_client.get(
                f"{self.fastapi_url}/api/job/{session['current_job_id']}"
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка получения статуса: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Ошибка при получении статуса: {e}")
            return None

    async def download_result(self, user_id: int) -> Optional[bytes]:

        session = self.get_user_session(user_id)

        if not session["current_job_id"]:
            return None

        try:
            response = await self.http_client.get(
                f"{self.fastapi_url}/api/download/{session['current_job_id']}"
            )

            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"Ошибка скачивания: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Ошибка при скачивании: {e}")
            return None

    async def get_history(self, user_id: int) -> List[Dict[str, Any]]:

        try:
            response = await self.http_client.get(f"{self.fastapi_url}/api/history")

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка получения истории: {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"Ошибка при получении истории: {e}")
            return []

    async def cleanup_user_files(self, user_id: int):

        session = self.get_user_session(user_id)

        for file_info in session["files"]:
            try:
                os.unlink(file_info["path"])
            except:
                pass

        session["files"] = []

    async def close(self):

        await self.http_client.aclose()


bot_manager = BotManager()
