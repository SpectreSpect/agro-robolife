import asyncio
import logging
import shutil
from datetime import datetime, time
from pathlib import Path
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Report, ScheduleConfig
from .email_sender import EmailSender
from ..data_processing import DataParser, TableBuilder

logger = logging.getLogger(__name__)


class ReportScheduler:
    """Планировщик для автоматической генерации отчетов"""
    
    def __init__(self, shared_files_dir: Path, archived_files_dir: Path, output_dir: Path, template_path: Path):
        self.scheduler = AsyncIOScheduler()
        self.shared_files_dir = shared_files_dir
        self.archived_files_dir = archived_files_dir
        self.output_dir = output_dir
        self.template_path = template_path
        self.email_sender = EmailSender()
        self._started = False
        
        # Создаем папки если не существуют
        self.shared_files_dir.mkdir(exist_ok=True)
        self.archived_files_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        
    def start(self):
        """Запуск планировщика"""
        if not self._started:
            self.scheduler.start()
            self._started = True
            logger.info("Планировщик отчетов запущен")
            
            # Загружаем активные задачи из БД
            self._load_active_schedule()
    
    def shutdown(self):
        """Остановка планировщика"""
        if self._started:
            self.scheduler.shutdown()
            self._started = False
            logger.info("Планировщик отчетов остановлен")
    
    def _load_active_schedule(self):
        """Загрузка активного расписания из БД"""
        db = SessionLocal()
        try:
            # Ищем активное расписание (должно быть только одно)
            config = db.query(ScheduleConfig).filter(
                ScheduleConfig.is_enabled == True
            ).first()
            
            if config:
                logger.info(f"Найдено активное расписание: {config.schedule_type}")
                self._schedule_from_config(config)
            else:
                logger.info("Активных расписаний не найдено")
                    
        finally:
            db.close()
    
    def _schedule_from_config(self, config: ScheduleConfig):
        """Создание задачи планировщика из конфигурации"""
        try:
            # Удаляем существующие задачи
            if self.scheduler.get_job("report_generation"):
                self.scheduler.remove_job("report_generation")
            
            if config.schedule_type == "one_time":
                # Разовая задача
                if config.scheduled_time and config.scheduled_time > datetime.now():
                    self.scheduler.add_job(
                        self._generate_report,
                        trigger=DateTrigger(run_date=config.scheduled_time),
                        id="report_generation",
                        replace_existing=True
                    )
                    logger.info(f"Разовая задача запланирована на {config.scheduled_time}")
                else:
                    logger.warning("Время разовой задачи в прошлом или не указано")
                    
            elif config.schedule_type == "periodic":
                # Периодическая задача
                if config.periodic_time:
                    hour, minute = map(int, config.periodic_time.split(":"))
                    self.scheduler.add_job(
                        self._generate_report,
                        trigger=CronTrigger(hour=hour, minute=minute),
                        id="report_generation",
                        replace_existing=True
                    )
                    logger.info(f"Периодическая задача запланирована на {config.periodic_time} ежедневно")
                else:
                    logger.warning("Время периодической задачи не указано")
            
        except Exception as e:
            logger.error(f"Ошибка при создании задачи планировщика: {e}")
    
    def set_schedule(
        self,
        schedule_type: str,
        recipient_email: str,
        scheduled_time: Optional[datetime] = None,
        periodic_time: Optional[str] = None
    ) -> bool:
        """
        Установка нового расписания
        
        Args:
            schedule_type: "one_time" или "periodic"
            recipient_email: Email для отправки отчета
            scheduled_time: Datetime для разовой задачи
            periodic_time: Время суток для периодической (формат "HH:MM")
        """
        db = SessionLocal()
        try:
            # Отключаем все существующие расписания
            db.query(ScheduleConfig).update({"is_enabled": False})
            
            # Создаем новое расписание
            config = ScheduleConfig(
                is_enabled=True,
                schedule_type=schedule_type,
                scheduled_time=scheduled_time,
                periodic_time=periodic_time,
                recipient_email=recipient_email
            )
            db.add(config)
            db.commit()
            db.refresh(config)
            
            # Создаем задачу в планировщике
            self._schedule_from_config(config)
            
            logger.info(f"Расписание установлено: {schedule_type}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при установке расписания: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    def cancel_schedule(self) -> bool:
        """Отмена активного расписания"""
        db = SessionLocal()
        try:
            # Отключаем все расписания
            db.query(ScheduleConfig).update({"is_enabled": False})
            db.commit()
            
            # Удаляем задачу из планировщика
            if self.scheduler.get_job("report_generation"):
                self.scheduler.remove_job("report_generation")
            
            logger.info("Расписание отменено")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при отмене расписания: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    def get_active_schedule(self) -> Optional[dict]:
        """Получить активное расписание"""
        db = SessionLocal()
        try:
            config = db.query(ScheduleConfig).filter(
                ScheduleConfig.is_enabled == True
            ).first()
            
            if config:
                return config.to_dict()
            return None
            
        finally:
            db.close()
    
    async def _generate_report(self, manual: bool = False):
        """
        Основная функция генерации отчета
        
        Args:
            manual: True если вызвано вручную (кнопка "сгенерировать сейчас")
        """
        db = SessionLocal()
        report = None
        
        try:
            if manual:
                logger.info("Начало генерации отчета (ручной запуск)")
            else:
                logger.info("Начало генерации отчета по расписанию")
            
            # Получаем активную конфигурацию (может не быть для ручного запуска)
            config = db.query(ScheduleConfig).filter(
                ScheduleConfig.is_enabled == True
            ).first()
            
            # Для ручного запуска config не обязателен
            if not config and not manual:
                logger.error("Активная конфигурация не найдена")
                return
            
            # Определяем email получателя
            recipient_email = config.recipient_email if config else None
            
            # Проверяем наличие файлов
            files = list(self.shared_files_dir.glob("*.xlsx")) + list(self.shared_files_dir.glob("*.xls"))
            
            if not files:
                logger.warning("В папке shared_files нет файлов для обработки")
                if config:
                    config.last_run = datetime.now()
                    db.commit()
                return
            
            # Создаем папку для архива
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_dir = self.archived_files_dir / timestamp
            archive_dir.mkdir(exist_ok=True)
            
            # Копируем файлы в архив
            archived_file_names = []
            for file in files:
                dest = archive_dir / file.name
                shutil.copy2(file, dest)
                archived_file_names.append(file.name)
                logger.info(f"Файл {file.name} скопирован в архив")
            
            # Обрабатываем файлы из архива
            logger.info(f"Обработка {len(files)} файлов из архива")
            data_parser = DataParser(archive_dir)
            all_data = data_parser.parse_all_files()
            
            if not all_data:
                logger.error("Не удалось извлечь данные из файлов")
                report = Report(
                    scheduled_time=config.scheduled_time if (config and config.schedule_type == "one_time") else None,
                    output_file="",
                    status="failed",
                    error_message="Не удалось извлечь данные из файлов",
                    recipient_email=recipient_email,
                    archived_files=archived_file_names
                )
                db.add(report)
                if config:
                    config.last_run = datetime.now()
                db.commit()
                return
            
            # Собираем статистику
            departments = set(record["department_name"] for record in all_data)
            operations = set(record["operation_name"] for record in all_data)
            crops = set(record["crop_name"] for record in all_data)
            
            # Генерируем отчет
            output_filename = f"report_{timestamp}.xlsx"
            output_path = self.output_dir / output_filename
            
            table_builder = TableBuilder(str(self.template_path))
            success = table_builder.build_table(all_data, str(output_path), "Отчет за день")
            
            if not success:
                logger.error("Ошибка при создании Excel файла")
                report = Report(
                    scheduled_time=config.scheduled_time if (config and config.schedule_type == "one_time") else None,
                    output_file="",
                    status="failed",
                    error_message="Ошибка при создании Excel файла",
                    recipient_email=recipient_email,
                    archived_files=archived_file_names
                )
                db.add(report)
                if config:
                    config.last_run = datetime.now()
                db.commit()
                return
            
            # Создаем запись отчета
            report = Report(
                scheduled_time=config.scheduled_time if (config and config.schedule_type == "one_time") else None,
                output_file=output_filename,
                status="completed",
                recipient_email=recipient_email,
                records_count=len(all_data),
                departments_count=len(departments),
                operations_count=len(operations),
                crops_count=len(crops),
                archived_files=archived_file_names
            )
            db.add(report)
            db.commit()
            db.refresh(report)
            
            logger.info(f"Отчет {output_filename} успешно создан")
            
            # Отправляем на email (если указан)
            if recipient_email:
                subject = f"Сводный отчет по сельскохозяйственным данным"
                body = f"""Добрый день!

Во вложении находится {'автоматически сгенерированный' if not manual else 'сгенерированный'} сводный отчет по сельскохозяйственным данным.

Дата создания: {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""
                
                job_info = {
                    'records_count': report.records_count,
                    'departments_count': report.departments_count,
                    'operations_count': report.operations_count,
                    'crops_count': report.crops_count,
                    'input_files': archived_file_names
                }
                
                logger.info(f"Отправка отчета на {recipient_email}")
                email_success = self.email_sender.send_file(
                    recipient_email=recipient_email,
                    subject=subject,
                    body=body,
                    file_path=output_path,
                    job_info=job_info
                )
                
                if email_success:
                    report.status = "sent"
                    report.sent_at = datetime.now()
                    logger.info("Отчет успешно отправлен")
                else:
                    report.error_message = "Ошибка при отправке email"
                    logger.error("Не удалось отправить отчет")
            
            # Обновляем время последнего запуска (только для запланированных задач)
            if config and not manual:
                config.last_run = datetime.now()
                
                # Если это была разовая задача, отключаем расписание
                if config.schedule_type == "one_time":
                    config.is_enabled = False
                    if self.scheduler.get_job("report_generation"):
                        self.scheduler.remove_job("report_generation")
                    logger.info("Разовая задача выполнена, расписание отключено")
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Ошибка при генерации отчета: {e}")
            import traceback
            traceback.print_exc()
            
            if report:
                report.status = "failed"
                report.error_message = f"Ошибка генерации: {str(e)}"
                db.commit()
        finally:
            db.close()
    
    async def generate_now(self) -> Optional[int]:
        """
        Немедленная генерация отчета (вне расписания)
        Запускается в отдельном потоке, не блокируя основной event loop
        """
        # Запускаем генерацию в отдельном потоке чтобы не блокировать сайт
        import asyncio
        await asyncio.to_thread(self._generate_report_sync, manual=True)
        
        # Возвращаем ID последнего созданного отчета
        db = SessionLocal()
        try:
            report = db.query(Report).order_by(Report.created_at.desc()).first()
            return report.id if report else None
        finally:
            db.close()
    
    def _generate_report_sync(self, manual: bool = False):
        """Синхронная обертка для _generate_report (для запуска в отдельном потоке)"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._generate_report(manual=manual))
        finally:
            loop.close()

