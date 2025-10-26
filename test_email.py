"""
Скрипт для тестирования настроек email
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from src.web.email_sender import EmailSender


def test_connection():
    """Тестирует подключение к SMTP серверу"""
    print("=" * 60)
    print("Тестирование подключения к SMTP серверу")
    print("=" * 60)
    
    sender = EmailSender()
    
    print(f"\nНастройки:")
    print(f"SMTP Server: {sender.smtp_server}")
    print(f"SMTP Port: {sender.smtp_port}")
    print(f"SMTP User: {sender.smtp_user}")
    print(f"Sender Email: {sender.sender_email}")
    print(f"Password: {'*' * len(sender.smtp_password) if sender.smtp_password else 'НЕ УКАЗАН'}")
    
    if not sender.smtp_user or not sender.smtp_password:
        print("\n❌ ОШИБКА: SMTP учетные данные не настроены!")
        print("\nДля настройки email:")
        print("1. Создайте файл .env в корне проекта")
        print("2. Добавьте в него настройки:")
        print("   SMTP_SERVER=smtp.mail.ru")
        print("   SMTP_PORT=465")
        print("   SMTP_USER=ваш-email@mail.ru")
        print("   SMTP_PASSWORD=ваш-пароль")
        print("   SENDER_EMAIL=ваш-email@mail.ru")
        print("3. Запустите этот скрипт снова")
        return False
    
    print("\n🔄 Проверка подключения...")
    
    if sender.test_connection():
        print("✅ Подключение успешно!")
        print("\nВаши настройки email работают корректно.")
        print("Теперь вы можете использовать автоматическую отправку файлов.")
        return True
    else:
        print("❌ Ошибка подключения!")
        print("\nПроверьте:")
        print("- Правильность введенных данных в .env")
        print("- Для Mail.ru используйте пароль для внешних приложений")
        print("- Для Gmail используйте пароль приложения (порт 587)")
        print("- Убедитесь, что антивирус не блокирует SMTP подключения")
        return False


def send_test_email():
    """Отправляет тестовое письмо"""
    print("\n" + "=" * 60)
    print("Отправка тестового письма")
    print("=" * 60)
    
    recipient = input("\nВведите email получателя для теста: ").strip()
    
    if not recipient or '@' not in recipient:
        print("❌ Некорректный email адрес")
        return False
    
    sender = EmailSender()
    
    # Создаем временный тестовый файл
    test_file = Path(__file__).parent / "test_email_attachment.txt"
    test_file.write_text("Это тестовое письмо от системы обработки сельскохозяйственных данных.", encoding='utf-8')
    
    print(f"\n🔄 Отправка тестового письма на {recipient}...")
    
    success = sender.send_file(
        recipient_email=recipient,
        subject="Тестовое письмо - Система обработки данных",
        body="Это тестовое письмо для проверки настроек email.\n\nЕсли вы получили это письмо, значит настройки работают корректно!",
        file_path=test_file,
        job_info={
            'records_count': 100,
            'departments_count': 5,
            'operations_count': 10,
            'crops_count': 8,
            'input_files': ['test1.xlsx', 'test2.xlsx']
        }
    )
    
    # Удаляем тестовый файл
    test_file.unlink()
    
    if success:
        print("✅ Письмо успешно отправлено!")
        print(f"\nПроверьте почту {recipient}")
        print("Письмо должно содержать вложение и информацию о тестовой обработке.")
        return True
    else:
        print("❌ Ошибка при отправке письма")
        print("Проверьте логи выше для деталей")
        return False


def main():
    """Главная функция"""
    print("\n🌾 Тестирование настроек Email")
    print("Система обработки сельскохозяйственных данных\n")
    
    # Тестируем подключение
    if not test_connection():
        sys.exit(1)
    
    # Спрашиваем, отправить ли тестовое письмо
    print("\n" + "-" * 60)
    answer = input("\nОтправить тестовое письмо? (y/n): ").strip().lower()
    
    if answer in ['y', 'yes', 'д', 'да']:
        send_test_email()
    else:
        print("\nТестирование завершено.")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nТестирование прервано пользователем")
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()

