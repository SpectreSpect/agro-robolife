import os
import sys
import subprocess
from pathlib import Path
import socket
import ssl
import pprint
import time

def ensure_certifi_and_set_env():
    try:
        import certifi
    except Exception:
        print("certifi не найден. Пытаюсь установить пакет certifi...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "certifi"])
            time.sleep(0.5)
            import certifi
        except Exception as exc:
            print("Не удалось установить certifi автоматически.")
            print("Пожалуйста, установите его вручную: python -m pip install certifi")
            print("Ошибка установки:", exc)
            return False

    try:
        import certifi as _certifi
        cafile = _certifi.where()
        os.environ.setdefault("SSL_CERT_FILE", cafile)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", cafile)
        print(f"Использую CA-bundle от certifi: {cafile}")
        return True
    except Exception as exc:
        print("Ошибка при установке SSL_CERT_FILE:", exc)
        return False


_ok = ensure_certifi_and_set_env()

sys.path.append(str(Path(__file__).parent))

try:
    from src.web.email_sender import EmailSender
except Exception as exc:
    print("\n❌ Не удалось импортировать EmailSender из src.web.email_sender.")
    print("Убедитесь, что файл существует и путь настроен правильно.")
    print("Ошибка:", exc)
    raise

def inspect_smtp_certificate(host: str, port: int = 465):
    try:
        s = socket.create_connection((host, port), timeout=10)
        ctx = ssl._create_unverified_context()
        ss = ctx.wrap_socket(s, server_hostname=host)
        cert = ss.getpeercert()
        ss.close()
        return cert
    except Exception as exc:
        return {"error": str(exc)}

def test_connection():
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
    
    try:
        ok = sender.test_connection()
    except Exception as exc:
        print(f"\nОшибка при попытке тестового подключения: {exc}")
        ok = False

    if ok:
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
        
        try:
            print("\n🔍 Диагностика сертификата, получаемого от сервера:")
            cert = inspect_smtp_certificate(sender.smtp_server, int(sender.smtp_port))
            if cert is None:
                print("Не удалось получить сертификат (alloc/timeout).")
            elif "error" in cert:
                print("Ошибка при получении сертификата:", cert["error"])
            else:
                subject = cert.get("subject")
                issuer = cert.get("issuer")
                notBefore = cert.get("notBefore")
                notAfter = cert.get("notAfter")
                print("Subject:")
                pprint.pprint(subject)
                print("\nIssuer:")
                pprint.pprint(issuer)
                print(f"\nПериод действия: {notBefore}  —  {notAfter}")
                print("\nЕсли в поле Issuer вы видите имя типа 'Kaspersky', 'Dr.Web', 'YourCompany CA' и т.п.,")
                print("то, скорее всего, на сервере происходит TLS-inspection / перехват трафика (MITM).")
                print("В этом случае нужно отключить TLS-inspection либо добавить внутренний CA в доверенные.")
        except Exception as exc:
            print("Не удалось выполнить диагностику сертификата:", exc)

        return False


def send_test_email():
    print("\n" + "=" * 60)
    print("Отправка тестового письма")
    print("=" * 60)
    
    recipient = input("\nВведите email получателя для теста: ").strip()
    
    if not recipient or '@' not in recipient:
        print("❌ Некорректный email адрес")
        return False
    
    sender = EmailSender()
    
    test_file = Path(__file__).parent / "test_email_attachment.txt"
    test_file.write_text("Это тестовое письмо от системы обработки сельскохозяйственных данных.", encoding='utf-8')
    
    print(f"\n🔄 Отправка тестового письма на {recipient}...")
    
    try:
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
    except Exception as exc:
        print("Ошибка при попытке отправки (исключение):", exc)
        success = False
    
    try:
        if test_file.exists():
            test_file.unlink()
    except Exception:
        pass
    
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
    print("\n🌾 Тестирование настроек Email")
    print("Система обработки сельскохозяйственных данных\n")
    
    if not test_connection():
        sys.exit(1)
    
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
