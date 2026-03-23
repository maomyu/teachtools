"""
完形填空 Pydantic Schema

[INPUT]: 依赖 pydantic BaseModel
[OUTPUT]: 对外提供完形相关的请求/响应模型
[POS]: backend/app/schemas 的完形数据结构定义
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md

考点分类系统 v2:
- 5大类(A-E) 16个考点
- 支持多标签: 主考点 + 辅助考点 + 排错点
- 优先级: P1(核心) > P2(重要) > P3(一般)

旧类型映射: 固定搭配→C2, 词义辨析→D1, 熟词僻义→D2
"""
from typing import Optional, List, Dict
from pydantic import BaseModel


# ============================================================================
#  考点类型定义 (v2)
# ============================================================================

class PointTypeBase(BaseModel):
    """考点类型基础定义"""
    code: str                    # A1, B2, C2, D1, E1, etc.
    category: str                # A, B, C, D, E
    category_name: str           # 语篇理解类, 逻辑关系类, etc.
    name: str                    # 上下文语义推断, 转折对比, etc.
    priority: int                # 1, 2, 3 (P1/P2/P3)
    description: Optional[str] = None

    class Config:
        from_attributes = True


class PointTypeListResponse(BaseModel):
    """考点类型列表响应"""
    total: int
    items: List[PointTypeBase]


class PointTypeByCategoryResponse(BaseModel):
    """按大类分组的考点类型响应"""
    A: List[PointTypeBase] = []  # 语篇理解类
    B: List[PointTypeBase] = []  # 逻辑关系类
    C: List[PointTypeBase] = []  # 句法语法类
    D: List[PointTypeBase] = []  # 词汇选项类
    E: List[PointTypeBase] = []  # 常识主题类


class SecondaryPointBase(BaseModel):
    """辅助考点"""
    point_code: str              # 考点编码
    explanation: Optional[str] = None  # 该辅助考点的解析

    class Config:
        from_attributes = True


class RejectionPointBase(BaseModel):
    """排错点"""
    option_word: str             # 被排除的选项词
    # V2 旧字段（兼容）
    point_code: Optional[str] = None
    explanation: Optional[str] = None
    # V5 新字段
    rejection_code: Optional[str] = None   # 排错依据编码
    rejection_reason: Optional[str] = None # 排除原因

    class Config:
        from_attributes = True


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
    primary_point_code: Optional[str] = None  # V2 主考点编码 (A1-E2)
    rejection_points: List[RejectionPointBase] = []  # 排错点列表

    class Config:
        from_attributes = True


class ClozePointNewResponse(BaseModel):
    """考点响应 (v2 多标签版本)

    支持主考点 + 辅助考点 + 排错点的多标签结构
    """
    id: int
    blank_number: Optional[int] = None
    correct_answer: Optional[str] = None
    correct_word: Optional[str] = None
    options: Optional[Dict[str, str]] = None
    sentence: Optional[str] = None

    # === 新考点系统 v2 ===
    primary_point: Optional[PointTypeBase] = None  # 主考点
    secondary_points: List[SecondaryPointBase] = []  # 辅助考点
    rejection_points: List[RejectionPointBase] = []  # 排错点

    # === 兼容旧系统 ===
    legacy_point_type: Optional[str] = None  # 旧类型: 固定搭配/词义辨析/熟词僻义
    point_type: Optional[str] = None  # 保留兼容

    # === 解析内容 ===
    translation: Optional[str] = None
    explanation: Optional[str] = None
    confusion_words: Optional[List[Dict]] = None
    tips: Optional[str] = None

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

    # 状态
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


class SecondaryPointInput(BaseModel):
    """辅助考点输入"""
    point_code: str
    explanation: Optional[str] = None


class RejectionPointInput(BaseModel):
    """排错点输入"""
    option_word: str
    point_code: str
    explanation: Optional[str] = None


class PointUpdateRequestV2(BaseModel):
    """更新考点请求 (v2 多标签版本)"""
    primary_point_code: str  # 主考点编码
    secondary_points: Optional[List[SecondaryPointInput]] = None  # 辅助考点
    rejection_points: Optional[List[RejectionPointInput]] = None  # 排错点
    # 解析内容
    explanation: Optional[str] = None
    translation: Optional[str] = None
    confusion_words: Optional[List[Dict]] = None
    tips: Optional[str] = None
    # 兼容旧字段
    phrase: Optional[str] = None
    similar_phrases: Optional[List[str]] = None
    word_analysis: Optional[Dict] = None
    textbook_meaning: Optional[str] = None
    textbook_source: Optional[str] = None
    context_meaning: Optional[str] = None
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


class ClozeDetailNewResponse(BaseModel):
    """详情响应 (v2 新考点系统)

    包含按大类和优先级统计的考点分布
    """
    id: int
    paper_id: int
    content: str
    original_content: Optional[str] = None
    word_count: Optional[int] = None
    primary_topic: Optional[str] = None
    secondary_topics: Optional[List[str]] = None
    topic_confidence: Optional[float] = None
    source: Optional[SourceInfo] = None
    points: List[ClozePointNewResponse] = []

    # === 新考点分布统计 ===
    point_distribution_by_category: Dict[str, int] = {}  # {"A": 5, "B": 3, "C": 2, ...}
    point_distribution_by_priority: Dict[str, int] = {}  # {"P1": 8, "P2": 4, "P3": 3}
    # 兼容旧分布
    point_distribution: Dict[str, int] = {}  # {"固定搭配": 4, "词义辨析": 5, ...}

    vocabulary: List[VocabularyInCloze] = []

    class Config:
        from_attributes = True


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


class PointOccurrenceNew(BaseModel):
    """考点出现位置 (v2)"""
    sentence: str
    source: str
    blank_number: int
    primary_point: Optional[PointTypeBase] = None  # 主考点
    secondary_points: List[SecondaryPointBase] = []  # 辅助考点
    passage_id: Optional[int] = None
    point_id: Optional[int] = None
    # 嵌套分析详情
    analysis: Optional[PointAnalysis] = None


class PointSummaryNewResponse(BaseModel):
    """考点汇总 (v2 新考点系统)"""
    word: str
    definition: Optional[str] = None
    frequency: int
    primary_point: Optional[PointTypeBase] = None  # 主考点
    occurrences: List[PointOccurrenceNew] = []
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
    schools: List[str] = []
    exam_types: List[str] = []
    point_types: List[str] = []
    semesters: List[str] = []


class ClozeFiltersNew(BaseModel):
    """完形筛选器 (v2 新考点系统)"""
    grades: List[str] = []
    topics: List[str] = []
    years: List[int] = []
    regions: List[str] = []
    exam_types: List[str] = []
    semesters: List[str] = []
    # 新增: 按考点编码筛选 (A1, B2, C2, etc.)
    point_codes: List[str] = []
    # 新增: 按大类筛选 (A, B, C, D, E)
    categories: List[str] = []
    # 新增: 按优先级筛选 (1, 2, 3)
    priorities: List[int] = []
    # 兼容旧筛选
    point_types: List[str] = []


# ============================================================================
#  讲义相关
# ============================================================================

class ClozeTopicStats(BaseModel):
    """完形主题统计"""
    topic: str
    passage_count: int
    recent_years: List[int] = []


class ArticleSource(BaseModel):
    """文章来源（按试卷分组）"""
    year: Optional[int] = None
    region: Optional[str] = None
    exam_type: Optional[str] = None
    semester: Optional[str] = None
    passages: List[Dict] = []  # [{"type": None, "id": 1, "title": None}]


class HandoutVocabulary(BaseModel):
    """讲义词汇（带来源类型）"""
    id: int
    word: str
    definition: Optional[str] = None
    phonetic: Optional[str] = None
    frequency: int
    source_type: str  # 'both' | 'reading' | 'cloze'


class WordAnalysisPoint(BaseModel):
    """词义辨析考点（聚合后）"""
    word: str
    frequency: int
    definition: Optional[str] = None
    word_analysis: Optional[Dict] = None
    dictionary_source: Optional[str] = None
    occurrences: List[PointOccurrence] = []


class FixedPhrasePoint(BaseModel):
    """固定搭配考点（聚合后）"""
    word: str
    frequency: int
    phrase: Optional[str] = None
    similar_phrases: Optional[List[str]] = None
    occurrences: List[PointOccurrence] = []


class RareMeaningPoint(BaseModel):
    """熟词僻义考点（聚合后）"""
    word: str
    frequency: int
    textbook_meaning: Optional[str] = None
    textbook_source: Optional[str] = None
    context_meaning: Optional[str] = None
    similar_words: Optional[List[Dict]] = None
    occurrences: List[PointOccurrence] = []


class PointsByType(BaseModel):
    """按类型分组的考点"""
    词义辨析: List[WordAnalysisPoint] = []
    固定搭配: List[FixedPhrasePoint] = []
    熟词僻义: List[RareMeaningPoint] = []


class ClozeHandoutPassage(BaseModel):
    """完形讲义文章"""
    id: int
    content: str
    word_count: Optional[int] = None
    source: Optional[SourceInfo] = None
    points: List[ClozePointResponse] = []


class ClozeTopicContent(BaseModel):
    """完形主题内容"""
    topic: str
    part1_article_sources: List[ArticleSource] = []
    part2_vocabulary: List[HandoutVocabulary] = []
    part3_points_by_type: PointsByType = PointsByType()
    part4_passages: List[ClozeHandoutPassage] = []


class ClozeHandoutDetailResponse(BaseModel):
    """完形讲义详情响应"""
    topic: str
    grade: str
    edition: str
    part1_article_sources: List[ArticleSource] = []
    part2_vocabulary: List[HandoutVocabulary] = []
    part3_points_by_type: PointsByType = PointsByType()
    part4_passages: List[ClozeHandoutPassage] = []


class ClozeGradeHandoutResponse(BaseModel):
    """完形年级讲义响应"""
    grade: str
    edition: str
    topics: List[ClozeTopicStats] = []
    content: List[ClozeTopicContent] = []
