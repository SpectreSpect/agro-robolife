from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean
from datetime import datetime
from .database import Base


class ProcessingJob(Base):
    """Старая модель - оставлена для совместимости"""
    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
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
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "status": self.status,
            "input_files": self.input_files,
            "output_file": self.output_file,
            "records_count": self.records_count,
            "departments_count": self.departments_count,
            "operations_count": self.operations_count,
            "crops_count": self.crops_count,
            "error_message": self.error_message,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "recipient_email": self.recipient_email,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "is_cancelled": self.is_cancelled,
        }


class Report(Base):
    """Модель для хранения сгенерированных отчетов"""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
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
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "output_file": self.output_file,
            "status": self.status,
            "recipient_email": self.recipient_email,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
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
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        return {
            "id": self.id,
            "is_enabled": self.is_enabled,
            "schedule_type": self.schedule_type,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "periodic_time": self.periodic_time,
            "recipient_email": self.recipient_email,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
