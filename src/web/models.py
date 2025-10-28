from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean
from datetime import datetime, timezone
from .database import Base


def _serialize_datetime(dt):
    """
    Сериализует datetime в ISO формат с UTC timezone
    Считаем что все даты в БД хранятся в UTC (naive datetime)
    """
    if dt is None:
        return None
    # Если дата без timezone, добавляем UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class ProcessingJob(Base):
    """Старая модель - оставлена для совместимости"""
    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    status = Column(String, default="pending")  # pending, processing, completed, failed, sent
    input_files = Column(JSON)  # Список имен загруженных файлов
    output_file = Column(String, nullable=True)
    records_count = Column(Integer, nullable=True)
    departments_count = Column(Integer, nullable=True)
    operations_count = Column(Integer, nullable=True)
    crops_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Новые поля для планирования отправки
    scheduled_time = Column(DateTime, nullable=True)  # Время отправки
    recipient_email = Column(String, nullable=True)  # Email получателя
    sent_at = Column(DateTime, nullable=True)  # Время фактической отправки
    is_cancelled = Column(Boolean, default=False)  # Флаг отмены

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": _serialize_datetime(self.created_at),
            "status": self.status,
            "input_files": self.input_files,
            "output_file": self.output_file,
            "records_count": self.records_count,
            "departments_count": self.departments_count,
            "operations_count": self.operations_count,
            "crops_count": self.crops_count,
            "error_message": self.error_message,
            "scheduled_time": _serialize_datetime(self.scheduled_time),
            "recipient_email": self.recipient_email,
            "sent_at": _serialize_datetime(self.sent_at),
            "is_cancelled": self.is_cancelled,
        }


class Report(Base):
    """Модель для хранения сгенерированных отчетов"""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    scheduled_time = Column(DateTime, nullable=True)  # Когда был запланирован
    output_file = Column(String, nullable=False)  # Имя файла отчета
    status = Column(String, default="completed")  # completed, sent, failed
    recipient_email = Column(String, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Статистика обработки
    records_count = Column(Integer, nullable=True)
    departments_count = Column(Integer, nullable=True)
    operations_count = Column(Integer, nullable=True)
    crops_count = Column(Integer, nullable=True)
    
    # Архивированные файлы
    archived_files = Column(JSON)  # Список файлов, использованных для отчета
    
    def to_dict(self):
        return {
            "id": self.id,
            "created_at": _serialize_datetime(self.created_at),
            "scheduled_time": _serialize_datetime(self.scheduled_time),
            "output_file": self.output_file,
            "status": self.status,
            "recipient_email": self.recipient_email,
            "sent_at": _serialize_datetime(self.sent_at),
            "error_message": self.error_message,
            "records_count": self.records_count,
            "departments_count": self.departments_count,
            "operations_count": self.operations_count,
            "crops_count": self.crops_count,
            "archived_files": self.archived_files,
        }


class ScheduleConfig(Base):
    """Модель для настройки расписания генерации отчетов"""
    __tablename__ = "schedule_config"

    id = Column(Integer, primary_key=True, index=True)
    is_enabled = Column(Boolean, default=False)
    schedule_type = Column(String, default="one_time")  # one_time или periodic
    scheduled_time = Column(DateTime, nullable=True)  # Для разовой задачи
    periodic_time = Column(String, nullable=True)  # Для периодической (например "14:00")
    recipient_email = Column(String, nullable=True)
    last_run = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    def to_dict(self):
        return {
            "id": self.id,
            "is_enabled": self.is_enabled,
            "schedule_type": self.schedule_type,
            "scheduled_time": _serialize_datetime(self.scheduled_time),
            "periodic_time": self.periodic_time,
            "recipient_email": self.recipient_email,
            "last_run": _serialize_datetime(self.last_run),
            "created_at": _serialize_datetime(self.created_at),
            "updated_at": _serialize_datetime(self.updated_at),
        }
