"""
词汇模块API

[INPUT]: 依赖 SQLAlchemy 异步会话、词汇模型、试卷模型
[OUTPUT]: 对外提供高频词库查询、筛选项、搜索接口
[POS]: backend/app/api 的词汇API模块
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct, and_
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.vocabulary import Vocabulary, VocabularyPassage
from app.models.reading import ReadingPassage
from app.models.paper import ExamPaper
from app.schemas.vocabulary import (
    VocabularyResponse,
    VocabularyListResponse,
    VocabularySearchResponse,
    VocabularyOccurrence,
    VocabularyFiltersResponse,
)

router = APIRouter()


# ============================================================================
#  筛选项接口
# ============================================================================

@router.get("/filters", response_model=VocabularyFiltersResponse)
async def get_vocabulary_filters(db: AsyncSession = Depends(get_db)):
    """
    获取词汇库的筛选项

    返回所有可用的年级、主题、年份、区县、考试类型、学期列表
    """
    # 获取年级列表（去重）
    grades_query = select(distinct(ExamPaper.grade)).where(
        ExamPaper.grade.isnot(None)
    ).order_by(ExamPaper.grade)
    grades_result = await db.execute(grades_query)
    grades = [g for g in grades_result.scalars().all() if g]

    # 获取主题列表（从阅读文章表）
    topics_query = select(distinct(ReadingPassage.primary_topic)).where(
        ReadingPassage.primary_topic.isnot(None)
    ).order_by(ReadingPassage.primary_topic)
    topics_result = await db.execute(topics_query)
    topics = [t for t in topics_result.scalars().all() if t]

    # 获取年份列表
    years_query = select(distinct(ExamPaper.year)).where(
        ExamPaper.year.isnot(None)
    ).order_by(ExamPaper.year.desc())
    years_result = await db.execute(years_query)
    years = [y for y in years_result.scalars().all() if y]

    # 获取区县列表
    regions_query = select(distinct(ExamPaper.region)).where(
        ExamPaper.region.isnot(None)
    ).order_by(ExamPaper.region)
    regions_result = await db.execute(regions_query)
    regions = [r for r in regions_result.scalars().all() if r]

    # 获取考试类型列表
    exam_types_query = select(distinct(ExamPaper.exam_type)).where(
        ExamPaper.exam_type.isnot(None)
    ).order_by(ExamPaper.exam_type)
    exam_types_result = await db.execute(exam_types_query)
    exam_types = [e for e in exam_types_result.scalars().all() if e]

    # 获取学期列表
    semesters_query = select(distinct(ExamPaper.semester)).where(
        ExamPaper.semester.isnot(None)
    ).order_by(ExamPaper.semester)
    semesters_result = await db.execute(semesters_query)
    semesters = [s for s in semesters_result.scalars().all() if s]

    return VocabularyFiltersResponse(
        grades=grades,
        topics=topics,
        years=years,
        regions=regions,
        exam_types=exam_types,
        semesters=semesters
    )


# ============================================================================
#  词汇列表接口
# ============================================================================

@router.get("", response_model=VocabularyListResponse)
async def list_vocabulary(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    # 筛选条件
    grade: Optional[str] = Query(None, description="年级筛选"),
    topic: Optional[str] = Query(None, description="主题筛选"),
    year: Optional[int] = Query(None, description="年份筛选"),
    region: Optional[str] = Query(None, description="区县筛选"),
    exam_type: Optional[str] = Query(None, description="考试类型筛选"),
    semester: Optional[str] = Query(None, description="学期筛选"),
    min_frequency: int = Query(1, ge=1, description="最低词频"),
    search: Optional[str] = Query(None, description="单词搜索"),
    db: AsyncSession = Depends(get_db)
):
    """
    获取高频词汇列表（支持多维度筛选）

    筛选逻辑：
    - 词频基于 VocabularyPassage 实际记录数计算
    - 有筛选条件时：通过 VocabularyPassage → ReadingPassage → ExamPaper 关联筛选
    """
    # 判断是否需要关联查询
    needs_join = any([grade, topic, year, region, exam_type, semester])

    if needs_join:
        # 带筛选条件的查询
        # 步骤1: 找出符合筛选条件的 (vocabulary_id, count) 列表
        vocab_count_subquery = (
            select(
                VocabularyPassage.vocabulary_id,
                func.count(VocabularyPassage.id).label('freq')
            )
            .select_from(VocabularyPassage)
            .join(ReadingPassage, VocabularyPassage.passage_id == ReadingPassage.id)
            .join(ExamPaper, ReadingPassage.paper_id == ExamPaper.id)
            .group_by(VocabularyPassage.vocabulary_id)
            .having(func.count(VocabularyPassage.id) >= min_frequency)
        )

        # 应用筛选条件
        conditions = []
        if grade:
            conditions.append(ExamPaper.grade == grade)
        if topic:
            conditions.append(ReadingPassage.primary_topic == topic)
        if year:
            conditions.append(ExamPaper.year == year)
        if region:
            conditions.append(ExamPaper.region == region)
        if exam_type:
            conditions.append(ExamPaper.exam_type == exam_type)
        if semester:
            conditions.append(ExamPaper.semester == semester)

        if conditions:
            vocab_count_subquery = vocab_count_subquery.where(and_(*conditions))

        vocab_count_subquery = vocab_count_subquery.subquery()

        # 步骤2: 主查询 - 关联 Vocabulary 表获取词汇信息
        query = (
            select(Vocabulary, vocab_count_subquery.c.freq)
            .join(vocab_count_subquery, Vocabulary.id == vocab_count_subquery.c.vocabulary_id)
        )

        # 搜索条件
        if search:
            query = query.where(Vocabulary.word == search.lower())

        # 统计总数
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query) or 0

        # 排序和分页（按实际词频降序）
        query = query.order_by(vocab_count_subquery.c.freq.desc())
        query = query.offset((page - 1) * size).limit(size)

        result = await db.execute(query)
        rows = result.all()

        # 构建响应
        items = []
        for word, actual_frequency in rows:
            occ_query = (
                select(VocabularyPassage)
                .where(VocabularyPassage.vocabulary_id == word.id)
                .options(selectinload(VocabularyPassage.passage).selectinload(ReadingPassage.paper))
                .limit(20)
            )
            occ_result = await db.execute(occ_query)
            occurrences = occ_result.scalars().all()

            items.append(VocabularyResponse(
                id=word.id,
                word=word.word,
                lemma=word.lemma,
                definition=word.definition,
                phonetic=word.phonetic,
                pos=word.pos,
                frequency=actual_frequency,
                occurrences=[
                    VocabularyOccurrence(
                        sentence=occ.sentence,
                        passage_id=occ.passage_id,
                        char_position=occ.char_position,
                        end_position=occ.end_position,
                        source=_format_source(occ.passage),
                        **_get_source_info(occ.passage)
                    )
                    for occ in occurrences
                ]
            ))

    else:
        # 无筛选条件的查询 - 直接从 VocabularyPassage 计算词频
        vocab_count_subquery = (
            select(
                VocabularyPassage.vocabulary_id,
                func.count(VocabularyPassage.id).label('freq')
            )
            .group_by(VocabularyPassage.vocabulary_id)
            .having(func.count(VocabularyPassage.id) >= min_frequency)
            .subquery()
        )

        # 主查询
        query = (
            select(Vocabulary, vocab_count_subquery.c.freq)
            .join(vocab_count_subquery, Vocabulary.id == vocab_count_subquery.c.vocabulary_id)
        )

        # 搜索条件
        if search:
            query = query.where(Vocabulary.word == search.lower())

        # 统计总数
        count_query = select(func.count()).select_from(query.subquery())
        total = await db.scalar(count_query) or 0

        # 排序和分页
        query = query.order_by(vocab_count_subquery.c.freq.desc())
        query = query.offset((page - 1) * size).limit(size)

        result = await db.execute(query)
        rows = result.all()

        # 构建响应
        items = []
        for word, actual_frequency in rows:
            occ_query = (
                select(VocabularyPassage)
                .where(VocabularyPassage.vocabulary_id == word.id)
                .options(selectinload(VocabularyPassage.passage).selectinload(ReadingPassage.paper))
                .limit(20)
            )
            occ_result = await db.execute(occ_query)
            occurrences = occ_result.scalars().all()

            items.append(VocabularyResponse(
                id=word.id,
                word=word.word,
                lemma=word.lemma,
                definition=word.definition,
                phonetic=word.phonetic,
                pos=word.pos,
                frequency=actual_frequency,
                occurrences=[
                    VocabularyOccurrence(
                        sentence=occ.sentence,
                        passage_id=occ.passage_id,
                        char_position=occ.char_position,
                        end_position=occ.end_position,
                        source=_format_source(occ.passage),
                        **_get_source_info(occ.passage)
                    )
                    for occ in occurrences
                ]
            ))

    return VocabularyListResponse(total=total, items=items)


def _format_source(passage: ReadingPassage) -> str:
    """格式化出处信息（用于显示）"""
    if not passage or not passage.paper:
        return ""
    parts = []
    if passage.paper.year:
        parts.append(str(passage.paper.year))
    if passage.paper.region:
        parts.append(passage.paper.region)
    if passage.paper.grade:
        parts.append(passage.paper.grade)
    return " ".join(parts)


def _get_source_info(passage: ReadingPassage) -> dict:
    """获取结构化的出处信息"""
    if not passage or not passage.paper:
        return {}
    return {
        "year": passage.paper.year,
        "region": passage.paper.region,
        "grade": passage.paper.grade,
        "exam_type": passage.paper.exam_type,
        "semester": passage.paper.semester,
    }


# ============================================================================
#  词汇搜索接口
# ============================================================================

@router.get("/search", response_model=VocabularySearchResponse)
async def search_vocabulary(
    word: str = Query(..., min_length=1, description="搜索单词"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(10, ge=1, le=100, description="每页数量"),
    # 筛选条件（与左侧词汇列表一致）
    grade: Optional[str] = Query(None, description="年级筛选"),
    topic: Optional[str] = Query(None, description="主题筛选"),
    year: Optional[int] = Query(None, description="年份筛选"),
    region: Optional[str] = Query(None, description="区县筛选"),
    exam_type: Optional[str] = Query(None, description="考试类型筛选"),
    semester: Optional[str] = Query(None, description="学期筛选"),
    db: AsyncSession = Depends(get_db)
):
    """
    搜索单词详情

    返回单词的出现位置和例句（分页）
    支持与左侧词汇列表相同的筛选条件
    """
    # 查找单词
    query = select(Vocabulary).where(Vocabulary.word == word.lower())
    vocab = await db.scalar(query)

    if not vocab:
        raise HTTPException(status_code=404, detail="单词不存在")

    # 判断是否有筛选条件
    has_filters = any([grade, topic, year, region, exam_type, semester])

    # 基础查询
    base_query = (
        select(VocabularyPassage)
        .where(VocabularyPassage.vocabulary_id == vocab.id)
    )

    if has_filters:
        # 带筛选：JOIN ReadingPassage 和 ExamPaper
        base_query = (
            base_query
            .join(ReadingPassage, VocabularyPassage.passage_id == ReadingPassage.id)
            .join(ExamPaper, ReadingPassage.paper_id == ExamPaper.id)
        )

        # 应用筛选条件
        conditions = []
        if grade:
            conditions.append(ExamPaper.grade == grade)
        if topic:
            conditions.append(ReadingPassage.primary_topic == topic)
        if year:
            conditions.append(ExamPaper.year == year)
        if region:
            conditions.append(ExamPaper.region == region)
        if exam_type:
            conditions.append(ExamPaper.exam_type == exam_type)
        if semester:
            conditions.append(ExamPaper.semester == semester)

        if conditions:
            base_query = base_query.where(and_(*conditions))

    # 统计总数
    count_query = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_query) or 0

    # 获取出现位置（包含关联的文章和试卷信息）- 分页
    occ_query = (
        base_query
        .options(selectinload(VocabularyPassage.passage).selectinload(ReadingPassage.paper))
        .order_by(VocabularyPassage.id)
        .offset((page - 1) * size)
        .limit(size)
    )

    result = await db.execute(occ_query)
    occurrences = result.scalars().all()

    # 计算是否有更多
    has_more = (page * size) < total

    # 计算当前筛选条件下的词频
    filtered_frequency = total

    return VocabularySearchResponse(
        word=vocab.word,
        definition=vocab.definition,
        frequency=filtered_frequency,  # 使用筛选后的词频
        total=total,
        page=page,
        size=size,
        has_more=has_more,
        occurrences=[
            VocabularyOccurrence(
                sentence=occ.sentence,
                passage_id=occ.passage_id,
                char_position=occ.char_position,
                end_position=occ.end_position,
                source=_format_source(occ.passage)
            )
            for occ in occurrences
        ]
    )
