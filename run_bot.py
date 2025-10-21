import asyncio
import sys
import signal
from pathlib import Path

sys.path.append(str(Path(__file__).parent / "src"))

from src.bot.telegram_bot import telegram_bot
from src.bot.config import config


def signal_handler(signum, frame):

    print("\nПолучен сигнал остановки...")
    sys.exit(0)


def main():

    print("Система обработки сельскохозяйственных данных - Telegram Bot")
    print("=" * 60)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:

        print(f"Конфигурация: {config}")
        print(f"FastAPI URL: {config.fastapi_url}")
        print()

        telegram_bot.start_bot()

    except KeyboardInterrupt:
        print("\nОстановка по запросу пользователя...")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        return 1
    finally:
        print("Бот остановлен")

    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nДо свидания!")
        sys.exit(0)
