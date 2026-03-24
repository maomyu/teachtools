"""
完形填空 API 路由

[INPUT]: 依赖 FastAPI, SQLAlchemy, app.models, app.schemas
[OUTPUT]: 对外提供完形填空相关的 REST API
[POS]: backend/app/api 的完形路由
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md

考点分类系统 v2:
- 5大类(A-E) 16个考点
- 支持多标签: 主考点 + 辅助考点 + 排错点
- 优先级: P1(核心) > P2(重要) > P3(一般)

旧类型映射: 固定搭配→C2, 词义辨析→D1, 熟词僻义→D2
"""
import json
from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct, delete
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.cloze import ClozePassage, ClozePoint, PointTypeDefinition, ClozeSecondaryPoint, ClozeRejectionPoint
from app.models.paper import ExamPaper
from app.models.vocabulary_cloze import VocabularyCloze
from app.models.vocabulary import Vocabulary
from app.models.reading import ReadingPassage
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
    # V2 新增
    PointTypeBase,
    PointTypeListResponse,
    PointTypeByCategoryResponse,
    ClozePointNewResponse,
    ClozeDetailNewResponse,
    SecondaryPointBase,
    RejectionPointBase,
)

router = APIRouter()


# ============================================================================
#  考点类型定义（V2 新增，必须放在 /{cloze_id} 之前）
# ============================================================================

# 旧类型到新编码的映射
LEGACY_TO_NEW_CODE = {
    "固定搭配": "C2",
    "词义辨析": "D1",
    "熟词僻义": "D2",
}

# 新编码到旧类型的映射
NEW_CODE_TO_LEGACY = {
    "C2": "固定搭配",
    "D1": "词义辨析",
    "D2": "熟词僻义",
}


@router.get("/point-types", response_model=PointTypeListResponse)
async def get_point_types(db: AsyncSession = Depends(get_db)):
    """获取所有考点类型定义（V2）"""
    result = await db.execute(
        select(PointTypeDefinition).order_by(PointTypeDefinition.category, PointTypeDefinition.code)
    )
    definitions = result.scalars().all()

    items = [PointTypeBase(
        code=d.code,
        category=d.category,
        category_name=d.category_name,
        name=d.name,
        priority=d.priority,
        description=d.description
    ) for d in definitions]

    return PointTypeListResponse(total=len(items), items=items)


@router.get("/point-types/by-category", response_model=PointTypeByCategoryResponse)
async def get_point_types_by_category(db: AsyncSession = Depends(get_db)):
    """按大类获取考点类型（V2）"""
    result = await db.execute(
        select(PointTypeDefinition).order_by(PointTypeDefinition.code)
    )
    definitions = result.scalars().all()

    response = PointTypeByCategoryResponse()
    for d in definitions:
        pt = PointTypeBase(
            code=d.code,
            category=d.category,
            category_name=d.category_name,
            name=d.name,
            priority=d.priority,
            description=d.description
        )
        if d.category == "A":
            response.A.append(pt)
        elif d.category == "B":
            response.B.append(pt)
        elif d.category == "C":
            response.C.append(pt)
        elif d.category == "D":
            response.D.append(pt)
        elif d.category == "E":
            response.E.append(pt)

    return response


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

    # 获取所有学校
    schools_result = await db.execute(
        select(distinct(ExamPaper.school)).join(ClozePassage).where(ExamPaper.school != None)
    )
    schools = [s[0] for s in schools_result.fetchall() if s[0]]

    return ClozeFilters(
        grades=sorted(grades),
        topics=sorted(topics),
        years=sorted(years, reverse=True),
        regions=sorted(regions),
        schools=sorted(schools),
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
    school: Optional[str] = None,
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
    if school:
        query = query.join(ExamPaper).where(ExamPaper.school == school)
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
        # 统计考点分布 (V2: 使用 primary_point_code， V1: 兼容 point_type)
        point_dist = {}
        for point in p.points:
            # V2 优先使用 primary_point_code
            code = point.primary_point_code or point.point_type
            if code:
                point_dist[code] = point_dist.get(code, 0) + 1

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
                primary_point_code=pt.primary_point_code if hasattr(pt, 'primary_point_code') else None,
                # 固定搭配
                phrase=pt.phrase if hasattr(pt, 'phrase') else None,
                similar_phrases=json.loads(pt.similar_phrases) if hasattr(pt, 'similar_phrases') and pt.similar_phrases else None,
                # 词义辨析
                word_analysis=json.loads(pt.word_analysis) if hasattr(pt, 'word_analysis') and pt.word_analysis else None,
                dictionary_source=pt.dictionary_source if hasattr(pt, 'dictionary_source') else None,
                # 熟词僻义
                is_rare_meaning=pt.is_rare_meaning if hasattr(pt, 'is_rare_meaning') else False,
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
    grade: Optional[str] = None,
    keyword: Optional[str] = None,
    # V5 筛选参数（纯V5格式，不兼容旧数据）
    category: Optional[str] = Query(None, description="按大类筛选 (A/B/C/D/E)"),
    point_code: Optional[str] = Query(None, description="按考点编码筛选 (A1/B2/C2等)"),
    priority: Optional[int] = Query(None, description="按优先级筛选 (1=核心/2=重要/3=一般)"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """获取考点汇总（V5 纯净版本 - 仅使用 primary_point_code）"""
    # 先查询所有匹配的考点，不做分页（需要聚合）
    query = select(ClozePoint).options(
        selectinload(ClozePoint.cloze).selectinload(ClozePassage.paper)
    )

    # V5 筛选（仅使用 primary_point_code）
    if category:
        # 按大类筛选：匹配 primary_point_code 首字母
        query = query.where(ClozePoint.primary_point_code.startswith(category))

    if point_code:
        # 按具体考点编码筛选：精确匹配
        query = query.where(ClozePoint.primary_point_code == point_code)

    # 按优先级筛选
    if priority:
        priority_result = await db.execute(
            select(PointTypeDefinition.code).where(PointTypeDefinition.priority == priority)
        )
        priority_codes = [row[0] for row in priority_result.fetchall()]
        if priority_codes:
            query = query.where(ClozePoint.primary_point_code.in_(priority_codes))
        else:
            return PointListResponse(items=[], total=0, page=page, size=size)

    if grade:
        query = query.join(ClozePassage).join(ExamPaper).where(ExamPaper.grade == grade)
    if keyword:
        query = query.where(ClozePoint.correct_word.contains(keyword))

    # 排序
    query = query.order_by(ClozePoint.correct_word)

    result = await db.execute(query)
    all_points = result.scalars().all()

    # 按 (correct_word, primary_point_code) 聚合 - V5 纯净版本
    aggregated = {}
    for pt in all_points:
        agg_key = pt.primary_point_code or "词汇"  # V5: 直接使用 primary_point_code
        key = (pt.correct_word or "", agg_key)
        if key not in aggregated:
            aggregated[key] = []
        aggregated[key].append(pt)

    # 构建聚合后的列表
    summaries = []
    for (word, agg_key), points in aggregated.items():
        occurrences = []
        first_point = points[0]

        # 查询 V5 考点定义
        primary_point = None
        if first_point.primary_point_code:
            pt_def_result = await db.execute(
                select(PointTypeDefinition).where(PointTypeDefinition.code == first_point.primary_point_code)
            )
            pt_def = pt_def_result.scalar_one_or_none()
            if pt_def:
                primary_point = PointTypeBase(
                    code=pt_def.code,
                    category=pt_def.category,
                    category_name=pt_def.category_name,
                    name=pt_def.name,
                    priority=pt_def.priority,
                    description=pt_def.description
                )

        # V5: 使用编码和名称作为显示
        point_type_display = f"{primary_point.code} {primary_point.name}" if primary_point else agg_key

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
                is_rare_meaning=pt.is_rare_meaning if hasattr(pt, 'is_rare_meaning') else False,
                textbook_meaning=pt.textbook_meaning if hasattr(pt, 'textbook_meaning') else None,
                textbook_source=pt.textbook_source if hasattr(pt, 'textbook_source') else None,
                context_meaning=pt.context_meaning if hasattr(pt, 'context_meaning') else None,
                similar_words=json.loads(pt.similar_words) if hasattr(pt, 'similar_words') and pt.similar_words else None,
            )

            # 每个出现位置也包含 v2 考点信息
            occurrence_point = None
            if hasattr(pt, 'primary_point_code') and pt.primary_point_code:
                pt_def_occ_result = await db.execute(
                    select(PointTypeDefinition).where(PointTypeDefinition.code == pt.primary_point_code)
                )
                pt_def_occ = pt_def_occ_result.scalar_one_or_none()
                if pt_def_occ:
                    occurrence_point = PointTypeBase(
                        code=pt_def_occ.code,
                        category=pt_def_occ.category,
                        category_name=pt_def_occ.category_name,
                        name=pt_def_occ.name,
                        priority=pt_def_occ.priority,
                        description=pt_def_occ.description
                    )

            occurrences.append(PointOccurrence(
                sentence=pt.sentence or "",
                source=source,
                blank_number=pt.blank_number,
                point_type=pt.point_type or "词汇",
                passage_id=pt.cloze_id,
                point_id=pt.id,
                analysis=analysis
            ))
            # 附加 v2 数据（扩展字段，前端通过 (occ as any).primary_point 访问）
            if occurrence_point:
                occurrences[-1].__dict__['primary_point'] = occurrence_point

        # 根据考点类型选择释义字段：熟词僻义优先使用 context_meaning
        ptype = first_point.point_type or "词汇"
        if ptype == '熟词僻义' and hasattr(first_point, 'context_meaning') and first_point.context_meaning:
            definition = first_point.context_meaning
        else:
            definition = first_point.translation

        summary = PointSummary(
            word=word,
            definition=definition,
            frequency=len(points),
            point_type=point_type_display,
            occurrences=occurrences,
            tips=first_point.tips if hasattr(first_point, 'tips') else None
        )
        # 附加 v2 主考点数据（前端通过 (summary as any).primary_point 访问）
        if primary_point:
            summary.__dict__['primary_point'] = primary_point

        summaries.append(summary)

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

async def _build_point_v2_response(
    pt: ClozePoint,
    db: AsyncSession
) -> ClozePointNewResponse:
    """
    构建单个考点的 v2 格式响应

    [INPUT]: ClozePoint 对象、数据库会话
    [OUTPUT]: ClozePointNewResponse 对象
    [POS]: cloze.py 的私有辅助函数
    [PROTOCOL]: 变更时更新此头部
    """
    # 1. 查询主考点定义
    primary_point = None
    if hasattr(pt, 'primary_point_code') and pt.primary_point_code:
        result = await db.execute(
            select(PointTypeDefinition).where(PointTypeDefinition.code == pt.primary_point_code)
        )
        pt_def = result.scalar_one_or_none()
        if pt_def:
            primary_point = PointTypeBase(
                code=pt_def.code,
                category=pt_def.category,
                category_name=pt_def.category_name,
                name=pt_def.name,
                priority=pt_def.priority,
                description=pt_def.description
            )

    # 2. 查询辅助考点
    secondary_points = []
    sec_result = await db.execute(
        select(ClozeSecondaryPoint).where(ClozeSecondaryPoint.cloze_point_id == pt.id).order_by(ClozeSecondaryPoint.sort_order)
    )
    for sp in sec_result.scalars().all():
        secondary_points.append(SecondaryPointBase(
            point_code=sp.point_code,
            explanation=sp.explanation
        ))

    # 3. 查询排错点
    rejection_points = []
    rej_result = await db.execute(
        select(ClozeRejectionPoint).where(ClozeRejectionPoint.cloze_point_id == pt.id)
    )
    for rp in rej_result.scalars().all():
        rejection_points.append(RejectionPointBase(
            option_word=rp.option_word,
            point_code=rp.point_code,
            explanation=rp.explanation,
            rejection_code=rp.rejection_code,
            rejection_reason=rp.rejection_reason
        ))

    # 4. 确定旧类型（向后兼容）
    legacy_point_type = None
    if pt.point_type:
        legacy_point_type = pt.point_type
    elif pt.primary_point_code and pt.primary_point_code in NEW_CODE_TO_LEGACY:
        legacy_point_type = NEW_CODE_TO_LEGACY[pt.primary_point_code]

    return ClozePointNewResponse(
        id=pt.id,
        blank_number=pt.blank_number,
        correct_answer=pt.correct_answer,
        correct_word=pt.correct_word,
        options=json.loads(pt.options) if pt.options else {},
        sentence=pt.sentence,
        # v2 字段
        primary_point=primary_point,
        secondary_points=secondary_points,
        rejection_points=rejection_points,
        # 兼容字段
        legacy_point_type=legacy_point_type,
        point_type=pt.point_type,
        # 解析内容
        translation=pt.translation,
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
        is_rare_meaning=pt.is_rare_meaning if hasattr(pt, 'is_rare_meaning') else False,
        textbook_meaning=pt.textbook_meaning if hasattr(pt, 'textbook_meaning') else None,
        textbook_source=pt.textbook_source if hasattr(pt, 'textbook_source') else None,
        context_meaning=pt.context_meaning if hasattr(pt, 'context_meaning') else None,
        similar_words=json.loads(pt.similar_words) if hasattr(pt, 'similar_words') and pt.similar_words else None,
        # 状态
        point_verified=pt.point_verified if hasattr(pt, 'point_verified') else False
    )


@router.get("/{cloze_id}", response_model=ClozeDetailNewResponse)
async def get_cloze(
    cloze_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取完形文章详情 (v2 格式，支持多标签考点)"""
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

    # 构建考点列表（v2 格式）
    points_v2 = []
    point_dist_v1 = {}  # 旧分布
    point_dist_by_category = {}  # 新分布：按大类
    point_dist_by_priority = {}  # 新分布：按优先级

    for pt in passage.points:
        # 构建 v2 考点响应
        point_v2 = await _build_point_v2_response(pt, db)
        points_v2.append(point_v2)

        # 统计旧分布
        if pt.point_type:
            point_dist_v1[pt.point_type] = point_dist_v1.get(pt.point_type, 0) + 1

        # 统计新分布
        if hasattr(pt, 'primary_point_code') and pt.primary_point_code:
            category = pt.primary_point_code[0] if pt.primary_point_code else None
            if category:
                point_dist_by_category[category] = point_dist_by_category.get(category, 0) + 1

            # 查询优先级
            pt_def_result = await db.execute(
                select(PointTypeDefinition.priority).where(PointTypeDefinition.code == pt.primary_point_code)
            )
            priority_row = pt_def_result.first()
            if priority_row:
                priority_key = f"P{priority_row[0]}"
                point_dist_by_priority[priority_key] = point_dist_by_priority.get(priority_key, 0) + 1

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

    return ClozeDetailNewResponse(
        id=passage.id,
        paper_id=passage.paper_id,
        content=passage.content,
        original_content=passage.original_content,
        word_count=passage.word_count,
        primary_topic=passage.primary_topic,
        secondary_topics=json.loads(passage.secondary_topics) if passage.secondary_topics else [],
        topic_confidence=passage.topic_confidence,
        source=source,
        points=points_v2,
        # v2 分布统计
        point_distribution_by_category=point_dist_by_category,
        point_distribution_by_priority=point_dist_by_priority,
        # v1 兼容分布
        point_distribution=point_dist_v1,
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
#  删除接口
# ============================================================================

@router.delete("/{cloze_id}")
async def delete_cloze(
    cloze_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除完形文章及其关联数据"""
    # 1. 查询完形文章
    result = await db.execute(
        select(ClozePassage).where(ClozePassage.id == cloze_id)
    )
    cloze = result.scalar_one_or_none()

    if not cloze:
        raise HTTPException(status_code=404, detail="完形文章不存在")

    paper_id = cloze.paper_id
    filename = None

    # 获取试卷信息
    paper_result = await db.execute(
        select(ExamPaper).where(ExamPaper.id == paper_id)
    )
    paper = paper_result.scalar_one_or_none()
    if paper:
        filename = paper.filename

    # 2. 删除完形文章（ORM 级联删除关联的考点和词汇记录）
    await db.delete(cloze)
    await db.commit()

    # 3. 检查该试卷下是否还有其他文章
    remaining_reading = await db.scalar(
        select(func.count()).select_from(ReadingPassage).where(
            ReadingPassage.paper_id == paper_id
        )
    )
    remaining_cloze = await db.scalar(
        select(func.count()).select_from(ClozePassage).where(
            ClozePassage.paper_id == paper_id
        )
    )

    # 如果没有文章了，删除试卷
    paper_deleted = False
    if remaining_reading == 0 and remaining_cloze == 0 and paper:
        await db.delete(paper)
        await db.commit()
        paper_deleted = True

    return {
        "message": "删除成功，试卷也已删除" if paper_deleted else "删除成功",
        "cloze_id": cloze_id,
        "paper_deleted": paper_deleted,
        "filename": filename
    }


@router.post("/batch-delete")
async def batch_delete_clozes(
    ids: List[int],
    db: AsyncSession = Depends(get_db)
):
    """批量删除完形文章及其关联数据"""
    if not ids:
        raise HTTPException(status_code=400, detail="请提供要删除的完形文章ID")

    # 1. 收集所有受影响的 paper_id
    result = await db.execute(
        select(ClozePassage).where(ClozePassage.id.in_(ids))
    )
    clozes = result.scalars().all()

    if not clozes:
        raise HTTPException(status_code=404, detail="未找到要删除的完形文章")

    paper_ids = {c.paper_id for c in clozes}

    # 2. 批量删除完形文章（ORM 级联删除关联数据）
    deleted_count = 0
    for cloze in clozes:
        await db.delete(cloze)
        deleted_count += 1

    await db.commit()

    # 3. 检查并清理空试卷
    paper_deleted_count = 0
    for paper_id in paper_ids:
        # 检查该试卷下是否还有阅读文章
        remaining_reading = await db.scalar(
            select(func.count()).select_from(ReadingPassage).where(
                ReadingPassage.paper_id == paper_id
            )
        )
        # 检查该试卷下是否还有完形文章
        remaining_cloze = await db.scalar(
            select(func.count()).select_from(ClozePassage).where(
                ClozePassage.paper_id == paper_id
            )
        )
        # 如果没有文章了，删除试卷
        if remaining_reading == 0 and remaining_cloze == 0:
            paper = await db.get(ExamPaper, paper_id)
            if paper:
                await db.delete(paper)
                paper_deleted_count += 1

    await db.commit()

    return {
        "message": f"成功删除 {deleted_count} 篇完形文章",
        "deleted_count": deleted_count,
        "paper_deleted": paper_deleted_count
    }


@router.post("/blanks/{blank_id}/analyze-v5")
async def analyze_blank_point_v5(
    blank_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    使用 V5 分析器重新分析单个考点（全信号扫描 + 动态维度）

    [INPUT]: 考点 ID
    [OUTPUT]: 分析结果（包含主考点、辅助考点、排错点、置信度、熟词僻义信息）
    [POS]: cloze.py 的 V5 分析端点
    [PROTOCOL]: 变更时更新此头部

    V5 核心改进：
    1. 全信号扫描流程：B类→A类→D2→C类→A1兜底
    2. 动态维度：根据词性切换 dimensions 模板
    3. A5+D1融合场景：联合主考点，weight=co-primary
    4. 熟词僻义结构化：rare_meaning_info 独立字段
    5. 柯林斯词频：collins_frequency 字段
    """
    from app.services.cloze_analyzer import ClozeAnalyzerV5

    # 1. 查询考点
    result = await db.execute(
        select(ClozePoint)
        .options(selectinload(ClozePoint.cloze))
        .where(ClozePoint.id == blank_id)
    )
    point = result.scalar_one_or_none()

    if not point:
        raise HTTPException(status_code=404, detail="考点不存在")

    if not point.cloze:
        raise HTTPException(status_code=400, detail="考点未关联文章")

    # 2. 获取上下文
    full_content = point.cloze.original_content or point.cloze.content
    options = json.loads(point.options) if point.options else {}

    # 3. 调用 V5 分析器
    analyzer = ClozeAnalyzerV5()

    # 提取空格附近的上下文（前后各2句），提高分析精准度
    context = analyzer.extract_context(full_content, point.blank_number, context_sentences=2)

    analysis_result = await analyzer.analyze_point(
        blank_number=point.blank_number,
        correct_word=point.correct_word or "",
        options=options,
        context=context,
        db_session=db
    )

    if not analysis_result.success:
        raise HTTPException(status_code=500, detail=f"分析失败: {analysis_result.error}")

    # 4. 保存结果到数据库
    # 更新主考点编码
    if analysis_result.primary_point:
        point.primary_point_code = analysis_result.primary_point.get("code")
        # 更新旧类型（向后兼容）
        if point.primary_point_code in NEW_CODE_TO_LEGACY:
            point.point_type = NEW_CODE_TO_LEGACY[point.primary_point_code]

    # 更新 V5 置信度字段
    point.confidence = analysis_result.confidence
    point.confidence_reason = analysis_result.confidence_reason

    # 更新解析字段
    if analysis_result.translation:
        point.translation = analysis_result.translation
    if analysis_result.explanation:
        point.explanation = analysis_result.explanation
    if analysis_result.confusion_words:
        point.confusion_words = json.dumps(analysis_result.confusion_words, ensure_ascii=False)
    if analysis_result.tips:
        point.tips = analysis_result.tips

    # 更新 word_analysis (V5 包含 collins_frequency)
    if analysis_result.word_analysis:
        point.word_analysis = json.dumps(analysis_result.word_analysis, ensure_ascii=False)
    if analysis_result.dictionary_source:
        point.dictionary_source = analysis_result.dictionary_source

    # 更新熟词僻义信息
    if analysis_result.is_rare_meaning:
        point.is_rare_meaning = True
        if analysis_result.rare_meaning_info:
            point.rare_meaning_info = json.dumps(analysis_result.rare_meaning_info, ensure_ascii=False)
            # 兼容旧字段
            point.textbook_meaning = analysis_result.rare_meaning_info.get("common_meaning")
            point.context_meaning = analysis_result.rare_meaning_info.get("context_meaning")
            point.textbook_source = analysis_result.rare_meaning_info.get("textbook_source")

    # 5. 删除旧的辅助考点和排错点
    await db.execute(
        delete(ClozeSecondaryPoint).where(ClozeSecondaryPoint.cloze_point_id == point.id)
    )
    await db.execute(
        delete(ClozeRejectionPoint).where(ClozeRejectionPoint.cloze_point_id == point.id)
    )

    # 6. 插入新的辅助考点（V5 支持 weight 字段）
    if analysis_result.secondary_points:
        for idx, sp in enumerate(analysis_result.secondary_points):
            point_code = sp.get("code") or sp.get("point_code") or "D1"
            weight = sp.get("weight", "auxiliary")  # V5 新增
            new_sp = ClozeSecondaryPoint(
                cloze_point_id=point.id,
                point_code=point_code,
                weight=weight,
                explanation=sp.get("explanation"),
                sort_order=idx
            )
            db.add(new_sp)

    # 7. 插入新的排错点（V5 使用 rejection_code / rejection_reason）
    if analysis_result.rejection_points:
        for rp in analysis_result.rejection_points:
            new_rp = ClozeRejectionPoint(
                cloze_point_id=point.id,
                option_word=rp.get("option_word"),
                point_code=rp.get("rejection_code") or rp.get("code") or rp.get("point_code") or "D1",
                rejection_code=rp.get("rejection_code") or rp.get("code"),
                explanation=rp.get("rejection_reason") or rp.get("explanation"),
                rejection_reason=rp.get("rejection_reason") or rp.get("explanation")
            )
            db.add(new_rp)

    await db.commit()

    return {
        "message": "分析成功",
        "version": "v5",
        "confidence": analysis_result.confidence,
        "confidence_reason": analysis_result.confidence_reason,
        "primary_point": analysis_result.primary_point,
        "secondary_points": analysis_result.secondary_points,
        "rejection_points": analysis_result.rejection_points,
        "translation": analysis_result.translation,
        "explanation": analysis_result.explanation,
        "word_analysis": analysis_result.word_analysis,
        "is_rare_meaning": analysis_result.is_rare_meaning,
        "rare_meaning_info": analysis_result.rare_meaning_info
    }


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


def _normalize_paper_ids(paper_ids: Optional[List[int]]) -> Optional[List[int]]:
    ids = [paper_id for paper_id in (paper_ids or []) if paper_id is not None]
    return ids or None


def _apply_paper_filter(query, paper_ids: Optional[List[int]]):
    normalized_ids = _normalize_paper_ids(paper_ids)
    if normalized_ids:
        query = query.where(ExamPaper.id.in_(normalized_ids))
    return query


@router.get("/handouts/{grade}")
async def get_cloze_grade_handout(
    grade: str,
    edition: str = Query('teacher', pattern='^(teacher|student)$'),
    paper_ids: Optional[List[int]] = Query(None),
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
    topics = await _get_cloze_topic_stats_for_grade(db, grade, paper_ids)

    # 获取每个主题的内容
    content = []
    for topic_info in topics:
        topic = topic_info["topic"]
        topic_content = {
            "topic": topic,
            "part1_article_sources": await _get_cloze_article_sources(db, grade, topic, paper_ids),
            "part2_vocabulary": await _get_topic_vocabulary_with_source(db, grade, topic, paper_ids),
            "part3_points_by_type": await _get_points_by_type(db, grade, topic, paper_ids),
            "part4_passages": await _get_cloze_passages_with_points(db, grade, topic, edition, paper_ids)
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
    paper_ids: Optional[List[int]] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    获取某年级的完形主题统计（按考频降序）

    [INPUT]: 年级参数
    [OUTPUT]: 主题统计列表（按考频降序）
    [POS]: cloze.py 的讲义主题统计端点
    [PROTOCOL]: 变更时更新此头部
    """
    topics = await _get_cloze_topic_stats_for_grade(db, grade, paper_ids)
    return {"topics": topics}


@router.get("/handouts/{grade}/topics/{topic:path}")
async def get_cloze_handout_detail(
    grade: str,
    topic: str,
    edition: str = Query('teacher', pattern='^(teacher|student)$'),
    paper_ids: Optional[List[int]] = Query(None),
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
    article_sources = await _get_cloze_article_sources(db, grade, topic, paper_ids)

    # 第二部分：高频词汇
    vocabulary = await _get_topic_vocabulary_with_source(db, grade, topic, paper_ids)

    # 第三部分：考点分类
    points_by_type = await _get_points_by_type(db, grade, topic, paper_ids)

    # 第四部分：完形文章
    passages = await _get_cloze_passages_with_points(db, grade, topic, edition, paper_ids)

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

async def _get_cloze_topic_stats_for_grade(db: AsyncSession, grade: str, paper_ids: Optional[List[int]] = None):
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
    query = _apply_paper_filter(query, paper_ids)

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


async def _get_cloze_article_sources(db: AsyncSession, grade: str, topic: str, paper_ids: Optional[List[int]] = None):
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
    query = _apply_paper_filter(query, paper_ids)
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


async def _get_topic_vocabulary_with_source(db: AsyncSession, grade: str, topic: str, paper_ids: Optional[List[int]] = None):
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
    reading_query = _apply_paper_filter(reading_query, paper_ids)
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
    cloze_query = _apply_paper_filter(cloze_query, paper_ids)
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


async def _get_points_by_type(db: AsyncSession, grade: str, topic: str, paper_ids: Optional[List[int]] = None):
    """
    获取主题下按 V2 考点编码分组的考点（聚合统计）

    [INPUT]: 数据库会话、年级、主题
    [OUTPUT]: 按考点编码分组的考点数据（A1-E2）
    [POS]: cloze.py 的私有辅助函数
    [PROTOCOL]: 变更时更新此头部
    """
    # 首先获取所有考点类型定义，用于获取名称和大类信息
    type_defs_result = await db.execute(select(PointTypeDefinition))
    type_defs = {td.code: td for td in type_defs_result.scalars().all()}

    # 查询考点数据
    query = (
        select(ClozePoint, ClozePassage, ExamPaper)
        .join(ClozePassage, ClozePoint.cloze_id == ClozePassage.id)
        .join(ExamPaper, ClozePassage.paper_id == ExamPaper.id)
        .where(ExamPaper.grade == grade)
        .where(ClozePassage.primary_topic == topic)
        .where(ClozePoint.correct_word.isnot(None))
    )
    query = _apply_paper_filter(query, paper_ids)

    result = await db.execute(query)

    # 按考点编码和单词分组（使用动态字典）
    grouped: Dict[str, Dict] = {}

    for point, passage, paper in result.all():
        # 获取考点编码：优先使用 primary_point_code，否则通过旧类型映射
        point_code = point.primary_point_code
        if not point_code and point.point_type:
            point_code = LEGACY_TO_NEW_CODE.get(point.point_type)

        # 如果仍然没有编码，跳过
        if not point_code:
            continue

        # 获取考点元数据
        type_def = type_defs.get(point_code)
        category = type_def.category if type_def else point_code[0] if point_code else ""
        category_name = type_def.category_name if type_def else ""
        point_name = type_def.name if type_def else point_code

        word = point.correct_word or ""

        # 初始化考点编码分组
        if point_code not in grouped:
            grouped[point_code] = {
                "code": point_code,
                "name": point_name,
                "category": category,
                "category_name": category_name,
                "words": {}  # 按单词分组
            }

        # 初始化单词分组
        if word not in grouped[point_code]["words"]:
            # 过滤 word_analysis 中的 rejection_reason（应只在 rejection_points 中）
            raw_word_analysis = json.loads(point.word_analysis) if point.word_analysis else None
            if raw_word_analysis:
                for w in raw_word_analysis:
                    if isinstance(raw_word_analysis[w], dict):
                        raw_word_analysis[w].pop("rejection_reason", None)

            grouped[point_code]["words"][word] = {
                "word": word,
                "frequency": 0,
                "definition": point.translation,
                "word_analysis": raw_word_analysis,
                "dictionary_source": point.dictionary_source,
                "phrase": point.phrase,
                "similar_phrases": json.loads(point.similar_phrases) if point.similar_phrases else None,
                "textbook_meaning": point.textbook_meaning,
                "textbook_source": point.textbook_source,
                "context_meaning": point.context_meaning,
                "similar_words": json.loads(point.similar_words) if point.similar_words else None,
                "occurrences": []
            }

        # 增加频次
        grouped[point_code]["words"][word]["frequency"] += 1

        # 添加出现记录
        source = f"{paper.year}{paper.region}{paper.grade}{paper.exam_type or ''}·完形"

        # 过滤 word_analysis 中的 rejection_reason 字段（应只在 rejection_points 中）
        analysis_word_analysis = json.loads(point.word_analysis) if point.word_analysis else None
        if analysis_word_analysis:
            for w in analysis_word_analysis:
                if isinstance(analysis_word_analysis[w], dict):
                    analysis_word_analysis[w].pop("rejection_reason", None)

        analysis = PointAnalysis(
            explanation=point.explanation,
            confusion_words=json.loads(point.confusion_words) if point.confusion_words else None,
            tips=point.tips if hasattr(point, 'tips') else None,
            phrase=point.phrase,
            similar_phrases=json.loads(point.similar_phrases) if point.similar_phrases else None,
            word_analysis=analysis_word_analysis,
            dictionary_source=point.dictionary_source,
            textbook_meaning=point.textbook_meaning,
            textbook_source=point.textbook_source,
            context_meaning=point.context_meaning,
            similar_words=json.loads(point.similar_words) if point.similar_words else None,
        )

        occurrence = PointOccurrence(
            sentence=point.sentence or "",
            source=source,
            blank_number=point.blank_number,
            point_type=point_code,  # 使用 V2 编码
            passage_id=passage.id,
            point_id=point.id,
            analysis=analysis
        )
        grouped[point_code]["words"][word]["occurrences"].append(occurrence)

    # 转换为最终格式，并按大类和编码排序
    def sort_key(code):
        # 按大类 (A-E) 和数字排序
        return (code[0] if code else "Z", int(code[1]) if len(code) > 1 and code[1].isdigit() else 0)

    points_by_type = {}
    for code in sorted(grouped.keys(), key=sort_key):
        data = grouped[code]
        points_by_type[code] = {
            "code": data["code"],
            "name": data["name"],
            "category": data["category"],
            "category_name": data["category_name"],
            "points": sorted(list(data["words"].values()), key=lambda x: -x["frequency"])
        }

    return points_by_type


async def _get_cloze_passages_with_points(
    db: AsyncSession,
    grade: str,
    topic: str,
    edition: str,
    paper_ids: Optional[List[int]] = None
):
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
    query = _apply_paper_filter(query, paper_ids)

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
            # 查询排错点（仅教师版）
            rejection_points_data = []
            if edition == 'teacher':
                rp_query = select(ClozeRejectionPoint).where(
                    ClozeRejectionPoint.cloze_point_id == pt.id
                )
                rp_result = await db.execute(rp_query)
                rejection_points_records = rp_result.scalars().all()
                rejection_points_data = [
                    {
                        "option_word": rp.option_word,
                        "point_code": rp.point_code,
                        "explanation": rp.explanation,
                        "rejection_code": rp.rejection_code,
                        "rejection_reason": rp.rejection_reason
                    }
                    for rp in rejection_points_records
                ]

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
                is_rare_meaning=pt.is_rare_meaning if hasattr(pt, 'is_rare_meaning') else False,
                tips=pt.tips if hasattr(pt, 'tips') and edition == 'teacher' else None,
                rejection_points=rejection_points_data
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
