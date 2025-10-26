import smtplib
import ssl
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
except ImportError:
    logger.warning("certifi не установлен, используются системные сертификаты")

class EmailSender:
    def __init__(
        self,
        smtp_server: str = None,
        smtp_port: int = None,
        smtp_user: str = None,
        smtp_password: str = None,
        sender_email: str = None
    ):
        self.smtp_server = smtp_server or os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = smtp_user or os.getenv("SMTP_USER", "")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD", "")
        self.sender_email = sender_email or os.getenv("SENDER_EMAIL", self.smtp_user)
        
        self._setup_ssl_context()
    
    def _setup_ssl_context(self):
        try:
            import certifi
            self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            self.ssl_context = ssl.create_default_context()
    
    def send_file(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        file_path: Path,
        job_info: dict = None
    ) -> bool:
        try:
            if not self.smtp_user or not self.smtp_password:
                logger.error("SMTP учетные данные не настроены")
                logger.info(
                    "Установите переменные окружения: SMTP_SERVER, SMTP_PORT, "
                    "SMTP_USER, SMTP_PASSWORD, SENDER_EMAIL"
                )
                return False
            
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            msg['Subject'] = subject
            
            if job_info:
                body_with_info = f"{body}\n\n"
                body_with_info += "Информация об обработке:\n"
                body_with_info += f"- Обработано записей: {job_info.get('records_count', 0)}\n"
                body_with_info += f"- Подразделений: {job_info.get('departments_count', 0)}\n"
                body_with_info += f"- Операций: {job_info.get('operations_count', 0)}\n"
                body_with_info += f"- Культур: {job_info.get('crops_count', 0)}\n"
                body_with_info += f"- Обработано файлов: {len(job_info.get('input_files', []))}\n"
                msg.attach(MIMEText(body_with_info, 'plain', 'utf-8'))
            else:
                msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            if file_path.exists():
                with open(file_path, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())
                
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {file_path.name}",
                )
                msg.attach(part)
            else:
                logger.error(f"Файл не найден: {file_path}")
                return False
            
            logger.info(f"Подключение к SMTP серверу {self.smtp_server}:{self.smtp_port}")
            
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=self.ssl_context, timeout=15) as server:
                    server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15) as server:
                    server.starttls(context=self.ssl_context)
                    server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)
            
            logger.info(f"Письмо успешно отправлено на {recipient_email}")
            return True
            
        except smtplib.SMTPAuthenticationError:
            logger.error("Ошибка аутентификации SMTP. Проверьте учетные данные")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"Ошибка SMTP при отправке письма: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке email: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_connection(self) -> bool:
        try:
            if not self.smtp_user or not self.smtp_password:
                logger.error("SMTP учетные данные не настроены")
                return False
            
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=self.ssl_context, timeout=15) as server:
                    server.login(self.smtp_user, self.smtp_password)
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15) as server:
                    server.starttls(context=self.ssl_context)
                    server.login(self.smtp_user, self.smtp_password)
            
            logger.info("Подключение к SMTP серверу успешно")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к SMTP: {e}")
            return False

