"""
话题模块Schema
"""
from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel


class TopicResponse(BaseModel):
    """话题响应"""
    id: int
    name: str
    grade_level: str
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    sort_order: Optional[int] = None

    class Config:
        from_attributes = True


class TopicListResponse(BaseModel):
    """话题列表响应（按年级分组）"""
    topics_by_grade: Dict[str, List[TopicResponse]]
