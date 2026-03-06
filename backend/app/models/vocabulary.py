"""
词汇模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Vocabulary(Base):
    """高频词汇表"""
    __tablename__ = "vocabulary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    word = Column(String(100), nullable=False, unique=True)
    lemma = Column(String(100))  # 词元形式
    definition = Column(Text)
    phonetic = Column(String(100))
    pos = Column(String(50))  # 词性
    frequency = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    occurrences = relationship("VocabularyPassage", back_populates="vocabulary", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Vocabulary(id={self.id}, word={self.word}, freq={self.frequency})>"


class VocabularyPassage(Base):
    """词汇-文章关联表（含例句和位置）"""
    __tablename__ = "vocabulary_passage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vocabulary_id = Column(Integer, ForeignKey("vocabulary.id"), nullable=False)
    passage_id = Column(Integer, ForeignKey("reading_passages.id"), nullable=False)

    sentence = Column(Text, nullable=False)  # 包含该词的原句
    char_position = Column(Integer)  # 词在文章中的字符位置（起始）
    word_position = Column(Integer)  # 词在文章中的词序位置
    end_position = Column(Integer)  # 词在文章中的结束位置

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    vocabulary = relationship("Vocabulary", back_populates="occurrences")
    passage = relationship("ReadingPassage", back_populates="vocabulary_occurrences")

    __table_args__ = (
        UniqueConstraint("vocabulary_id", "passage_id", "char_position", name="uq_vocab_passage_pos"),
    )

    def __repr__(self):
        return f"<VocabularyPassage(vocab_id={self.vocabulary_id}, passage_id={self.passage_id}, pos={self.char_position})>"
