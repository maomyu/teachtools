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
from sqlalchemy import select, func, distinct, and_, union_all
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.vocabulary import Vocabulary, VocabularyPassage
from app.models.vocabulary_cloze import VocabularyCloze
from app.models.reading import ReadingPassage
from app.models.cloze import ClozePassage
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

    返回所有可用的年级、主题、年份、区县、考试类型、学期、来源列表
    """
    # 获取年级列表（去重）
    grades_query = select(distinct(ExamPaper.grade)).where(
        ExamPaper.grade.isnot(None)
    ).order_by(ExamPaper.grade)
    grades_result = await db.execute(grades_query)
    grades = [g for g in grades_result.scalars().all() if g]

    # 获取主题列表（从阅读文章表 + 完形文章表）
    topics_query = select(distinct(ReadingPassage.primary_topic)).where(
        ReadingPassage.primary_topic.isnot(None)
    ).order_by(ReadingPassage.primary_topic)
    topics_result = await db.execute(topics_query)
    topics = [t for t in topics_result.scalars().all() if t]

    # 完形主题
    cloze_topics_query = select(distinct(ClozePassage.primary_topic)).where(
        ClozePassage.primary_topic.isnot(None)
    )
    cloze_topics_result = await db.execute(cloze_topics_query)
    for t in cloze_topics_result.scalars().all():
        if t and t not in topics:
            topics.append(t)
    topics = sorted(topics)

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
        semesters=semesters,
        sources=["阅读", "完形"]
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
    source: Optional[str] = Query(None, description="来源筛选: reading/cloze/all"),
    db: AsyncSession = Depends(get_db)
):
    """
    获取高频词汇列表（支持多维度筛选 + 来源筛选）

    筛选逻辑：
    - source=reading → 只查阅读词汇
    - source=cloze → 只查完形词汇
    - source=all 或 None → 联合查询，聚合词频
    """
    items = []
    total = 0

    # ============================================================================
    #  阅读来源查询
    # ============================================================================
    if source == 'reading' or source is None or source == 'all':
        reading_items, reading_total = await _query_reading_vocabulary(
            db, grade, topic, year, region, exam_type, semester,
            min_frequency, search, page, size, source == 'reading'
        )
        items.extend(reading_items)
        total += reading_total

    # ============================================================================
    #  完形来源查询
    # ============================================================================
    if source == 'cloze' or source is None or source == 'all':
        cloze_items, cloze_total = await _query_cloze_vocabulary(
            db, grade, topic, year, region, exam_type, semester,
            min_frequency, search, page, size, source == 'cloze'
        )
        items.extend(cloze_items)
        total += cloze_total

    # ============================================================================
    #  聚合模式：合并相同词汇的词频
    # ============================================================================
    if source is None or source == 'all':
        # 合并相同词汇
        vocab_map = {}
        for item in items:
            if item.word not in vocab_map:
                vocab_map[item.word] = item
            else:
                existing = vocab_map[item.word]
                existing.frequency += item.frequency
                existing.sources = list(set(existing.sources + item.sources))
                existing.occurrences.extend(item.occurrences)

        # 重新排序并分页
        sorted_items = sorted(vocab_map.values(), key=lambda x: x.frequency, reverse=True)
        total = len(sorted_items)
        items = sorted_items[(page - 1) * size: page * size]

    return VocabularyListResponse(total=total, items=items)


async def _query_reading_vocabulary(
    db: AsyncSession,
    grade, topic, year, region, exam_type, semester,
    min_frequency, search, page, size, exclusive
):
    """查询阅读来源的词汇"""
    needs_join = any([grade, topic, year, region, exam_type, semester])

    if needs_join:
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
    else:
        vocab_count_subquery = (
            select(
                VocabularyPassage.vocabulary_id,
                func.count(VocabularyPassage.id).label('freq')
            )
            .group_by(VocabularyPassage.vocabulary_id)
            .having(func.count(VocabularyPassage.id) >= min_frequency)
            .subquery()
        )

    query = (
        select(Vocabulary, vocab_count_subquery.c.freq)
        .join(vocab_count_subquery, Vocabulary.id == vocab_count_subquery.c.vocabulary_id)
    )

    if search:
        query = query.where(Vocabulary.word == search.lower())

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    query = query.order_by(vocab_count_subquery.c.freq.desc())

    # 只在独占模式下分页
    if exclusive:
        query = query.offset((page - 1) * size).limit(size)

    result = await db.execute(query)
    rows = result.all()

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
            sources=["阅读"],
            occurrences=[
                VocabularyOccurrence(
                    sentence=occ.sentence,
                    passage_id=occ.passage_id,
                    char_position=occ.char_position,
                    end_position=occ.end_position,
                    source=_format_source_reading(occ.passage),
                    source_type="reading",
                    **_get_source_info_reading(occ.passage)
                )
                for occ in occurrences
            ]
        ))

    return items, total


async def _query_cloze_vocabulary(
    db: AsyncSession,
    grade, topic, year, region, exam_type, semester,
    min_frequency, search, page, size, exclusive
):
    """查询完形来源的词汇"""
    needs_join = any([grade, topic, year, region, exam_type, semester])

    if needs_join:
        vocab_count_subquery = (
            select(
                VocabularyCloze.vocabulary_id,
                func.count(VocabularyCloze.id).label('freq')
            )
            .select_from(VocabularyCloze)
            .join(ClozePassage, VocabularyCloze.cloze_id == ClozePassage.id)
            .join(ExamPaper, ClozePassage.paper_id == ExamPaper.id)
            .group_by(VocabularyCloze.vocabulary_id)
            .having(func.count(VocabularyCloze.id) >= min_frequency)
        )

        conditions = []
        if grade:
            conditions.append(ExamPaper.grade == grade)
        if topic:
            conditions.append(ClozePassage.primary_topic == topic)
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
    else:
        vocab_count_subquery = (
            select(
                VocabularyCloze.vocabulary_id,
                func.count(VocabularyCloze.id).label('freq')
            )
            .group_by(VocabularyCloze.vocabulary_id)
            .having(func.count(VocabularyCloze.id) >= min_frequency)
            .subquery()
        )

    query = (
        select(Vocabulary, vocab_count_subquery.c.freq)
        .join(vocab_count_subquery, Vocabulary.id == vocab_count_subquery.c.vocabulary_id)
    )

    if search:
        query = query.where(Vocabulary.word == search.lower())

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    query = query.order_by(vocab_count_subquery.c.freq.desc())

    # 只在独占模式下分页
    if exclusive:
        query = query.offset((page - 1) * size).limit(size)

    result = await db.execute(query)
    rows = result.all()

    items = []
    for word, actual_frequency in rows:
        occ_query = (
            select(VocabularyCloze)
            .where(VocabularyCloze.vocabulary_id == word.id)
            .options(selectinload(VocabularyCloze.cloze).selectinload(ClozePassage.paper))
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
            sources=["完形"],
            occurrences=[
                VocabularyOccurrence(
                    sentence=occ.sentence,
                    passage_id=occ.cloze_id,
                    char_position=occ.char_position or 0,
                    end_position=occ.end_position,
                    source=_format_source_cloze(occ.cloze),
                    source_type="cloze",
                    **_get_source_info_cloze(occ.cloze)
                )
                for occ in occurrences
            ]
        ))

    return items, total


def _format_source_reading(passage: ReadingPassage) -> str:
    """格式化阅读文章出处信息"""
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


def _get_source_info_reading(passage: ReadingPassage) -> dict:
    """获取阅读文章结构化的出处信息"""
    if not passage or not passage.paper:
        return {}
    return {
        "year": passage.paper.year,
        "region": passage.paper.region,
        "grade": passage.paper.grade,
        "exam_type": passage.paper.exam_type,
        "semester": passage.paper.semester,
    }


def _format_source_cloze(cloze: ClozePassage) -> str:
    """格式化完形文章出处信息"""
    if not cloze or not cloze.paper:
        return ""
    parts = []
    if cloze.paper.year:
        parts.append(str(cloze.paper.year))
    if cloze.paper.region:
        parts.append(cloze.paper.region)
    if cloze.paper.grade:
        parts.append(cloze.paper.grade)
    return " ".join(parts)


def _get_source_info_cloze(cloze: ClozePassage) -> dict:
    """获取完形文章结构化的出处信息"""
    if not cloze or not cloze.paper:
        return {}
    return {
        "year": cloze.paper.year,
        "region": cloze.paper.region,
        "grade": cloze.paper.grade,
        "exam_type": cloze.paper.exam_type,
        "semester": cloze.paper.semester,
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
    支持阅读和完形两种来源
    """
    # 查找单词
    query = select(Vocabulary).where(Vocabulary.word == word.lower())
    vocab = await db.scalar(query)

    if not vocab:
        raise HTTPException(status_code=404, detail="单词不存在")

    # ============================================================================
    #  查询阅读来源
    # ============================================================================
    reading_occurrences = await _search_reading_occurrences(
        db, vocab.id, grade, topic, year, region, exam_type, semester
    )

    # ============================================================================
    #  查询完形来源
    # ============================================================================
    cloze_occurrences = await _search_cloze_occurrences(
        db, vocab.id, grade, topic, year, region, exam_type, semester
    )

    # ============================================================================
    #  合并结果
    # ============================================================================
    all_occurrences = reading_occurrences + cloze_occurrences
    total = len(all_occurrences)

    # 分页
    start = (page - 1) * size
    end = start + size
    paginated = all_occurrences[start:end]

    has_more = end < total

    return VocabularySearchResponse(
        word=vocab.word,
        definition=vocab.definition,
        frequency=total,
        total=total,
        page=page,
        size=size,
        has_more=has_more,
        occurrences=paginated
    )


async def _search_reading_occurrences(
    db: AsyncSession,
    vocab_id: int,
    grade, topic, year, region, exam_type, semester
) -> List[VocabularyOccurrence]:
    """查询阅读来源的出现位置"""
    has_filters = any([grade, topic, year, region, exam_type, semester])

    base_query = (
        select(VocabularyPassage)
        .where(VocabularyPassage.vocabulary_id == vocab_id)
    )

    if has_filters:
        base_query = (
            base_query
            .join(ReadingPassage, VocabularyPassage.passage_id == ReadingPassage.id)
            .join(ExamPaper, ReadingPassage.paper_id == ExamPaper.id)
        )

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

    occ_query = base_query.options(
        selectinload(VocabularyPassage.passage).selectinload(ReadingPassage.paper)
    )

    result = await db.execute(occ_query)
    occurrences = result.scalars().all()

    return [
        VocabularyOccurrence(
            sentence=occ.sentence,
            passage_id=occ.passage_id,
            char_position=occ.char_position,
            end_position=occ.end_position,
            source=_format_source_reading(occ.passage),
            source_type="reading",
            **_get_source_info_reading(occ.passage)
        )
        for occ in occurrences
        if occ.passage  # 过滤掉无效数据
    ]


async def _search_cloze_occurrences(
    db: AsyncSession,
    vocab_id: int,
    grade, topic, year, region, exam_type, semester
) -> List[VocabularyOccurrence]:
    """查询完形来源的出现位置"""
    has_filters = any([grade, topic, year, region, exam_type, semester])

    base_query = (
        select(VocabularyCloze)
        .where(VocabularyCloze.vocabulary_id == vocab_id)
    )

    if has_filters:
        base_query = (
            base_query
            .join(ClozePassage, VocabularyCloze.cloze_id == ClozePassage.id)
            .join(ExamPaper, ClozePassage.paper_id == ExamPaper.id)
        )

        conditions = []
        if grade:
            conditions.append(ExamPaper.grade == grade)
        if topic:
            conditions.append(ClozePassage.primary_topic == topic)
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

    occ_query = base_query.options(
        selectinload(VocabularyCloze.cloze).selectinload(ClozePassage.paper)
    )

    result = await db.execute(occ_query)
    occurrences = result.scalars().all()

    return [
        VocabularyOccurrence(
            sentence=occ.sentence or "",
            passage_id=occ.cloze_id,  # 完形用 cloze_id
            char_position=occ.char_position or 0,
            end_position=occ.end_position,
            source=_format_source_cloze(occ.cloze),
            source_type="cloze",
            **_get_source_info_cloze(occ.cloze)
        )
        for occ in occurrences
        if occ.cloze  # 过滤掉无效数据
    ]
