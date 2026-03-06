"""
作文模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class WritingTask(Base):
    """作文题目表"""
    __tablename__ = "writing_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(Integer, ForeignKey("exam_papers.id"), nullable=False)

    task_content = Column(Text, nullable=False)  # 题目要求
    requirements = Column(Text)  # 具体要求
    word_limit = Column(String(50))
    points_value = Column(String(20))  # 分值

    # 文体分类
    writing_type = Column(String(50))  # 应用文, 记叙文, 其他
    application_type = Column(String(50))  # 应用文子类：书信、通知、邀请等

    # 话题分类
    primary_topic = Column(String(100))
    topic_verified = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    paper = relationship("ExamPaper")
    samples = relationship("WritingSample", back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "writing_type IN ('应用文', '记叙文', '其他')",
            name="ck_writing_type"
        ),
    )

    def __repr__(self):
        return f"<WritingTask(id={self.id}, type={self.writing_type})>"


class WritingTemplate(Base):
    """作文模板表"""
    __tablename__ = "writing_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    writing_type = Column(String(50), nullable=False)
    application_type = Column(String(50))
    template_name = Column(String(100), nullable=False)
    template_content = Column(Text, nullable=False)
    tips = Column(Text)  # 写作技巧
    structure = Column(Text)  # 结构说明

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    samples = relationship("WritingSample", back_populates="template")

    def __repr__(self):
        return f"<WritingTemplate(id={self.id}, name={self.template_name})>"


class WritingSample(Base):
    """作文范文表"""
    __tablename__ = "writing_samples"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("writing_tasks.id"))
    template_id = Column(Integer, ForeignKey("writing_templates.id"))

    sample_content = Column(Text, nullable=False)
    sample_type = Column(String(20))  # AI生成, 人工编写, 真题范文
    score_level = Column(String(20))  # 档次：一档、二档等

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    task = relationship("WritingTask", back_populates="samples")
    template = relationship("WritingTemplate", back_populates="samples")

    __table_args__ = (
        CheckConstraint(
            "sample_type IN ('AI生成', '人工编写', '真题范文')",
            name="ck_sample_type"
        ),
    )

    def __repr__(self):
        return f"<WritingSample(id={self.id}, type={self.sample_type})>"
