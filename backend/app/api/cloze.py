"""
完形填空 API 路由

[INPUT]: 依赖 FastAPI, SQLAlchemy, app.models, app.schemas
[OUTPUT]: 对外提供完形填空相关的 REST API
[POS]: backend/app/api 的完形路由
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.cloze import ClozePassage, ClozePoint
from app.models.paper import ExamPaper
from app.models.vocabulary_cloze import VocabularyCloze
from app.models.vocabulary import Vocabulary
from app.schemas.cloze import (
    ClozeListResponse,
    ClozeDetailResponse,
    ClozePassageResponse,
    ClozePointResponse,
    PointListResponse,
    PointSummary,
    PointOccurrence,
    TopicUpdateRequest,
    PointUpdateRequest,
    VocabularyInCloze,
    ClozeFilters,
    SourceInfo,
)

router = APIRouter()


# ============================================================================
#  筛选器（必须放在 /{cloze_id} 之前）
# ============================================================================

@router.get("/filters/", response_model=ClozeFilters)
async def get_cloze_filters(db: AsyncSession = Depends(get_db)):
    """获取完形筛选器选项"""
    # 获取所有年级
    grades_result = await db.execute(
        select(distinct(ExamPaper.grade)).join(ClozePassage).where(ExamPaper.grade != None)
    )
    grades = [g[0] for g in grades_result.fetchall() if g[0]]

    # 获取所有话题
    topics_result = await db.execute(
        select(distinct(ClozePassage.primary_topic)).where(ClozePassage.primary_topic != None)
    )
    topics = [t[0] for t in topics_result.fetchall() if t[0]]

    # 获取所有年份
    years_result = await db.execute(
        select(distinct(ExamPaper.year)).join(ClozePassage).where(ExamPaper.year != None)
    )
    years = [y[0] for y in years_result.fetchall() if y[0]]

    # 获取所有区县
    regions_result = await db.execute(
        select(distinct(ExamPaper.region)).join(ClozePassage).where(ExamPaper.region != None)
    )
    regions = [r[0] for r in regions_result.fetchall() if r[0]]

    # 获取所有考试类型
    exam_types_result = await db.execute(
        select(distinct(ExamPaper.exam_type)).join(ClozePassage).where(ExamPaper.exam_type != None)
    )
    exam_types = [e[0] for e in exam_types_result.fetchall() if e[0]]

    # 获取所有考点类型
    point_types_result = await db.execute(
        select(distinct(ClozePoint.point_type)).where(ClozePoint.point_type != None)
    )
    point_types = [p[0] for p in point_types_result.fetchall() if p[0]]

    # 获取所有学期
    semesters_result = await db.execute(
        select(distinct(ExamPaper.semester)).join(ClozePassage).where(ExamPaper.semester != None)
    )
    semesters = [s[0] for s in semesters_result.fetchall() if s[0]]

    return ClozeFilters(
        grades=sorted(grades),
        topics=sorted(topics),
        years=sorted(years, reverse=True),
        regions=sorted(regions),
        exam_types=sorted(exam_types),
        point_types=sorted(point_types),
        semesters=sorted(semesters)
    )


# ============================================================================
#  完形文章列表
# ============================================================================

@router.get("/", response_model=ClozeListResponse)
async def list_cloze(
    grade: Optional[str] = None,
    topic: Optional[str] = None,
    point_type: Optional[str] = None,
    exam_type: Optional[str] = None,
    semester: Optional[str] = None,
    region: Optional[str] = None,
    year: Optional[int] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取完形文章列表"""
    query = select(ClozePassage).options(
        selectinload(ClozePassage.points),
        selectinload(ClozePassage.paper)
    )

    # 筛选条件
    if grade:
        query = query.join(ExamPaper).where(ExamPaper.grade == grade)
    if region:
        query = query.join(ExamPaper).where(ExamPaper.region == region)
    if year:
        query = query.join(ExamPaper).where(ExamPaper.year == year)
    if topic:
        query = query.where(ClozePassage.primary_topic == topic)
    if exam_type:
        query = query.join(ExamPaper).where(ExamPaper.exam_type == exam_type)
    if semester:
        query = query.join(ExamPaper).where(ExamPaper.semester == semester)
    if point_type:
        query = query.join(ClozePoint).where(ClozePoint.point_type == point_type)

    # 计数
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 分页
    query = query.offset((page - 1) * size).limit(size)
    query = query.order_by(ClozePassage.created_at.desc())

    result = await db.execute(query)
    passages = result.scalars().all()

    # 构建响应
    items = []
    for p in passages:
        # 统计考点分布
        point_dist = {}
        for point in p.points:
            if point.point_type:
                point_dist[point.point_type] = point_dist.get(point.point_type, 0) + 1

        source = None
        if p.paper:
            source = SourceInfo(
                year=p.paper.year,
                region=p.paper.region,
                grade=p.paper.grade,
                semester=p.paper.semester,
                exam_type=p.paper.exam_type,
                filename=p.paper.filename
            )

        items.append(ClozePassageResponse(
            id=p.id,
            paper_id=p.paper_id,
            content=p.content,
            original_content=p.original_content,
            word_count=p.word_count,
            primary_topic=p.primary_topic,
            secondary_topics=json.loads(p.secondary_topics) if p.secondary_topics else [],
            topic_confidence=p.topic_confidence,
            source=source,
            points=[ClozePointResponse(
                id=pt.id,
                blank_number=pt.blank_number,
                correct_answer=pt.correct_answer,
                correct_word=pt.correct_word,
                options=json.loads(pt.options) if pt.options else {},
                point_type=pt.point_type,
                translation=pt.translation,
                explanation=pt.explanation,
                confusion_words=json.loads(pt.confusion_words) if pt.confusion_words else None,
                sentence=pt.sentence
            ) for pt in p.points]
        ))

    return {"total": total, "items": items}


# ============================================================================
#  考点汇总（必须放在 /{cloze_id} 之前）
# ============================================================================

@router.get("/points/summary", response_model=PointListResponse)
async def list_points(
    point_type: Optional[str] = None,
    grade: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取考点汇总"""
    query = select(ClozePoint).options(
        selectinload(ClozePoint.cloze).selectinload(ClozePassage.paper)
    )

    # 筛选
    if point_type:
        query = query.where(ClozePoint.point_type == point_type)
    if grade:
        query = query.join(ClozePassage).join(ExamPaper).where(ExamPaper.grade == grade)
    if keyword:
        query = query.where(ClozePoint.correct_word.contains(keyword))

    # 分页
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    query = query.offset((page - 1) * size).limit(size)

    result = await db.execute(query)
    points = result.scalars().all()

    # 构建响应
    items = []
    for pt in points:
        source = ""
        if pt.cloze and pt.cloze.paper:
            paper = pt.cloze.paper
            source = f"{paper.year}{paper.region}{paper.grade}{paper.exam_type or ''}·完形"

        items.append(PointSummary(
            word=pt.correct_word or "",
            definition=pt.translation,
            frequency=1,
            point_type=pt.point_type or "词汇",
            occurrences=[PointOccurrence(
                sentence=pt.sentence or "",
                source=source,
                blank_number=pt.blank_number,
                point_type=pt.point_type or "词汇",
                explanation=pt.explanation,
                passage_id=pt.cloze_id
            )]
        ))

    return {"total": total, "items": items}


# ============================================================================
#  完形文章详情
# ============================================================================

@router.get("/{cloze_id}/", response_model=ClozeDetailResponse)
async def get_cloze(
    cloze_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取完形文章详情"""
    result = await db.execute(
        select(ClozePassage)
        .options(
            selectinload(ClozePassage.points),
            selectinload(ClozePassage.paper)
        )
        .where(ClozePassage.id == cloze_id)
    )
    passage = result.scalar_one_or_none()

    if not passage:
        raise HTTPException(status_code=404, detail="完形文章不存在")

    # 统计考点分布
    point_dist = {}
    for pt in passage.points:
        if pt.point_type:
            point_dist[pt.point_type] = point_dist.get(pt.point_type, 0) + 1

    source = None
    if passage.paper:
        source = SourceInfo(
            year=passage.paper.year,
            region=passage.paper.region,
            grade=passage.paper.grade,
            semester=passage.paper.semester,
            exam_type=passage.paper.exam_type,
            filename=passage.paper.filename
        )

    # 查询关联的词汇
    vocab_result = await db.execute(
        select(Vocabulary, VocabularyCloze)
        .join(VocabularyCloze, VocabularyCloze.vocabulary_id == Vocabulary.id)
        .where(VocabularyCloze.cloze_id == cloze_id)
    )
    vocab_rows = vocab_result.all()

    # 按词汇分组，聚合 frequency
    vocab_map = {}
    for vocab, vocab_cloze in vocab_rows:
        if vocab.id not in vocab_map:
            vocab_map[vocab.id] = VocabularyInCloze(
                id=vocab.id,
                word=vocab.word,
                definition=vocab.definition,
                frequency=0,
                sentence=vocab_cloze.sentence,
                char_position=vocab_cloze.char_position
            )
        vocab_map[vocab.id].frequency += 1

    vocabulary = list(vocab_map.values())

    return ClozeDetailResponse(
        id=passage.id,
        paper_id=passage.paper_id,
        content=passage.content,
        original_content=passage.original_content,
        word_count=passage.word_count,
        primary_topic=passage.primary_topic,
        secondary_topics=json.loads(passage.secondary_topics) if passage.secondary_topics else [],
        topic_confidence=passage.topic_confidence,
        source=source,
        points=[ClozePointResponse(
            id=pt.id,
            blank_number=pt.blank_number,
            correct_answer=pt.correct_answer,
            correct_word=pt.correct_word,
            options=json.loads(pt.options) if pt.options else {},
            point_type=pt.point_type,
            translation=pt.translation,
            explanation=pt.explanation,
            confusion_words=json.loads(pt.confusion_words) if pt.confusion_words else None,
            sentence=pt.sentence
        ) for pt in passage.points],
        point_distribution=point_dist,
        vocabulary=vocabulary
    )


# ============================================================================
#  更新接口
# ============================================================================

@router.put("/{cloze_id}/topic")
async def update_cloze_topic(
    cloze_id: int,
    data: TopicUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """更新完形话题（人工校对）"""
    result = await db.execute(
        select(ClozePassage).where(ClozePassage.id == cloze_id)
    )
    passage = result.scalar_one_or_none()

    if not passage:
        raise HTTPException(status_code=404, detail="完形文章不存在")

    passage.primary_topic = data.primary_topic
    passage.secondary_topics = json.dumps(data.secondary_topics or [], ensure_ascii=False)
    if data.verified:
        passage.topic_verified = True

    await db.commit()
    return {"message": "话题更新成功"}


@router.put("/blanks/{blank_id}/point")
async def update_blank_point(
    blank_id: int,
    data: PointUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """更新考点分析（人工校对）"""
    result = await db.execute(
        select(ClozePoint).where(ClozePoint.id == blank_id)
    )
    point = result.scalar_one_or_none()

    if not point:
        raise HTTPException(status_code=404, detail="考点不存在")

    point.point_type = data.point_type
    point.explanation = data.explanation
    point.translation = data.translation
    if data.confusion_words:
        point.confusion_words = json.dumps(data.confusion_words, ensure_ascii=False)

    await db.commit()
    return {"message": "考点更新成功"}
