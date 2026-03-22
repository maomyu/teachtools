"""
讲义转换相关的请求/响应 Schema
"""
from pydantic import BaseModel
from typing import Optional


class UploadResponse(BaseModel):
    """上传响应"""
    task_id: str
    filename: str
    file_size: int


class ProcessRequest(BaseModel):
    """处理请求"""
    task_id: str
    watermark_text: str = "学生版"


class ProcessStatus(BaseModel):
    """处理状态"""
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: int  # 0-100
    message: str
    download_url: Optional[str] = None
    error: Optional[str] = None


class ConversionResult(BaseModel):
    """转换结果"""
    success: bool
    pdf_path: Optional[str] = None
    answers_removed: int = 0
    original_file: str
    error: Optional[str] = None
