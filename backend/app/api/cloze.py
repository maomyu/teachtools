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
    PointAnalysis,
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

@router.get("/filters", response_model=ClozeFilters)
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

@router.get("", response_model=ClozeListResponse)
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
                sentence=pt.sentence,
                point_verified=pt.point_verified if hasattr(pt, 'point_verified') else False,
                # 固定搭配
                phrase=pt.phrase if hasattr(pt, 'phrase') else None,
                similar_phrases=json.loads(pt.similar_phrases) if hasattr(pt, 'similar_phrases') and pt.similar_phrases else None,
                # 词义辨析
                word_analysis=json.loads(pt.word_analysis) if hasattr(pt, 'word_analysis') and pt.word_analysis else None,
                dictionary_source=pt.dictionary_source if hasattr(pt, 'dictionary_source') else None,
                # 熟词僻义
                textbook_meaning=pt.textbook_meaning if hasattr(pt, 'textbook_meaning') else None,
                textbook_source=pt.textbook_source if hasattr(pt, 'textbook_source') else None,
                context_meaning=pt.context_meaning if hasattr(pt, 'context_meaning') else None,
                similar_words=json.loads(pt.similar_words) if hasattr(pt, 'similar_words') and pt.similar_words else None,
                # 通用
                tips=pt.tips if hasattr(pt, 'tips') else None
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
    """获取考点汇总（支持 frequency 聚合）"""
    # 先查询所有匹配的考点，不做分页（需要聚合）
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

    # 排序
    query = query.order_by(ClozePoint.correct_word)

    result = await db.execute(query)
    all_points = result.scalars().all()

    # 按 (correct_word, point_type) 聚合
    aggregated = {}
    for pt in all_points:
        key = (pt.correct_word or "", pt.point_type or "词汇")
        if key not in aggregated:
            aggregated[key] = []
        aggregated[key].append(pt)

    # 构建聚合后的列表
    summaries = []
    for (word, ptype), points in aggregated.items():
        occurrences = []
        first_point = points[0]

        for pt in points:
            source = ""
            if pt.cloze and pt.cloze.paper:
                paper = pt.cloze.paper
                source = f"{paper.year}{paper.region}{paper.grade}{paper.exam_type or ''}·完形"

            # 构建嵌套的分析对象
            analysis = PointAnalysis(
                explanation=pt.explanation,
                confusion_words=json.loads(pt.confusion_words) if pt.confusion_words else None,
                tips=pt.tips if hasattr(pt, 'tips') else None,
                # 固定搭配
                phrase=pt.phrase if hasattr(pt, 'phrase') else None,
                similar_phrases=json.loads(pt.similar_phrases) if hasattr(pt, 'similar_phrases') and pt.similar_phrases else None,
                # 词义辨析
                word_analysis=json.loads(pt.word_analysis) if hasattr(pt, 'word_analysis') and pt.word_analysis else None,
                dictionary_source=pt.dictionary_source if hasattr(pt, 'dictionary_source') else None,
                # 熟词僻义
                textbook_meaning=pt.textbook_meaning if hasattr(pt, 'textbook_meaning') else None,
                textbook_source=pt.textbook_source if hasattr(pt, 'textbook_source') else None,
                context_meaning=pt.context_meaning if hasattr(pt, 'context_meaning') else None,
                similar_words=json.loads(pt.similar_words) if hasattr(pt, 'similar_words') and pt.similar_words else None,
            )

            occurrences.append(PointOccurrence(
                sentence=pt.sentence or "",
                source=source,
                blank_number=pt.blank_number,
                point_type=ptype,
                passage_id=pt.cloze_id,
                point_id=pt.id,
                analysis=analysis
            ))

        # 根据考点类型选择释义字段：熟词僻义优先使用 context_meaning
        if ptype == '熟词僻义' and hasattr(first_point, 'context_meaning') and first_point.context_meaning:
            definition = first_point.context_meaning
        else:
            definition = first_point.translation

        summaries.append(PointSummary(
            word=word,
            definition=definition,
            frequency=len(points),
            point_type=ptype,
            occurrences=occurrences,
            tips=first_point.tips if hasattr(first_point, 'tips') else None
        ))

    # 按频率排序后分页
    summaries.sort(key=lambda x: x.frequency, reverse=True)
    total = len(summaries)
    start = (page - 1) * size
    end = start + size
    paginated_summaries = summaries[start:end]

    return {"total": total, "items": paginated_summaries}


# ============================================================================
#  完形文章详情
# ============================================================================

@router.get("/{cloze_id}", response_model=ClozeDetailResponse)
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
            sentence=pt.sentence,
            point_verified=pt.point_verified if hasattr(pt, 'point_verified') else False,
            # 固定搭配
            phrase=pt.phrase if hasattr(pt, 'phrase') else None,
            similar_phrases=json.loads(pt.similar_phrases) if hasattr(pt, 'similar_phrases') and pt.similar_phrases else None,
            # 词义辨析
            word_analysis=json.loads(pt.word_analysis) if hasattr(pt, 'word_analysis') and pt.word_analysis else None,
            dictionary_source=pt.dictionary_source if hasattr(pt, 'dictionary_source') else None,
            # 熟词僻义
            textbook_meaning=pt.textbook_meaning if hasattr(pt, 'textbook_meaning') else None,
            textbook_source=pt.textbook_source if hasattr(pt, 'textbook_source') else None,
            context_meaning=pt.context_meaning if hasattr(pt, 'context_meaning') else None,
            similar_words=json.loads(pt.similar_words) if hasattr(pt, 'similar_words') and pt.similar_words else None,
            # 通用
            tips=pt.tips if hasattr(pt, 'tips') else None
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


# ============================================================================
#  讲义API端点
# ============================================================================

from app.schemas.cloze import (
    ClozeTopicStats,
    ArticleSource,
    HandoutVocabulary,
    WordAnalysisPoint,
    FixedPhrasePoint,
    RareMeaningPoint,
    PointsByType,
    ClozeHandoutPassage,
    ClozeTopicContent,
    ClozeHandoutDetailResponse,
    ClozeGradeHandoutResponse,
)
from app.models.reading import ReadingPassage
from app.models.vocabulary import Vocabulary, VocabularyPassage


@router.get("/handouts/{grade}")
async def get_cloze_grade_handout(
    grade: str,
    edition: str = Query('teacher', pattern='^(teacher|student)$'),
    db: AsyncSession = Depends(get_db)
):
    """
    获取某年级的完整完形讲义（包含所有主题）

    [INPUT]: 年级参数、版本（teacher/student）
    [OUTPUT]: 年级讲义结构（目录 + 各主题内容）
    [POS]: cloze.py 的年级讲义端点
    [PROTOCOL]: 变更时更新此头部
    """
    # 获取主题统计（按考频排序）
    topics = await _get_cloze_topic_stats_for_grade(db, grade)

    # 获取每个主题的内容
    content = []
    for topic_info in topics:
        topic = topic_info["topic"]
        topic_content = {
            "topic": topic,
            "part1_article_sources": await _get_cloze_article_sources(db, grade, topic),
            "part2_vocabulary": await _get_topic_vocabulary_with_source(db, grade, topic),
            "part3_points_by_type": await _get_points_by_type(db, grade, topic),
            "part4_passages": await _get_cloze_passages_with_points(db, grade, topic, edition)
        }
        content.append(topic_content)

    return {
        "grade": grade,
        "edition": edition,
        "topics": topics,
        "content": content
    }


@router.get("/handouts/{grade}/topics")
async def get_cloze_topic_stats(
    grade: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取某年级的完形主题统计（按考频降序）

    [INPUT]: 年级参数
    [OUTPUT]: 主题统计列表（按考频降序）
    [POS]: cloze.py 的讲义主题统计端点
    [PROTOCOL]: 变更时更新此头部
    """
    topics = await _get_cloze_topic_stats_for_grade(db, grade)
    return {"topics": topics}


@router.get("/handouts/{grade}/topics/{topic:path}")
async def get_cloze_handout_detail(
    grade: str,
    topic: str,
    edition: str = Query('teacher', pattern='^(teacher|student)$'),
    db: AsyncSession = Depends(get_db)
):
    """
    获取某年级某主题的完形讲义详情

    [INPUT]: 年级、主题、版本（teacher/student）
    [OUTPUT]: 四段式讲义结构
    [POS]: cloze.py 的讲义详情端点
    [PROTOCOL]: 变更时更新此头部
    """
    # 第一部分：文章来源
    article_sources = await _get_cloze_article_sources(db, grade, topic)

    # 第二部分：高频词汇
    vocabulary = await _get_topic_vocabulary_with_source(db, grade, topic)

    # 第三部分：考点分类
    points_by_type = await _get_points_by_type(db, grade, topic)

    # 第四部分：完形文章
    passages = await _get_cloze_passages_with_points(db, grade, topic, edition)

    return {
        "topic": topic,
        "grade": grade,
        "edition": edition,
        "part1_article_sources": article_sources,
        "part2_vocabulary": vocabulary,
        "part3_points_by_type": points_by_type,
        "part4_passages": passages
    }


# ============================================================================
#  讲义辅助函数
# ============================================================================

async def _get_cloze_topic_stats_for_grade(db: AsyncSession, grade: str):
    """
    获取某年级的完形主题统计（按文章数降序）

    [INPUT]: 数据库会话、年级
    [OUTPUT]: 主题统计列表（按考频降序）
    [POS]: cloze.py 的私有辅助函数
    [PROTOCOL]: 变更时更新此头部
    """
    query = (
        select(
            ClozePassage.primary_topic.label('topic'),
            func.count(ClozePassage.id).label('passage_count'),
            func.group_concat(ExamPaper.year.distinct()).label('years')
        )
        .join(ExamPaper, ClozePassage.paper_id == ExamPaper.id)
        .where(ExamPaper.grade == grade)
        .where(ClozePassage.primary_topic.isnot(None))
        .group_by(ClozePassage.primary_topic)
        .order_by(func.count(ClozePassage.id).desc())
    )

    result = await db.execute(query)
    topics = []
    for row in result.all():
        years = sorted(set(int(y) for y in row.years.split(',') if y), reverse=True) if row.years else []
        topics.append({
            "topic": row.topic,
            "passage_count": row.passage_count,
            "recent_years": years[:3]
        })

    return topics


async def _get_cloze_article_sources(db: AsyncSession, grade: str, topic: str):
    """
    获取主题下所有完形文章来源（按年份+区县分组）

    [INPUT]: 数据库会话、年级、主题
    [OUTPUT]: 文章来源列表（按试卷分组）
    [POS]: cloze.py 的私有辅助函数
    [PROTOCOL]: 变更时更新此头部
    """
    query = (
        select(ClozePassage, ExamPaper)
        .join(ExamPaper, ClozePassage.paper_id == ExamPaper.id)
        .where(ExamPaper.grade == grade)
        .where(ClozePassage.primary_topic == topic)
        .order_by(ExamPaper.year.desc(), ExamPaper.region)
    )
    result = await db.execute(query)

    # 按试卷分组
    sources = {}
    for passage, paper in result.all():
        key = f"{paper.year}_{paper.region}_{paper.exam_type}"
        if key not in sources:
            sources[key] = {
                "year": paper.year,
                "region": paper.region,
                "exam_type": paper.exam_type,
                "semester": paper.semester,
                "passages": []
            }
        sources[key]["passages"].append({
            "type": None,  # 完形没有 C/D 篇区分
            "id": passage.id,
            "title": None
        })

    return list(sources.values())


async def _get_topic_vocabulary_with_source(db: AsyncSession, grade: str, topic: str):
    """
    获取主题高频词汇（含来源标注，按优先级排序）

    排序优先级：
    1. 阅读+完形共同出现 (both)
    2. 仅阅读 (reading)
    3. 仅完形 (cloze)
    同优先级内按词频降序

    [INPUT]: 数据库会话、年级、主题
    [OUTPUT]: 高频词汇列表（带 source_type 字段）
    [POS]: cloze.py 的私有辅助函数
    [PROTOCOL]: 变更时更新此头部
    """
    # 1. 查询阅读文章中的词汇
    reading_query = (
        select(
            Vocabulary.id,
            Vocabulary.word,
            Vocabulary.definition,
            Vocabulary.phonetic,
            func.count(VocabularyPassage.id).label('frequency')
        )
        .join(VocabularyPassage, Vocabulary.id == VocabularyPassage.vocabulary_id)
        .join(ReadingPassage, VocabularyPassage.passage_id == ReadingPassage.id)
        .join(ExamPaper, ReadingPassage.paper_id == ExamPaper.id)
        .where(ExamPaper.grade == grade)
        .where(ReadingPassage.primary_topic == topic)
        .group_by(Vocabulary.id)
    )
    reading_result = await db.execute(reading_query)
    reading_vocabs = {row.id: {"id": row.id, "word": row.word, "definition": row.definition,
                                "phonetic": row.phonetic, "frequency": row.frequency}
                      for row in reading_result.all()}

    # 2. 查询完形文章中的词汇
    cloze_query = (
        select(
            Vocabulary.id,
            Vocabulary.word,
            Vocabulary.definition,
            Vocabulary.phonetic,
            func.count(VocabularyCloze.id).label('frequency')
        )
        .join(VocabularyCloze, Vocabulary.id == VocabularyCloze.vocabulary_id)
        .join(ClozePassage, VocabularyCloze.cloze_id == ClozePassage.id)
        .join(ExamPaper, ClozePassage.paper_id == ExamPaper.id)
        .where(ExamPaper.grade == grade)
        .where(ClozePassage.primary_topic == topic)
        .group_by(Vocabulary.id)
    )
    cloze_result = await db.execute(cloze_query)
    cloze_vocabs = {row.id: {"id": row.id, "word": row.word, "definition": row.definition,
                              "phonetic": row.phonetic, "frequency": row.frequency}
                    for row in cloze_result.all()}

    # 3. 合并词汇，标注来源类型
    all_vocab_ids = set(reading_vocabs.keys()) | set(cloze_vocabs.keys())
    vocabulary = []

    for vid in all_vocab_ids:
        in_reading = vid in reading_vocabs
        in_cloze = vid in cloze_vocabs

        if in_reading and in_cloze:
            source_type = "both"
            freq = reading_vocabs[vid]["frequency"] + cloze_vocabs[vid]["frequency"]
            vocab_data = reading_vocabs[vid]
        elif in_reading:
            source_type = "reading"
            freq = reading_vocabs[vid]["frequency"]
            vocab_data = reading_vocabs[vid]
        else:
            source_type = "cloze"
            freq = cloze_vocabs[vid]["frequency"]
            vocab_data = cloze_vocabs[vid]

        vocabulary.append({
            "id": vocab_data["id"],
            "word": vocab_data["word"],
            "definition": vocab_data["definition"],
            "phonetic": vocab_data["phonetic"],
            "frequency": freq,
            "source_type": source_type
        })

    # 4. 排序：优先级 both > reading > cloze，同优先级按词频降序
    source_priority = {"both": 0, "reading": 1, "cloze": 2}
    vocabulary.sort(key=lambda x: (source_priority[x["source_type"]], -x["frequency"]))

    return vocabulary


async def _get_points_by_type(db: AsyncSession, grade: str, topic: str):
    """
    获取主题下按类型分组的考点（聚合统计）

    [INPUT]: 数据库会话、年级、主题
    [OUTPUT]: 按类型分组的考点数据
    [POS]: cloze.py 的私有辅助函数
    [PROTOCOL]: 变更时更新此头部
    """
    query = (
        select(ClozePoint, ClozePassage, ExamPaper)
        .join(ClozePassage, ClozePoint.cloze_id == ClozePassage.id)
        .join(ExamPaper, ClozePassage.paper_id == ExamPaper.id)
        .where(ExamPaper.grade == grade)
        .where(ClozePassage.primary_topic == topic)
        .where(ClozePoint.point_type.isnot(None))
        .where(ClozePoint.correct_word.isnot(None))
    )

    result = await db.execute(query)

    # 按考点类型和单词分组
    grouped = {
        "词义辨析": {},
        "固定搭配": {},
        "熟词僻义": {}
    }

    for point, passage, paper in result.all():
        ptype = point.point_type
        word = point.correct_word or ""

        if ptype not in grouped:
            continue

        if word not in grouped[ptype]:
            # 初始化
            if ptype == "词义辨析":
                grouped[ptype][word] = {
                    "word": word,
                    "frequency": 0,
                    "definition": point.translation,
                    "word_analysis": json.loads(point.word_analysis) if point.word_analysis else None,
                    "dictionary_source": point.dictionary_source,
                    "occurrences": []
                }
            elif ptype == "固定搭配":
                grouped[ptype][word] = {
                    "word": word,
                    "frequency": 0,
                    "phrase": point.phrase,
                    "similar_phrases": json.loads(point.similar_phrases) if point.similar_phrases else None,
                    "occurrences": []
                }
            else:  # 熟词僻义
                grouped[ptype][word] = {
                    "word": word,
                    "frequency": 0,
                    "textbook_meaning": point.textbook_meaning,
                    "textbook_source": point.textbook_source,
                    "context_meaning": point.context_meaning,
                    "similar_words": json.loads(point.similar_words) if point.similar_words else None,
                    "occurrences": []
                }

        # 增加频次
        grouped[ptype][word]["frequency"] += 1

        # 添加出现记录
        source = f"{paper.year}{paper.region}{paper.grade}{paper.exam_type or ''}·完形"
        analysis = PointAnalysis(
            explanation=point.explanation,
            confusion_words=json.loads(point.confusion_words) if point.confusion_words else None,
            tips=point.tips if hasattr(point, 'tips') else None,
            phrase=point.phrase if ptype == "固定搭配" else None,
            similar_phrases=json.loads(point.similar_phrases) if ptype == "固定搭配" and point.similar_phrases else None,
            word_analysis=json.loads(point.word_analysis) if ptype == "词义辨析" and point.word_analysis else None,
            dictionary_source=point.dictionary_source if ptype == "词义辨析" else None,
            textbook_meaning=point.textbook_meaning if ptype == "熟词僻义" else None,
            textbook_source=point.textbook_source if ptype == "熟词僻义" else None,
            context_meaning=point.context_meaning if ptype == "熟词僻义" else None,
            similar_words=json.loads(point.similar_words) if ptype == "熟词僻义" and point.similar_words else None,
        )

        occurrence = PointOccurrence(
            sentence=point.sentence or "",
            source=source,
            blank_number=point.blank_number,
            point_type=ptype,
            passage_id=passage.id,
            point_id=point.id,
            analysis=analysis
        )
        grouped[ptype][word]["occurrences"].append(occurrence)

    # 转换为列表并按频次排序
    points_by_type = {
        "词义辨析": sorted(list(grouped["词义辨析"].values()), key=lambda x: -x["frequency"]),
        "固定搭配": sorted(list(grouped["固定搭配"].values()), key=lambda x: -x["frequency"]),
        "熟词僻义": sorted(list(grouped["熟词僻义"].values()), key=lambda x: -x["frequency"])
    }

    return points_by_type


async def _get_cloze_passages_with_points(db: AsyncSession, grade: str, topic: str, edition: str):
    """
    获取主题下的完形文章（含考点分析）

    [INPUT]: 数据库会话、年级、主题、版本（teacher/student）
    [OUTPUT]: 文章列表
    [POS]: cloze.py 的私有辅助函数
    [PROTOCOL]: 变更时更新此头部
    """
    query = (
        select(ClozePassage)
        .options(
            selectinload(ClozePassage.paper),
            selectinload(ClozePassage.points)
        )
        .join(ExamPaper, ClozePassage.paper_id == ExamPaper.id)
        .where(ExamPaper.grade == grade)
        .where(ClozePassage.primary_topic == topic)
        .order_by(ExamPaper.year.desc())
    )

    result = await db.execute(query)
    passages = result.scalars().all()

    items = []
    for p in passages:
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

        # 构建考点列表
        points_list = []
        for pt in p.points:
            point_data = ClozePointResponse(
                id=pt.id,
                blank_number=pt.blank_number,
                correct_answer=pt.correct_answer,
                correct_word=pt.correct_word,
                options=json.loads(pt.options) if pt.options else {},
                point_type=pt.point_type,
                translation=pt.translation,
                explanation=pt.explanation if edition == 'teacher' else None,
                confusion_words=json.loads(pt.confusion_words) if pt.confusion_words and edition == 'teacher' else None,
                sentence=pt.sentence,
                point_verified=pt.point_verified if hasattr(pt, 'point_verified') else False,
                phrase=pt.phrase if hasattr(pt, 'phrase') else None,
                similar_phrases=json.loads(pt.similar_phrases) if hasattr(pt, 'similar_phrases') and pt.similar_phrases and edition == 'teacher' else None,
                word_analysis=json.loads(pt.word_analysis) if hasattr(pt, 'word_analysis') and pt.word_analysis and edition == 'teacher' else None,
                dictionary_source=pt.dictionary_source if hasattr(pt, 'dictionary_source') and edition == 'teacher' else None,
                textbook_meaning=pt.textbook_meaning if hasattr(pt, 'textbook_meaning') else None,
                textbook_source=pt.textbook_source if hasattr(pt, 'textbook_source') and edition == 'teacher' else None,
                context_meaning=pt.context_meaning if hasattr(pt, 'context_meaning') else None,
                similar_words=json.loads(pt.similar_words) if hasattr(pt, 'similar_words') and pt.similar_words and edition == 'teacher' else None,
                tips=pt.tips if hasattr(pt, 'tips') and edition == 'teacher' else None
            )
            points_list.append(point_data)

        passage_data = ClozeHandoutPassage(
            id=p.id,
            content=p.content,
            word_count=p.word_count,
            source=source,
            points=points_list
        )
        items.append(passage_data)

    return items
