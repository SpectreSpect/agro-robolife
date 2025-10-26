from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean
from datetime import datetime, timezone, timedelta
from .database import Base


class ProcessingJob(Base):

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
        server_offset_seconds = datetime.now().astimezone().utcoffset().total_seconds()
        server_offset_minutes = int(server_offset_seconds / 60)
        
        def local_to_utc_iso(dt):
            if dt is None:
                return None
            utc_dt = dt + timedelta(minutes=-server_offset_minutes)
            return utc_dt.isoformat() + 'Z'
        
        return {
            "id": self.id,
            "created_at": local_to_utc_iso(self.created_at),
            "status": self.status,
            "input_files": self.input_files,
            "output_file": self.output_file,
            "records_count": self.records_count,
            "departments_count": self.departments_count,
            "operations_count": self.operations_count,
            "crops_count": self.crops_count,
            "error_message": self.error_message,
            "scheduled_time": local_to_utc_iso(self.scheduled_time),
            "recipient_email": self.recipient_email,
            "sent_at": local_to_utc_iso(self.sent_at),
            "is_cancelled": self.is_cancelled,
        }
