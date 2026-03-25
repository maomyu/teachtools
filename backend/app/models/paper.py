"""
试卷模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, CheckConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class ExamPaper(Base):
    """试卷信息表"""
    __tablename__ = "exam_papers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    original_path = Column(String(500))

    # 元数据
    year = Column(Integer, nullable=True)
    region = Column(String(50))  # 区县：东城、西城、海淀等
    school = Column(String(100))  # 学校（如果有）
    grade = Column(String(20), nullable=True)  # 初一、初二、初三
    semester = Column(String(10))  # 上、下
    season = Column(String(20))  # 春季、秋季
    exam_type = Column(String(20))  # 期中、期末、一模、二模、月考
    version = Column(String(20))  # 教师版、学生版、原卷版、解析版

    # 处理状态
    import_status = Column(String(20), default="pending")  # pending, processing, completed, failed, partial
    parse_strategy = Column(String(20))  # rule, llm, manual
    confidence = Column(Float, default=0.0)
    error_message = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    reading_passages = relationship("ReadingPassage", back_populates="paper", cascade="all, delete-orphan")
    cloze_passages = relationship("ClozePassage", back_populates="paper", cascade="all, delete-orphan")
    writing_tasks = relationship("WritingTask", back_populates="paper", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "grade IS NULL OR grade IN ('初一', '初二', '初三')",
            name="ck_papers_grade"
        ),
        CheckConstraint(
            "import_status IN ('pending', 'processing', 'completed', 'failed', 'partial')",
            name="ck_papers_status"
        ),
    )

    def __repr__(self):
        return f"<ExamPaper(id={self.id}, filename={self.filename})>"
