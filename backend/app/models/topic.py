"""
话题模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Topic(Base):
    """话题表"""
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    grade_level = Column(String(20), nullable=False)  # 按年级分开
    description = Column(Text)
    keywords = Column(Text)  # JSON格式
    parent_topic_id = Column(Integer, ForeignKey("topics.id"))
    sort_order = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)

    # 自引用关系
    parent = relationship("Topic", remote_side=[id], backref="children")

    __table_args__ = (
        UniqueConstraint("name", "grade_level", name="uq_topic_name_grade"),
    )

    def __repr__(self):
        return f"<Topic(id={self.id}, name={self.name}, grade={self.grade_level})>"
