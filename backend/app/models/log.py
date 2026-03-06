"""
日志模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime

from app.database import Base


class ImportLog(Base):
    """导入日志表"""
    __tablename__ = "import_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(50))  # 批次ID
    filename = Column(String(255))
    import_type = Column(String(50))
    status = Column(String(20))
    error_message = Column(Text)
    processing_time = Column(Float)  # 处理耗时（秒）

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ImportLog(id={self.id}, filename={self.filename}, status={self.status})>"
