"""
词汇模块Schema
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class VocabularyOccurrence(BaseModel):
    """词汇出现位置"""
    sentence: str
    passage_id: int
    char_position: int
    end_position: Optional[int] = None
    source: Optional[str] = None  # 出处信息字符串


class VocabularyResponse(BaseModel):
    """词汇响应"""
    id: int
    word: str
    lemma: Optional[str] = None
    definition: Optional[str] = None
    phonetic: Optional[str] = None
    pos: Optional[str] = None
    frequency: int
    occurrences: List[VocabularyOccurrence] = []

    class Config:
        from_attributes = True


class VocabularyListResponse(BaseModel):
    """词汇列表响应"""
    total: int
    items: List[VocabularyResponse]


class VocabularySearchResponse(BaseModel):
    """词汇搜索响应"""
    word: str
    definition: Optional[str] = None
    frequency: int
    occurrences: List[VocabularyOccurrence]
