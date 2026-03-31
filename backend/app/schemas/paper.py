"""
试卷相关Schema
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class PaperBase(BaseModel):
    """试卷基础信息"""
    filename: str
    year: Optional[int] = None
    region: Optional[str] = None
    school: Optional[str] = None
    grade: Optional[str] = None
    semester: Optional[str] = None
    exam_type: Optional[str] = None
    version: Optional[str] = None


class PaperCreate(PaperBase):
    """创建试卷请求"""
    original_path: Optional[str] = None


class PaperResponse(PaperBase):
    """试卷响应"""
    id: int
    original_path: Optional[str] = None
    import_status: str
    parse_strategy: Optional[str] = None
    confidence: float = 0.0
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaperListResponse(BaseModel):
    """试卷列表响应"""
    total: int
    items: List[PaperResponse]


# ============================================================================
#  讲义生成状态相关 Schema
# ============================================================================

class PaperHandoutStatus(BaseModel):
    """试卷讲义状态"""
    id: int
    filename: str
    year: Optional[int] = None
    region: Optional[str] = None
    exam_type: Optional[str] = None
    generated_at: Optional[str] = None

    class Config:
        from_attributes = True


class HandoutStatusResponse(BaseModel):
    """讲义状态响应"""
    generated: List[PaperHandoutStatus]
    not_generated: List[PaperHandoutStatus]


class BatchHandoutUpdateRequest(BaseModel):
    """批量更新讲义生成状态请求"""
    paper_ids: List[int]
    handout_type: str  # reading | cloze | writing
