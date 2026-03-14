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
#  考点分析详情（嵌套对象）
# ============================================================================

class PointAnalysis(BaseModel):
    """考点分析详情 - 包含各类考点的扩展字段"""
    # 通用字段
    explanation: Optional[str] = None
    confusion_words: Optional[List[Dict]] = None
    tips: Optional[str] = None

    # 固定搭配专用
    phrase: Optional[str] = None
    similar_phrases: Optional[List[str]] = None

    # 词义辨析专用
    word_analysis: Optional[Dict] = None
    dictionary_source: Optional[str] = None

    # 熟词僻义专用
    textbook_meaning: Optional[str] = None
    textbook_source: Optional[str] = None
    context_meaning: Optional[str] = None
    similar_words: Optional[List[Dict]] = None


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

    # 固定搭配专用字段
    phrase: Optional[str] = None
    similar_phrases: Optional[List[str]] = None

    # 词义辨析专用字段
    word_analysis: Optional[Dict] = None
    dictionary_source: Optional[str] = None

    # 熟词僻义专用字段
    textbook_meaning: Optional[str] = None
    textbook_source: Optional[str] = None
    context_meaning: Optional[str] = None
    similar_words: Optional[List[Dict]] = None

    # 通用
    tips: Optional[str] = None


class ClozePointResponse(ClozePointBase):
    """考点响应"""
    id: int
    sentence: Optional[str] = None
    point_verified: bool = False

    class Config:
        from_attributes = True


class PointUpdateRequest(BaseModel):
    """更新考点请求"""
    point_type: str
    explanation: Optional[str] = None
    translation: Optional[str] = None
    confusion_words: Optional[List[Dict]] = None
    # 新增字段
    phrase: Optional[str] = None
    similar_phrases: Optional[List[str]] = None
    word_analysis: Optional[Dict] = None
    textbook_meaning: Optional[str] = None
    textbook_source: Optional[str] = None
    context_meaning: Optional[str] = None
    tips: Optional[str] = None
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
    passage_id: Optional[int] = None  # 完形文章ID，用于跳转
    point_id: Optional[int] = None    # 考点ID，用于编辑
    # 嵌套分析详情
    analysis: Optional[PointAnalysis] = None


class PointSummary(BaseModel):
    """考点汇总"""
    word: str
    definition: Optional[str] = None
    frequency: int
    point_type: str
    occurrences: List[PointOccurrence]
    # 聚合后的分析概要（取第一次出现的信息）
    tips: Optional[str] = None


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
