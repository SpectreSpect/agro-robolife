import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import ProcessingJob
from .email_sender import EmailSender

logger = logging.getLogger(__name__)


class JobScheduler:
    def __init__(self, output_dir: Path):
        self.scheduler = AsyncIOScheduler()
        self.output_dir = output_dir
        self.email_sender = EmailSender()
        self._started = False
        
    def start(self):
        if not self._started:
            self.scheduler.start()
            self._started = True
            logger.info("Планировщик задач запущен")
            
            self._load_pending_jobs()
    
    def shutdown(self):
        if self._started:
            self.scheduler.shutdown()
            self._started = False
            logger.info("Планировщик задач остановлен")
    
    def _load_pending_jobs(self):
        db = SessionLocal()
        try:
            jobs = db.query(ProcessingJob).filter(
                ProcessingJob.status == "completed",
                ProcessingJob.scheduled_time.isnot(None),
                ProcessingJob.is_cancelled == False,
                ProcessingJob.sent_at.is_(None)
            ).all()
            
            for job in jobs:
                if job.scheduled_time > datetime.now():
                    self.schedule_job(job.id, job.scheduled_time)
                    logger.info(
                        f"Восстановлена задача {job.id} "
                        f"для отправки в {job.scheduled_time}"
                    )
                else:
                    logger.info(
                        f"Задача {job.id} пропущена, отправка немедленно"
                    )
                    asyncio.create_task(self._send_job(job.id))
                    
        finally:
            db.close()
    
    def schedule_job(self, job_id: int, scheduled_time: datetime) -> bool:
        try:
            job_str_id = f"job_{job_id}"
            if self.scheduler.get_job(job_str_id):
                self.scheduler.remove_job(job_str_id)
            
            self.scheduler.add_job(
                self._send_job,
                trigger=DateTrigger(run_date=scheduled_time),
                args=[job_id],
                id=job_str_id,
                replace_existing=True
            )
            
            logger.info(f"Задача {job_id} запланирована на {scheduled_time}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при планировании задачи {job_id}: {e}")
            return False
    
    def cancel_job(self, job_id: int) -> bool:
        try:
            job_str_id = f"job_{job_id}"
            if self.scheduler.get_job(job_str_id):
                self.scheduler.remove_job(job_str_id)
                logger.info(f"Отправка задачи {job_id} отменена")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка при отмене задачи {job_id}: {e}")
            return False
    
    async def _send_job(self, job_id: int):
        db = SessionLocal()
        try:
            job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            
            if not job:
                logger.error(f"Задача {job_id} не найдена")
                return
            
            if job.is_cancelled:
                logger.info(f"Задача {job_id} отменена, отправка пропущена")
                return
            
            if not job.recipient_email:
                logger.error(f"Для задачи {job_id} не указан email получателя")
                job.error_message = "Email получателя не указан"
                db.commit()
                return
            
            if not job.output_file:
                logger.error(f"Для задачи {job_id} нет выходного файла")
                job.error_message = "Файл для отправки не найден"
                db.commit()
                return
            
            # Путь к файлу
            file_path = self.output_dir / job.output_file
            
            if not file_path.exists():
                logger.error(f"Файл {file_path} не существует")
                job.error_message = f"Файл {job.output_file} не найден"
                db.commit()
                return
            
            # Подготовка данных письма
            subject = f"Сводный отчет по сельскохозяйственным данным (ID: {job_id})"
            body = f"""Добрый день!

Во вложении находится обработанный сводный отчет по сельскохозяйственным данным.

Дата обработки: {job.created_at.strftime('%d.%m.%Y %H:%M')}
"""
            
            job_info = {
                'records_count': job.records_count,
                'departments_count': job.departments_count,
                'operations_count': job.operations_count,
                'crops_count': job.crops_count,
                'input_files': job.input_files or []
            }
            
            # Отправка email
            logger.info(f"Отправка задачи {job_id} на {job.recipient_email}")
            success = self.email_sender.send_file(
                recipient_email=job.recipient_email,
                subject=subject,
                body=body,
                file_path=file_path,
                job_info=job_info
            )
            
            if success:
                job.status = "sent"
                job.sent_at = datetime.now()
                job.error_message = None
                logger.info(f"Задача {job_id} успешно отправлена")
            else:
                job.error_message = "Ошибка при отправке email"
                logger.error(f"Не удалось отправить задачу {job_id}")
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Ошибка при отправке задачи {job_id}: {e}")
            import traceback
            traceback.print_exc()
            
            if job:
                job.error_message = f"Ошибка отправки: {str(e)}"
                db.commit()
        finally:
            db.close()
    
    async def send_immediately(self, job_id: int) -> bool:
        self.cancel_job(job_id)
        await self._send_job(job_id)
        
        db = SessionLocal()
        try:
            job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            return job and job.status == "sent"
        finally:
            db.close()

