"""
完形填空模型

考点分类系统 v2:
- 5大类(A-E) 16个考点
- 支持多标签: 主考点 + 辅助考点 + 排错点
- 优先级: P1(核心) > P2(重要) > P3(一般)

旧类型映射: 固定搭配→C2, 词义辨析→D1, 熟词僻义→D2
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class PointTypeDefinition(Base):
    """考点类型定义表（系统常量）"""
    __tablename__ = "point_type_definitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), unique=True, nullable=False)  # A1, B2, C2, etc.
    category = Column(String(10), nullable=False)           # A, B, C, D, E
    category_name = Column(String(50), nullable=False)      # 语篇理解类, 逻辑关系类, etc.
    name = Column(String(50), nullable=False)               # 上下文语义推断, 转折对比, etc.
    priority = Column(Integer, nullable=False)              # 1, 2, 3 (P1/P2/P3)
    description = Column(Text)                              # 判断标准描述

    def __repr__(self):
        return f"<PointTypeDefinition(code={self.code}, name={self.name})>"


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
    """完形考点表

    v2 支持多标签考点系统:
    - primary_point_code: 主考点编码（如 A1, B2, C2）
    - secondary_points: 辅助考点（一对多关联）
    - rejection_points: 排错点（一对多关联）
    - legacy_point_type: 兼容旧类型（固定搭配/词义辨析/熟词僻义）
    """
    __tablename__ = "cloze_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cloze_id = Column(Integer, ForeignKey("cloze_passages.id"), nullable=False)

    blank_number = Column(Integer)  # 第几个空
    correct_answer = Column(String(100))  # 正确答案选项 (A/B/C/D)
    correct_word = Column(String(255))  # 正确答案对应的词
    options = Column(Text)  # JSON: {"A": "...", "B": "...", ...}

    # === 新考点分类系统 v2 ===
    primary_point_code = Column(String(20))  # 主考点编码: A1, B2, C2, D1, E1, etc.
    legacy_point_type = Column(String(50))   # 兼容旧类型: 固定搭配/词义辨析/熟词僻义

    # === 旧考点分类（保留兼容） ===
    point_type = Column(String(50))  # 固定搭配, 词义辨析, 熟词僻义 (不再有CHECK约束)
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

    # 熟词僻义专用字段（作为附加标签）
    is_rare_meaning = Column(Boolean, default=False)  # 是否包含熟词僻义
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
    secondary_points = relationship("ClozeSecondaryPoint", back_populates="cloze_point", cascade="all, delete-orphan")
    rejection_points = relationship("ClozeRejectionPoint", back_populates="cloze_point", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ClozePoint(id={self.id}, blank={self.blank_number}, code={self.primary_point_code}, legacy={self.point_type})>"


class ClozeSecondaryPoint(Base):
    """辅助考点关联表

    每个空格可以有多个辅助考点，用于补充说明
    """
    __tablename__ = "cloze_secondary_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cloze_point_id = Column(Integer, ForeignKey("cloze_points.id"), nullable=False)
    point_code = Column(String(20), nullable=False)  # 考点编码: A1, B2, etc.
    explanation = Column(Text)  # 该辅助考点的解析
    sort_order = Column(Integer, default=0)  # 排序

    # 关系
    cloze_point = relationship("ClozePoint", back_populates="secondary_points")

    def __repr__(self):
        return f"<ClozeSecondaryPoint(point_code={self.point_code})>"


class ClozeRejectionPoint(Base):
    """排错点关联表

    记录每个干扰选项的排除依据
    """
    __tablename__ = "cloze_rejection_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cloze_point_id = Column(Integer, ForeignKey("cloze_points.id"), nullable=False)
    option_word = Column(String(255), nullable=False)  # 被排除的选项词
    point_code = Column(String(20), nullable=False)  # 排错依据编码
    explanation = Column(Text)  # 为什么排除

    # 关系
    cloze_point = relationship("ClozePoint", back_populates="rejection_points")

    def __repr__(self):
        return f"<ClozeRejectionPoint(option={self.option_word}, reason={self.point_code})>"
