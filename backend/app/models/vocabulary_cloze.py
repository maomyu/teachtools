"""
完形填空词汇关联模型

[INPUT]: 依赖 app.database.Base, app.models.vocabulary.Vocabulary, app.models.cloze.ClozePassage
[OUTPUT]: 对外提供 VocabularyCloze 类
[POS]: backend/app/models 的完形词汇关联表
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from datetime import datetime
from sqlalchemy import Column, Integer, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class VocabularyCloze(Base):
    """完形词汇关联表 - 记录词汇在完形文章中的出现"""
    __tablename__ = "vocabulary_cloze"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vocabulary_id = Column(Integer, ForeignKey("vocabulary.id"), nullable=False)
    cloze_id = Column(Integer, ForeignKey("cloze_passages.id"), nullable=False)

    # 出现位置信息
    sentence = Column(Text, nullable=False)  # 包含该词的句子
    char_position = Column(Integer)  # 字符起始位置
    end_position = Column(Integer)  # 字符结束位置
    word_position = Column(Integer)  # 词序位置（第几个词）

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    vocabulary = relationship("Vocabulary", backref="cloze_occurrences")
    cloze = relationship("ClozePassage", backref="vocabulary_occurrences")

    # 唯一约束：同一词汇在同一位置只记录一次
    __table_args__ = (
        UniqueConstraint("vocabulary_id", "cloze_id", "char_position", name="uq_vocab_cloze_position"),
    )

    def __repr__(self):
        return f"<VocabularyCloze(vocab_id={self.vocabulary_id}, cloze_id={self.cloze_id})>"
