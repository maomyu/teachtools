"""
阅读文章模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class ReadingPassage(Base):
    """阅读文章表"""
    __tablename__ = "reading_passages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(Integer, ForeignKey("exam_papers.id"), nullable=False)

    passage_type = Column(String(5), nullable=False)  # C, D
    title = Column(String(255))
    content = Column(Text, nullable=False)
    word_count = Column(Integer)

    # 话题分类
    primary_topic = Column(String(100))
    secondary_topics = Column(Text)  # JSON格式存储
    topic_confidence = Column(Float)
    topic_verified = Column(Boolean, default=False)
    verified_by = Column(String(50))
    verified_at = Column(DateTime)

    # 题目信息
    has_questions = Column(Boolean, default=False)

    # 未来扩展预留
    content_embedding = Column(Text)  # BLOB in SQLite
    summary = Column(Text)
    keywords = Column(Text)  # JSON格式

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    paper = relationship("ExamPaper", back_populates="reading_passages")
    questions = relationship("Question", back_populates="passage", cascade="all, delete-orphan")
    vocabulary_occurrences = relationship("VocabularyPassage", back_populates="passage", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "passage_type IN ('C', 'D')",
            name="ck_passages_type"
        ),
    )

    @property
    def source_info(self):
        """获取出处信息"""
        if self.paper:
            return {
                "year": self.paper.year,
                "region": self.paper.region,
                "school": self.paper.school,
                "grade": self.paper.grade,
                "exam_type": self.paper.exam_type,
                "semester": self.paper.semester,
                "filename": self.paper.filename
            }
        return None

    def __repr__(self):
        return f"<ReadingPassage(id={self.id}, type={self.passage_type}, topic={self.primary_topic})>"


class Question(Base):
    """题目表"""
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    passage_id = Column(Integer, ForeignKey("reading_passages.id"), nullable=False)

    question_number = Column(Integer)
    question_text = Column(Text, nullable=False)
    option_a = Column(Text)
    option_b = Column(Text)
    option_c = Column(Text)
    option_d = Column(Text)
    correct_answer = Column(String(5))
    answer_explanation = Column(Text)
    question_type = Column(String(50))

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    passage = relationship("ReadingPassage", back_populates="questions")

    def __repr__(self):
        return f"<Question(id={self.id}, number={self.question_number})>"
