"""
作文模块 Schema

[INPUT]: 依赖 pydantic BaseModel
[OUTPUT]: 对外提供作文分类树、列表、详情与讲义相关 Schema
[POS]: backend/app/schemas 的作文 schema 定义
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, field_validator


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


class SourceInfo(BaseModel):
    """出处信息"""

    year: Optional[int] = None
    region: Optional[str] = None
    school: Optional[str] = None
    grade: Optional[str] = None
    exam_type: Optional[str] = None
    semester: Optional[str] = None
    filename: Optional[str] = None


class WritingCategoryResponse(BaseModel):
    """作文分类节点"""

    id: int
    code: str
    name: str
    level: int
    parent_id: Optional[int] = None
    path: str
    template_key: str

    class Config:
        from_attributes = True


class WritingTaskBase(BaseModel):
    """作文题目基础信息"""

    task_content: str
    requirements: Optional[str] = None
    word_limit: Optional[str] = None
    points_value: Optional[str] = None


class WritingFilter(BaseModel):
    """作文筛选参数"""

    page: int = 1
    size: int = 20
    grade: Optional[str] = None
    semester: Optional[str] = None
    exam_type: Optional[str] = None
    group_category_id: Optional[int] = None
    major_category_id: Optional[int] = None
    category_id: Optional[int] = None
    search: Optional[str] = None


class BatchGenerateRequest(BaseModel):
    """批量范文生成请求"""

    task_ids: List[int]

    @field_validator("task_ids")
    @classmethod
    def validate_task_ids(cls, value: List[int]) -> List[int]:
        if len(value) > 100:
            raise ValueError("批量生成数量不能超过 100")
        if len(value) == 0:
            raise ValueError("请选择至少一篇作文")
        return list(dict.fromkeys(value))


class WritingTaskResponse(WritingTaskBase):
    """作文题目响应"""

    id: int
    paper_id: int
    grade: Optional[str] = None
    semester: Optional[str] = None
    exam_type: Optional[str] = None
    group_category: Optional[WritingCategoryResponse] = None
    major_category: Optional[WritingCategoryResponse] = None
    category: Optional[WritingCategoryResponse] = None
    category_confidence: float = 0.0
    category_reasoning: Optional[str] = None
    training_word_target: str = "150词左右"
    source: Optional[SourceInfo] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WritingTaskListResponse(BaseModel):
    """作文列表响应"""

    total: int
    items: List[WritingTaskResponse]
    grade_counts: dict = {}


class TemplateResponse(BaseModel):
    """模板响应"""

    id: int
    category: WritingCategoryResponse
    template_name: str
    template_content: str
    tips: Optional[str] = None
    structure: Optional[str] = None
    template_schema_json: Optional[str] = None
    template_version: int = 1
    quality_status: str = "pending"
    representative_sample_content: Optional[str] = None
    representative_translation: Optional[str] = None
    representative_rendered_slots_json: Optional[str] = None
    representative_word_count: Optional[int] = None
    opening_sentences: Optional[str] = None
    closing_sentences: Optional[str] = None
    transition_words: Optional[str] = None
    advanced_vocabulary: Optional[str] = None
    grammar_points: Optional[str] = None
    scoring_criteria: Optional[str] = None
    created_at: datetime


class SampleResponse(BaseModel):
    """范文响应"""

    id: int
    task_id: Optional[int] = None
    template_id: Optional[int] = None
    sample_content: str
    sample_type: str
    score_level: Optional[str] = None
    word_count: Optional[int] = None
    translation: Optional[str] = None
    rendered_slots_json: Optional[str] = None
    template_version: int = 1
    generation_mode: str = "slot_fill"
    quality_status: str = "pending"
    created_at: datetime


class WritingTaskDetailResponse(WritingTaskResponse):
    """作文详情响应（含模板和范文）"""

    templates: List[TemplateResponse] = []
    samples: List[SampleResponse] = []


class WritingTypeDetectResponse(BaseModel):
    """作文分类响应"""

    task_id: int
    group_category: Optional[WritingCategoryResponse] = None
    major_category: Optional[WritingCategoryResponse] = None
    category: Optional[WritingCategoryResponse] = None
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
    groups: List[WritingCategoryResponse] = []
    major_categories: List[WritingCategoryResponse] = []
    categories: List[WritingCategoryResponse] = []


class WritingFrameworkSection(BaseModel):
    """写作框架段落"""

    name: str
    description: str
    examples: List[str] = []


class WritingFramework(BaseModel):
    """写作框架"""

    title: str
    category_name: str
    sections: List[WritingFrameworkSection]


class HighFrequencyExpression(BaseModel):
    """高频表达"""

    category: str
    items: List[str]


class HighlightedSentence(BaseModel):
    """重点句标注"""

    sentence: str
    highlight_type: str
    explanation: str


class HandoutSampleSource(BaseModel):
    """讲义范文来源"""

    year: Optional[int] = None
    region: Optional[str] = None
    exam_type: Optional[str] = None
    semester: Optional[str] = None


class HandoutSample(BaseModel):
    """讲义范文"""

    id: int
    task_content: str
    sample_content: str
    translation: Optional[str] = None
    word_count: Optional[int] = None
    highlighted_sentences: List[HighlightedSentence] = []
    source: Optional[HandoutSampleSource] = None


class WritingHandoutCategorySummary(BaseModel):
    """作文讲义子类统计"""

    group_name: str
    major_category_name: str
    category_name: str
    task_count: int
    sample_count: int
    recent_years: List[int] = []
    applicable_ranges: List[str] = []


class WritingHandoutCategorySection(BaseModel):
    """单个子类讲义内容"""

    group_category: WritingCategoryResponse
    major_category: WritingCategoryResponse
    category: WritingCategoryResponse
    summary: WritingHandoutCategorySummary
    frameworks: List[WritingFramework] = []
    expressions: List[HighFrequencyExpression] = []
    samples: List[HandoutSample] = []
    template_content: Optional[str] = None


class WritingHandoutGroupResponse(BaseModel):
    """讲义一级分组"""

    group_category: WritingCategoryResponse
    sections: List[WritingHandoutCategorySection] = []


class WritingGradeHandoutResponse(BaseModel):
    """年级作文讲义响应"""

    grade: str
    edition: str
    total_task_count: int = 0
    groups: List[WritingHandoutGroupResponse] = []


class WritingTemplateListItem(BaseModel):
    """作文模板列表项"""

    id: int
    group_category: WritingCategoryResponse
    major_category: WritingCategoryResponse
    category: WritingCategoryResponse
    template_name: str
    template_content: str
    structure: Optional[str] = None
    template_schema_json: Optional[str] = None
    template_version: int = 1
    quality_status: str = "pending"
    representative_sample_content: Optional[str] = None
    representative_translation: Optional[str] = None
    representative_word_count: Optional[int] = None
    paper_count: int = 0
    task_count: int = 0
    updated_at: Optional[datetime] = None


class WritingTemplateListResponse(BaseModel):
    """作文模板列表响应"""

    total: int
    total_paper_count: int = 0
    total_task_count: int = 0
    items: List[WritingTemplateListItem] = []


class WritingTemplatePaperItem(BaseModel):
    """模板下的试卷列表项"""

    paper_id: int
    filename: str
    year: Optional[int] = None
    region: Optional[str] = None
    school: Optional[str] = None
    grade: Optional[str] = None
    exam_type: Optional[str] = None
    semester: Optional[str] = None
    task_count: int = 0


class WritingTemplatePaperListResponse(BaseModel):
    """模板下试卷列表响应"""

    template: WritingTemplateListItem
    papers: List[WritingTemplatePaperItem] = []


class WritingTemplatePaperDetailResponse(BaseModel):
    """模板下单张试卷详情"""

    template: TemplateResponse
    paper: SourceInfo
    tasks: List[WritingTaskDetailResponse] = []
