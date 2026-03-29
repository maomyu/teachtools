"""
词汇模块API

[INPUT]: 依赖 SQLAlchemy 异步会话、词汇模型、试卷模型
[OUTPUT]: 对外提供高频词库查询、筛选项、搜索接口
[POS]: backend/app/api 的词汇API模块
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from collections import defaultdict
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct, and_, union_all, case, literal
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
    normalized_source = source or 'all'

    if normalized_source == 'reading':
        total, items = await _query_single_source_vocabulary(
            db=db,
            source_type='reading',
            grade=grade,
            topic=topic,
            year=year,
            region=region,
            exam_type=exam_type,
            semester=semester,
            min_frequency=min_frequency,
            search=search,
            page=page,
            size=size,
        )
        return VocabularyListResponse(total=total, items=items)

    if normalized_source == 'cloze':
        total, items = await _query_single_source_vocabulary(
            db=db,
            source_type='cloze',
            grade=grade,
            topic=topic,
            year=year,
            region=region,
            exam_type=exam_type,
            semester=semester,
            min_frequency=min_frequency,
            search=search,
            page=page,
            size=size,
        )
        return VocabularyListResponse(total=total, items=items)

    total, items = await _query_combined_vocabulary(
        db=db,
        grade=grade,
        topic=topic,
        year=year,
        region=region,
        exam_type=exam_type,
        semester=semester,
        min_frequency=min_frequency,
        search=search,
        page=page,
        size=size,
    )
    return VocabularyListResponse(total=total, items=items)


def _build_reading_conditions(grade, topic, year, region, exam_type, semester):
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
    return conditions


def _build_cloze_conditions(grade, topic, year, region, exam_type, semester):
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
    return conditions


def _build_reading_frequency_query(
    grade, topic, year, region, exam_type, semester,
    min_frequency: Optional[int] = None,
):
    query = (
        select(
            VocabularyPassage.vocabulary_id.label('vocabulary_id'),
            func.count(VocabularyPassage.id).label('freq'),
            literal('reading').label('source_type'),
        )
        .select_from(VocabularyPassage)
    )

    conditions = _build_reading_conditions(grade, topic, year, region, exam_type, semester)
    if conditions:
        query = (
            query.join(ReadingPassage, VocabularyPassage.passage_id == ReadingPassage.id)
            .join(ExamPaper, ReadingPassage.paper_id == ExamPaper.id)
            .where(and_(*conditions))
        )

    query = query.group_by(VocabularyPassage.vocabulary_id)
    if min_frequency is not None:
        query = query.having(func.count(VocabularyPassage.id) >= min_frequency)

    return query


def _build_cloze_frequency_query(
    grade, topic, year, region, exam_type, semester,
    min_frequency: Optional[int] = None,
):
    query = (
        select(
            VocabularyCloze.vocabulary_id.label('vocabulary_id'),
            func.count(VocabularyCloze.id).label('freq'),
            literal('cloze').label('source_type'),
        )
        .select_from(VocabularyCloze)
    )

    conditions = _build_cloze_conditions(grade, topic, year, region, exam_type, semester)
    if conditions:
        query = (
            query.join(ClozePassage, VocabularyCloze.cloze_id == ClozePassage.id)
            .join(ExamPaper, ClozePassage.paper_id == ExamPaper.id)
            .where(and_(*conditions))
        )

    query = query.group_by(VocabularyCloze.vocabulary_id)
    if min_frequency is not None:
        query = query.having(func.count(VocabularyCloze.id) >= min_frequency)

    return query


async def _fetch_reading_occurrence_map(
    db: AsyncSession,
    vocabulary_ids: list[int],
    grade, topic, year, region, exam_type, semester,
):
    if not vocabulary_ids:
        return {}

    query = (
        select(VocabularyPassage)
        .where(VocabularyPassage.vocabulary_id.in_(vocabulary_ids))
        .options(selectinload(VocabularyPassage.passage).selectinload(ReadingPassage.paper))
        .order_by(VocabularyPassage.vocabulary_id, VocabularyPassage.id)
    )

    conditions = _build_reading_conditions(grade, topic, year, region, exam_type, semester)
    if conditions:
        query = (
            query.join(ReadingPassage, VocabularyPassage.passage_id == ReadingPassage.id)
            .join(ExamPaper, ReadingPassage.paper_id == ExamPaper.id)
            .where(and_(*conditions))
        )

    result = await db.execute(query)
    occurrences = result.scalars().all()

    occurrence_map = defaultdict(list)
    for occ in occurrences:
        occurrence_map[occ.vocabulary_id].append(
            VocabularyOccurrence(
                sentence=occ.sentence,
                passage_id=occ.passage_id,
                char_position=occ.char_position,
                end_position=occ.end_position,
                source=_format_source_reading(occ.passage),
                source_type="reading",
                **_get_source_info_reading(occ.passage)
            )
        )

    return occurrence_map


async def _fetch_cloze_occurrence_map(
    db: AsyncSession,
    vocabulary_ids: list[int],
    grade, topic, year, region, exam_type, semester,
):
    if not vocabulary_ids:
        return {}

    query = (
        select(VocabularyCloze)
        .where(VocabularyCloze.vocabulary_id.in_(vocabulary_ids))
        .options(selectinload(VocabularyCloze.cloze).selectinload(ClozePassage.paper))
        .order_by(VocabularyCloze.vocabulary_id, VocabularyCloze.id)
    )

    conditions = _build_cloze_conditions(grade, topic, year, region, exam_type, semester)
    if conditions:
        query = (
            query.join(ClozePassage, VocabularyCloze.cloze_id == ClozePassage.id)
            .join(ExamPaper, ClozePassage.paper_id == ExamPaper.id)
            .where(and_(*conditions))
        )

    result = await db.execute(query)
    occurrences = result.scalars().all()

    occurrence_map = defaultdict(list)
    for occ in occurrences:
        occurrence_map[occ.vocabulary_id].append(
            VocabularyOccurrence(
                sentence=occ.sentence,
                passage_id=occ.cloze_id,
                char_position=occ.char_position or 0,
                end_position=occ.end_position,
                source=_format_source_cloze(occ.cloze),
                source_type="cloze",
                **_get_source_info_cloze(occ.cloze)
            )
        )

    return occurrence_map


async def _query_single_source_vocabulary(
    db: AsyncSession,
    source_type: str,
    grade, topic, year, region, exam_type, semester,
    min_frequency, search, page, size,
):
    if source_type == 'reading':
        freq_query = _build_reading_frequency_query(
            grade, topic, year, region, exam_type, semester, min_frequency
        ).subquery()
        source_label = "阅读"
    else:
        freq_query = _build_cloze_frequency_query(
            grade, topic, year, region, exam_type, semester, min_frequency
        ).subquery()
        source_label = "完形"

    base_query = (
        select(Vocabulary, freq_query.c.freq)
        .join(freq_query, Vocabulary.id == freq_query.c.vocabulary_id)
    )

    if search:
        base_query = base_query.where(Vocabulary.word == search.lower())

    total = await db.scalar(select(func.count()).select_from(base_query.subquery())) or 0
    paged_query = (
        base_query
        .order_by(freq_query.c.freq.desc(), Vocabulary.word.asc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = (await db.execute(paged_query)).all()

    vocabulary_ids = [word.id for word, _ in rows]
    if source_type == 'reading':
        occurrence_map = await _fetch_reading_occurrence_map(
            db, vocabulary_ids, grade, topic, year, region, exam_type, semester
        )
    else:
        occurrence_map = await _fetch_cloze_occurrence_map(
            db, vocabulary_ids, grade, topic, year, region, exam_type, semester
        )

    items = [
        VocabularyResponse(
            id=word.id,
            word=word.word,
            lemma=word.lemma,
            definition=word.definition,
            phonetic=word.phonetic,
            pos=word.pos,
            frequency=actual_frequency,
            sources=[source_label],
            occurrences=occurrence_map.get(word.id, []),
        )
        for word, actual_frequency in rows
    ]

    return total, items


async def _query_combined_vocabulary(
    db: AsyncSession,
    grade, topic, year, region, exam_type, semester,
    min_frequency, search, page, size,
):
    combined_frequency = union_all(
        _build_reading_frequency_query(grade, topic, year, region, exam_type, semester),
        _build_cloze_frequency_query(grade, topic, year, region, exam_type, semester),
    ).subquery()

    aggregated_frequency = (
        select(
            combined_frequency.c.vocabulary_id,
            func.sum(combined_frequency.c.freq).label('freq'),
            func.max(case((combined_frequency.c.source_type == 'reading', 1), else_=0)).label('has_reading'),
            func.max(case((combined_frequency.c.source_type == 'cloze', 1), else_=0)).label('has_cloze'),
        )
        .group_by(combined_frequency.c.vocabulary_id)
        .having(func.sum(combined_frequency.c.freq) >= min_frequency)
        .subquery()
    )

    base_query = (
        select(
            Vocabulary,
            aggregated_frequency.c.freq,
            aggregated_frequency.c.has_reading,
            aggregated_frequency.c.has_cloze,
        )
        .join(aggregated_frequency, Vocabulary.id == aggregated_frequency.c.vocabulary_id)
    )

    if search:
        base_query = base_query.where(Vocabulary.word == search.lower())

    total = await db.scalar(select(func.count()).select_from(base_query.subquery())) or 0
    paged_query = (
        base_query
        .order_by(aggregated_frequency.c.freq.desc(), Vocabulary.word.asc())
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = (await db.execute(paged_query)).all()

    vocabulary_ids = [word.id for word, _, _, _ in rows]
    reading_occurrences = await _fetch_reading_occurrence_map(
        db, vocabulary_ids, grade, topic, year, region, exam_type, semester
    )
    cloze_occurrences = await _fetch_cloze_occurrence_map(
        db, vocabulary_ids, grade, topic, year, region, exam_type, semester
    )

    items = []
    for word, actual_frequency, has_reading, has_cloze in rows:
        sources = []
        if has_reading:
            sources.append("阅读")
        if has_cloze:
            sources.append("完形")

        items.append(
            VocabularyResponse(
                id=word.id,
                word=word.word,
                lemma=word.lemma,
                definition=word.definition,
                phonetic=word.phonetic,
                pos=word.pos,
                frequency=actual_frequency,
                sources=sources,
                occurrences=reading_occurrences.get(word.id, []) + cloze_occurrences.get(word.id, []),
            )
        )

    return total, items


def _format_source_reading(passage: ReadingPassage) -> str:
    """格式化阅读文章出处信息"""
    if not passage or not passage.paper:
        return ""
    parts = []
    if passage.paper.year:
        parts.append(str(passage.paper.year))
    # 同时显示区县和学校（如果都有）
    if passage.paper.region:
        parts.append(passage.paper.region)
    if passage.paper.school:
        parts.append(passage.paper.school)
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
        "school": passage.paper.school,
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
    # 同时显示区县和学校（如果都有）
    if cloze.paper.region:
        parts.append(cloze.paper.region)
    if cloze.paper.school:
        parts.append(cloze.paper.school)
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
        "school": cloze.paper.school,
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
