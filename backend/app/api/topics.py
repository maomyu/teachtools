"""
话题管理API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.topic import Topic
from app.schemas.topic import TopicResponse, TopicListResponse

router = APIRouter()


@router.get("", response_model=TopicListResponse)
async def list_topics(
    grade: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取话题列表"""
    query = select(Topic)

    if grade:
        query = query.where(Topic.grade_level == grade)

    query = query.order_by(Topic.grade_level, Topic.sort_order)

    result = await db.execute(query)
    topics = result.scalars().all()

    # 按年级分组
    grouped = {}
    for topic in topics:
        grade = topic.grade_level
        if grade not in grouped:
            grouped[grade] = []
        grouped[grade].append(TopicResponse.model_validate(topic))

    return TopicListResponse(topics_by_grade=grouped)
