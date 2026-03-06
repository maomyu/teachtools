"""
阅读模块Schema
"""
import json
from datetime import datetime
from typing import Optional, List, Any, Union
from pydantic import BaseModel, field_validator


class SourceInfo(BaseModel):
    """出处信息"""
    year: Optional[int] = None
    region: Optional[str] = None
    school: Optional[str] = None
    grade: Optional[str] = None
    exam_type: Optional[str] = None
    filename: Optional[str] = None


class PassageBase(BaseModel):
    """文章基础信息"""
    passage_type: str
    title: Optional[str] = None
    content: str
    word_count: Optional[int] = None


class PassageResponse(PassageBase):
    """文章响应"""
    id: int
    paper_id: int
    primary_topic: Optional[str] = None
    secondary_topics: Optional[List[str]] = None
    topic_confidence: Optional[float] = None
    topic_verified: bool = False
    source: Optional[SourceInfo] = None
    created_at: datetime

    class Config:
        from_attributes = True

    @field_validator('secondary_topics', mode='before')
    @classmethod
    def parse_secondary_topics(cls, v):
        """解析JSON字符串格式的secondary_topics"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except:
                return None
        return v

    @field_validator('source', mode='before')
    @classmethod
    def parse_source(cls, v, info):
        """从source_info属性映射到source"""
        if v is not None:
            return v
        # 尝试从原始对象获取source_info
        if info.data and 'source_info' in info.data:
            source_info = info.data['source_info']
            if source_info:
                return SourceInfo(**source_info)
        return None


class PassageListResponse(BaseModel):
    """文章列表响应"""
    total: int
    items: List[PassageResponse]


class VocabularyOccurrenceInPassage(BaseModel):
    """文章中的词汇出现"""
    sentence: str
    char_position: int
    end_position: Optional[int] = None


class VocabularyInPassage(BaseModel):
    """文章详情中的词汇"""
    id: int
    word: str
    definition: Optional[str] = None
    frequency: int
    occurrences: List[VocabularyOccurrenceInPassage]


class QuestionOptions(BaseModel):
    """题目选项"""
    A: Optional[str] = None
    B: Optional[str] = None
    C: Optional[str] = None
    D: Optional[str] = None


class QuestionResponse(BaseModel):
    """题目响应"""
    id: int
    question_number: Optional[int] = None
    question_text: str
    options: QuestionOptions
    correct_answer: Optional[str] = None
    answer_explanation: Optional[str] = None


class PassageDetailResponse(PassageResponse):
    """文章详情响应（含词汇和题目）"""
    vocabulary: List[VocabularyInPassage] = []
    questions: List[QuestionResponse] = []
    has_questions: bool = False


class TopicUpdateRequest(BaseModel):
    """话题更新请求"""
    primary_topic: str
    secondary_topics: Optional[List[str]] = None
    verified_by: Optional[str] = None
