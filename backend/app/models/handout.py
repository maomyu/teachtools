"""
讲义转换模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, CheckConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class HandoutConversion(Base):
    """讲义转换记录表"""
    __tablename__ = "handout_conversions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_filename = Column(String(255))
    original_path = Column(String(500))
    output_path = Column(String(500))

    conversion_settings = Column(Text)  # JSON格式
    status = Column(String(20))  # pending, processing, completed, failed
    error_message = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_handout_status"
        ),
    )

    def __repr__(self):
        return f"<HandoutConversion(id={self.id}, status={self.status})>"
