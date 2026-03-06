"""
词汇模块API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.vocabulary import Vocabulary, VocabularyPassage
from app.schemas.vocabulary import (
    VocabularyResponse,
    VocabularyListResponse,
    VocabularySearchResponse,
    VocabularyOccurrence
)

router = APIRouter()


@router.get("", response_model=VocabularyListResponse)
async def list_vocabulary(
    grade: Optional[str] = None,
    topic: Optional[str] = None,
    min_frequency: int = 1,
    page: int = 1,
    size: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """获取高频词汇列表"""
    query = select(Vocabulary)

    # 按词频筛选
    query = query.where(Vocabulary.frequency >= min_frequency)

    # TODO: 按年级和话题筛选（需要JOIN）

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # 分页并按词频排序
    query = query.order_by(Vocabulary.frequency.desc())
    query = query.offset((page - 1) * size).limit(size)

    result = await db.execute(query)
    words = result.scalars().all()

    return VocabularyListResponse(
        total=total or 0,
        items=[VocabularyResponse.model_validate(w) for w in words]
    )


@router.get("/search", response_model=VocabularySearchResponse)
async def search_vocabulary(
    word: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db)
):
    """搜索单词"""
    # 查找单词
    query = select(Vocabulary).where(Vocabulary.word == word.lower())
    vocab = await db.scalar(query)

    if not vocab:
        raise HTTPException(status_code=404, detail="单词不存在")

    # 获取所有出现位置
    occ_query = select(VocabularyPassage).where(
        VocabularyPassage.vocabulary_id == vocab.id
    ).options(selectinload(VocabularyPassage.passage))

    result = await db.execute(occ_query)
    occurrences = result.scalars().all()

    return VocabularySearchResponse(
        word=vocab.word,
        definition=vocab.definition,
        frequency=vocab.frequency,
        occurrences=[
            VocabularyOccurrence(
                sentence=occ.sentence,
                passage_id=occ.passage_id,
                char_position=occ.char_position,
                end_position=occ.end_position,
                source=f"{occ.passage.paper.year if occ.passage.paper else ''} {occ.passage.paper.region if occ.passage.paper else ''}"
            )
            for occ in occurrences
        ]
    )
