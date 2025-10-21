from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from datetime import datetime
from .database import Base


class ProcessingJob(Base):

    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    input_files = Column(JSON)  # Список имен загруженных файлов
    output_file = Column(String, nullable=True)
    records_count = Column(Integer, nullable=True)
    departments_count = Column(Integer, nullable=True)
    operations_count = Column(Integer, nullable=True)
    crops_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

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
        }
