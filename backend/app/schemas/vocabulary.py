"""
词汇模块Schema

[INPUT]: 依赖 pydantic 的 BaseModel
[OUTPUT]: 对外提供词汇相关的请求/响应模型
[POS]: backend/app/schemas 的词汇模块定义
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class VocabularyFiltersResponse(BaseModel):
    """筛选项响应"""
    grades: List[str] = []
    topics: List[str] = []
    years: List[int] = []
    regions: List[str] = []
    exam_types: List[str] = []
    semesters: List[str] = []
    sources: List[str] = []  # 来源：阅读、完形


class VocabularyOccurrence(BaseModel):
    """词汇出现位置"""
    sentence: str
    passage_id: int
    char_position: int
    end_position: Optional[int] = None
    source: Optional[str] = None  # 出处信息字符串（用于显示）
    source_type: Optional[str] = None  # 来源类型：reading/cloze
    year: Optional[int] = None
    region: Optional[str] = None
    grade: Optional[str] = None
    exam_type: Optional[str] = None
    semester: Optional[str] = None


class VocabularyResponse(BaseModel):
    """词汇响应"""
    id: int
    word: str
    lemma: Optional[str] = None
    definition: Optional[str] = None
    phonetic: Optional[str] = None
    pos: Optional[str] = None
    frequency: int
    sources: List[str] = []  # 来源列表：阅读、完形
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
    total: int                          # 总数
    page: int                           # 当前页码
    size: int                           # 每页数量
    has_more: bool                       # 是否有更多
    occurrences: List[VocabularyOccurrence]
