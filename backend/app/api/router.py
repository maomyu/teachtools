"""
API路由汇总

[INPUT]: 依赖各模块 API 路由
[OUTPUT]: 对外提供统一的 api_router
[POS]: backend/app/api 的路由注册中心
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from fastapi import APIRouter

from app.api.papers import router as papers_router
from app.api.reading import router as reading_router
from app.api.vocabulary import router as vocabulary_router
from app.api.topics import router as topics_router
from app.api.cloze import router as cloze_router
from app.api.textbook import router as textbook_router
from app.api.writing import router as writing_router
from app.api.handout import router as handout_router

api_router = APIRouter()

# 注册各模块路由
api_router.include_router(papers_router, prefix="/papers", tags=["试卷管理"])
api_router.include_router(reading_router, prefix="/passages", tags=["阅读模块"])
api_router.include_router(vocabulary_router, prefix="/vocabulary", tags=["词汇模块"])
api_router.include_router(topics_router, prefix="/topics", tags=["话题管理"])
api_router.include_router(cloze_router, prefix="/cloze", tags=["完形填空"])
api_router.include_router(textbook_router, prefix="/textbook-vocab", tags=["课本单词表"])
api_router.include_router(writing_router, prefix="/writings", tags=["作文模块"])
api_router.include_router(handout_router, prefix="/handout", tags=["讲义转换"])
