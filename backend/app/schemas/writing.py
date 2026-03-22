"""
作文模块 Schema

[INPUT]: 依赖 pydantic BaseModel
[OUTPUT]: 对外提供作文相关的 Pydantic 模型
[POS]: backend/app/schemas 的作文 schema 定义
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, field_validator
from enum import Enum


# ==============================================================================
#                              ENUMS
# ==============================================================================

class GradeEnum(str, Enum):
    """年级枚举"""
    GRADE_7 = "初一"
    GRADE_8 = "初二"
    GRADE_9 = "初三"


class SemesterEnum(str, Enum):
    """学期枚举"""
    FIRST = "上学期"
    SECOND = "下学期"


class ExamTypeEnum(str, Enum):
    """考试类型枚举"""
    MIDTERM = "期中"
    FINAL = "期末"
    FIRST_MODEL = "一模"
    ZHONGKAO = "中考"
    OTHER = "其他"


class WritingTypeEnum(str, Enum):
    """文体类型枚举"""
    APPLICATION = "应用文"
    NARRATIVE = "记叙文"
    OTHER = "其他"


# ==============================================================================
#                              BASE MODELS
# ==============================================================================

class SourceInfo(BaseModel):
    """出处信息"""
    year: Optional[int] = None
    region: Optional[str] = None
    school: Optional[str] = None
    grade: Optional[str] = None
    exam_type: Optional[str] = None
    semester: Optional[str] = None
    filename: Optional[str] = None


class WritingTaskBase(BaseModel):
    """作文题目基础信息"""
    task_content: str
    requirements: Optional[str] = None
    word_limit: Optional[str] = None
    points_value: Optional[str] = None


# ==============================================================================
#                              REQUEST MODELS
# ==============================================================================

class WritingFilter(BaseModel):
    """作文筛选参数"""
    page: int = 1
    size: int = 20
    grade: Optional[str] = None
    semester: Optional[str] = None
    exam_type: Optional[str] = None
    writing_type: Optional[str] = None
    application_type: Optional[str] = None
    topic: Optional[str] = None
    search: Optional[str] = None


class WritingTypeUpdateRequest(BaseModel):
    """文体更新请求"""
    writing_type: str
    application_type: Optional[str] = None


class TopicUpdateRequest(BaseModel):
    """话题更新请求"""
    primary_topic: str
    secondary_topics: Optional[List[str]] = None
    verified_by: Optional[str] = None


class BatchGenerateRequest(BaseModel):
    """批量范文生成请求"""
    task_ids: List[int]

    @field_validator('task_ids')
    @classmethod
    def validate_task_ids(cls, v):
        if len(v) > 100:
            raise ValueError('批量生成数量不能超过 100')
        if len(v) == 0:
            raise ValueError('请选择至少一篇作文')
        return list(set(v))  # 去重


# ==============================================================================
#                              RESPONSE MODELS
# ==============================================================================

class WritingTaskResponse(WritingTaskBase):
    """作文题目响应"""
    id: int
    paper_id: int
    grade: Optional[str] = None
    semester: Optional[str] = None
    exam_type: Optional[str] = None
    writing_type: Optional[str] = None
    application_type: Optional[str] = None
    primary_topic: Optional[str] = None
    topic_verified: bool = False
    source: Optional[SourceInfo] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WritingTaskListResponse(BaseModel):
    """作文列表响应"""
    total: int
    items: List[WritingTaskResponse]
    grade_counts: dict = {}  # 各年级数量统计


class TemplateResponse(BaseModel):
    """模板响应"""
    id: int
    writing_type: str
    application_type: Optional[str] = None
    template_name: str
    template_content: str
    tips: Optional[str] = None
    structure: Optional[str] = None
    created_at: datetime


class SampleResponse(BaseModel):
    """范文响应"""
    id: int
    task_id: Optional[int] = None
    template_id: Optional[int] = None
    sample_content: str
    sample_type: str
    score_level: Optional[str] = None
    word_count: Optional[int] = None  # 实际字数
    translation: Optional[str] = None  # 中文翻译
    created_at: datetime


class WritingTaskDetailResponse(WritingTaskResponse):
    """作文详情响应（含模板和范文）"""
    templates: List[TemplateResponse] = []
    samples: List[SampleResponse] = []


class WritingTypeDetectResponse(BaseModel):
    """文体识别响应"""
    task_id: int
    writing_type: str
    application_type: Optional[str] = None
    confidence: float
    reasoning: Optional[str] = None


class BatchGenerateResponse(BaseModel):
    """批量生成响应"""
    success_count: int
    fail_count: int
    results: List[dict]


class WritingFiltersResponse(BaseModel):
    """筛选项响应"""
    grades: List[str] = []
    semesters: List[str] = []
    exam_types: List[str] = []
    writing_types: List[str] = []
    application_types: List[str] = []
    topics: List[str] = []


# ==============================================================================
#                              MATERIAL MODELS
# ==============================================================================

class MaterialResponse(BaseModel):
    """素材响应"""
    id: int
    topic: str
    sentence_patterns: List[str] = []
    vocabulary: List[str] = []
    tips: Optional[str] = None
    created_at: datetime


class MaterialListResponse(BaseModel):
    """素材列表响应"""
    items: List[MaterialResponse]


# ==============================================================================
#                              HANDOUT MODELS
# ==============================================================================

class WritingHandoutTopicStats(BaseModel):
    """作文讲义话题统计"""
    topic: str
    task_count: int  # 题目数量
    sample_count: int  # 范文数量
    recent_years: List[int] = []


class WritingFrameworkSection(BaseModel):
    """写作框架段落"""
    name: str  # 开头句/背景句/中心句/主体段/结尾句
    description: str  # 段落说明
    examples: List[str] = []  # 示例句子


class WritingFramework(BaseModel):
    """写作框架"""
    writing_type: str  # 应用文/记叙文
    sections: List[WritingFrameworkSection]


class HighFrequencyExpression(BaseModel):
    """高频表达"""
    category: str  # 开头句型/结尾句型/过渡词汇/高级词汇
    items: List[str]


class HighlightedSentence(BaseModel):
    """重点句标注"""
    sentence: str  # 完整句子
    highlight_type: str  # 高级词汇/复杂句型/地道表达/过渡词
    explanation: str  # 亮点说明


class HandoutSampleSource(BaseModel):
    """讲义范文来源"""
    year: Optional[int] = None
    region: Optional[str] = None
    exam_type: Optional[str] = None
    semester: Optional[str] = None


class HandoutSample(BaseModel):
    """讲义范文"""
    id: int
    task_content: str  # 题目
    sample_content: str  # 范文正文
    translation: Optional[str] = None  # 中文翻译
    word_count: Optional[int] = None
    highlighted_sentences: List[HighlightedSentence] = []  # 重点句标注
    source: Optional[HandoutSampleSource] = None


class WritingHandoutDetailResponse(BaseModel):
    """作文讲义详情响应（四段式）"""
    topic: str
    grade: str
    edition: str  # teacher/student

    # Part 1: 话题统计
    part1_topic_stats: WritingHandoutTopicStats

    # Part 2: 写作框架
    part2_frameworks: List[WritingFramework] = []

    # Part 3: 高频表达
    part3_expressions: List[HighFrequencyExpression] = []

    # Part 4: 范文展示
    part4_samples: List[HandoutSample] = []


class WritingGradeHandoutResponse(BaseModel):
    """年级作文讲义响应"""
    grade: str
    edition: str  # teacher/student
    topics: List[WritingHandoutTopicStats] = []  # 话题统计列表
    content: List[WritingHandoutDetailResponse] = []  # 各话题讲义内容
