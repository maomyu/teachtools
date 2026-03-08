"""
完形填空 Pydantic Schema

[INPUT]: 依赖 pydantic BaseModel
[OUTPUT]: 对外提供完形相关的请求/响应模型
[POS]: backend/app/schemas 的完形数据结构定义
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from typing import Optional, List, Dict
from pydantic import BaseModel


# ============================================================================
#  考点相关
# ============================================================================

class ClozePointBase(BaseModel):
    """考点基础"""
    blank_number: Optional[int] = None
    correct_answer: Optional[str] = None
    correct_word: Optional[str] = None
    options: Optional[Dict[str, str]] = None
    point_type: Optional[str] = None
    translation: Optional[str] = None
    explanation: Optional[str] = None
    confusion_words: Optional[List[Dict]] = None


class ClozePointResponse(ClozePointBase):
    """考点响应"""
    id: int
    sentence: Optional[str] = None

    class Config:
        from_attributes = True


class PointUpdateRequest(BaseModel):
    """更新考点请求"""
    point_type: str
    explanation: Optional[str] = None
    translation: Optional[str] = None
    confusion_words: Optional[List[Dict]] = None
    verified: bool = False


# ============================================================================
#  完形文章相关
# ============================================================================

class SourceInfo(BaseModel):
    """出处信息"""
    year: Optional[int] = None
    region: Optional[str] = None
    grade: Optional[str] = None
    semester: Optional[str] = None
    exam_type: Optional[str] = None
    filename: Optional[str] = None


class ClozePassageBase(BaseModel):
    """完形文章基础"""
    content: str  # 带空格原文
    original_content: Optional[str] = None
    word_count: Optional[int] = None
    primary_topic: Optional[str] = None
    secondary_topics: Optional[List[str]] = None


class ClozePassageResponse(ClozePassageBase):
    """完形文章响应"""
    id: int
    paper_id: int
    topic_confidence: Optional[float] = None
    source: Optional[SourceInfo] = None
    points: List[ClozePointResponse] = []

    class Config:
        from_attributes = True


class ClozeListResponse(BaseModel):
    """列表响应"""
    total: int
    items: List[ClozePassageResponse]


class VocabularyInCloze(BaseModel):
    """完形词汇"""
    id: int
    word: str
    definition: Optional[str] = None
    frequency: int
    sentence: Optional[str] = None


    char_position: Optional[int] = None


class ClozeDetailResponse(ClozePassageResponse):
    """详情响应"""
    point_distribution: Dict[str, int] = {}  # {"固定搭配": 4, "词义辨析": 5, ...}
    vocabulary: List[VocabularyInCloze] = []  # 完形相关词汇


class TopicUpdateRequest(BaseModel):
    """更新话题请求"""
    primary_topic: str
    secondary_topics: Optional[List[str]] = None
    verified: bool = False


# ============================================================================
#  考点汇总相关
# ============================================================================

class PointOccurrence(BaseModel):
    """考点出现位置"""
    sentence: str
    source: str
    blank_number: int
    point_type: str
    explanation: Optional[str] = None


class PointSummary(BaseModel):
    """考点汇总"""
    word: str
    definition: Optional[str] = None
    frequency: int
    point_type: str
    occurrences: List[PointOccurrence]


class PointListResponse(BaseModel):
    """考点汇总列表响应"""
    total: int
    items: List[PointSummary]


# ============================================================================
#  筛选相关
# ============================================================================

class ClozeFilters(BaseModel):
    """完形筛选器"""
    grades: List[str] = []
    topics: List[str] = []
    years: List[int] = []
    regions: List[str] = []
    exam_types: List[str] = []
    point_types: List[str] = []
    semesters: List[str] = []
