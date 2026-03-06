"""
API路由汇总
"""
from fastapi import APIRouter

from app.api.papers import router as papers_router
from app.api.reading import router as reading_router
from app.api.vocabulary import router as vocabulary_router
from app.api.topics import router as topics_router

api_router = APIRouter()

# 注册各模块路由
api_router.include_router(papers_router, prefix="/papers", tags=["试卷管理"])
api_router.include_router(reading_router, prefix="/passages", tags=["阅读模块"])
api_router.include_router(vocabulary_router, prefix="/vocabulary", tags=["词汇模块"])
api_router.include_router(topics_router, prefix="/topics", tags=["话题管理"])
