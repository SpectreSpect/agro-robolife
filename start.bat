@echo off
chcp 65001 >nul
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║  🌾 Система обработки сельскохозяйственных данных             ║
echo ║                                                                 ║
echo ║  Запуск веб-приложения...                                      ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

REM Проверка активации виртуального окружения
if exist .venv\Scripts\activate.bat (
    echo ✓ Активация виртуального окружения...
    call .venv\Scripts\activate.bat
    
    echo ✓ Проверка certifi для SSL...
    python -c "import certifi" 2>nul
    if errorlevel 1 (
        echo Установка certifi...
        pip install certifi --quiet
    )
) else (
    echo ⚠ Виртуальное окружение не найдено!
    echo.
    echo Создание виртуального окружения...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo.
    echo Установка зависимостей...
    pip install -r src\requirements.txt
    echo.
)

REM Проверка наличия .env файла
if not exist .env (
    echo.
    echo ╔════════════════════════════════════════════════════════════════╗
    echo ║  ⚠ Настройка Email не обнаружена                              ║
    echo ╚════════════════════════════════════════════════════════════════╝
    echo.
    echo Для использования автоматической отправки по email:
    echo 1. Скопируйте файл env_example.txt в .env
    echo 2. Отредактируйте .env и укажите настройки вашего email
    echo 3. Подробная инструкция в файле README_EMAIL_SETUP.md
    echo.
    echo Вы можете продолжить без email (файлы можно скачивать вручную^)
    echo.
    pause
)

echo.
echo ✓ Запуск приложения...
echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║  Приложение запущено!                                          ║
echo ║                                                                 ║
echo ║  Откройте в браузере: http://localhost:8000                   ║
echo ║                                                                 ║
echo ║  Для остановки нажмите Ctrl+C                                 ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

python app.py

pause

