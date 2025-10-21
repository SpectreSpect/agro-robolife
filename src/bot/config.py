import os
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent
env_path = project_root / ".env"

if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                if line.startswith('\ufeff'):
                    line = line[1:]
                key, value = line.split('=', 1)
                os.environ[key] = value


class Config:

    def __init__(self):
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.fastapi_url = os.getenv("FASTAPI_BASE_URL", "http://127.0.0.1:8000")

        if not self.telegram_token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN не найден в переменных окружения.\n"
                "Создайте файл .env и добавьте:\n"
                "TELEGRAM_BOT_TOKEN=your_token_here"
            )

        if not self.telegram_token.startswith(
            ("1", "2", "3", "4", "5", "6", "7", "8", "9")
        ):
            raise ValueError(
                "Неверный формат TELEGRAM_BOT_TOKEN.\n"
                "Токен должен начинаться с цифры."
            )

    def __str__(self):
        return f"Config(telegram_token=***, fastapi_url={self.fastapi_url})"


config = Config()
