"""
课本单词表模型

用于熟词僻义判断的参照基准
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Index

from app.database import Base


class TextbookVocab(Base):
    """
    课本单词表 - 熟词僻义判断的参照基准

    判断标准：
    - 熟词：课本单词表里有这个词
    - 僻义：文章中的意思与课本单词表的释义不同
    """
    __tablename__ = "textbook_vocab"

    id = Column(Integer, primary_key=True)
    word = Column(String(255), nullable=False, comment="单词")
    pos = Column(String(100), comment="词性 (part of speech)")
    definition = Column(Text, nullable=False, comment="中文释义")
    publisher = Column(String(50), nullable=False, comment="出版社 (人教版/外研版)")
    grade = Column(String(20), nullable=False, comment="年级 (七年级/八年级/九年级)")
    semester = Column(String(10), nullable=False, comment="学期 (上/下)")
    unit = Column(String(50), comment="单元 (Unit 1, Module 4)")
    created_at = Column(DateTime, default=datetime.utcnow)

    # 创建索引加速查询
    __table_args__ = (
        Index('idx_textbook_vocab_word', 'word'),
        Index('idx_textbook_vocab_publisher_grade', 'publisher', 'grade'),
    )

    def __repr__(self):
        return f"<TextbookVocab(word='{self.word}', publisher='{self.publisher}', grade='{self.grade}')>"

    def to_dict(self):
        """转换为字典格式"""
        return {
            "id": self.id,
            "word": self.word,
            "pos": self.pos,
            "definition": self.definition,
            "publisher": self.publisher,
            "grade": self.grade,
            "semester": self.semester,
            "unit": self.unit,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    @property
    def source_display(self):
        """生成课本出处显示文本"""
        grade_map = {
            "七年级": "七上" if self.semester == "上" else "七下",
            "八年级": "八上" if self.semester == "上" else "八下",
            "九年级": "九上" if self.semester == "上" else "九下",
        }
        short_grade = grade_map.get(self.grade, self.grade)
        unit_str = f" {self.unit}" if self.unit else ""
        return f"{self.publisher}{short_grade}{unit_str}"
