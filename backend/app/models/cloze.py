"""
完形填空模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class ClozePassage(Base):
    """完形填空表"""
    __tablename__ = "cloze_passages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(Integer, ForeignKey("exam_papers.id"), nullable=False)

    content = Column(Text, nullable=False)  # 带空格标记的原文
    original_content = Column(Text)  # 完整原文（如果可用）
    word_count = Column(Integer)

    # 话题分类
    primary_topic = Column(String(100))
    secondary_topics = Column(Text)  # JSON格式
    topic_confidence = Column(Float)
    topic_verified = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    paper = relationship("ExamPaper", back_populates="cloze_passages")
    points = relationship("ClozePoint", back_populates="cloze", cascade="all, delete-orphan")
    vocabulary_occurrences = relationship("VocabularyCloze", back_populates="cloze", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ClozePassage(id={self.id}, topic={self.primary_topic})>"


class ClozePoint(Base):
    """完形考点表"""
    __tablename__ = "cloze_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cloze_id = Column(Integer, ForeignKey("cloze_passages.id"), nullable=False)

    blank_number = Column(Integer)  # 第几个空
    correct_answer = Column(String(100))  # 正确答案选项 (A/B/C/D)
    correct_word = Column(String(255))  # 正确答案对应的词
    options = Column(Text)  # JSON: {"A": "...", "B": "...", ...}

    # 三类考点
    point_type = Column(String(50))  # 固定搭配, 词义辨析, 熟词僻义
    point_detail = Column(Text)  # 考点详解
    translation = Column(Text)  # 翻译
    explanation = Column(Text)  # 解析

    # 易混淆信息（词义辨析类）
    confusion_words = Column(Text)  # JSON格式

    # 通用字段
    tips = Column(Text)  # 记忆技巧或相关拓展

    # 固定搭配专用字段
    phrase = Column(String(255))  # 完整短语 (take a break)
    similar_phrases = Column(Text)  # JSON: ["take a chance", ...]

    # 词义辨析专用字段
    word_analysis = Column(Text)  # JSON: 三维度分析
    dictionary_source = Column(String(100))  # 词典来源 (柯林斯词典)

    # 熟词僻义专用字段
    textbook_meaning = Column(Text)  # 课本释义
    textbook_source = Column(String(100))  # 课本出处 (人教版八上 Unit 5)
    context_meaning = Column(Text)  # 语境释义
    similar_words = Column(Text)  # JSON: 相似熟词僻义列表

    # 人工校对
    point_verified = Column(Boolean, default=False)

    # 例句和出处
    sentence = Column(Text)  # 包含该空的句子
    char_position = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    cloze = relationship("ClozePassage", back_populates="points")

    __table_args__ = (
        CheckConstraint(
            "point_type IN ('固定搭配', '词义辨析', '熟词僻义')",
            name="ck_point_type"
        ),
    )

    def __repr__(self):
        return f"<ClozePoint(id={self.id}, blank={self.blank_number}, type={self.point_type})>"
