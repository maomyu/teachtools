"""
阅读模块API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.reading import ReadingPassage, Question
from app.models.paper import ExamPaper
from app.models.vocabulary import Vocabulary, VocabularyPassage
from app.schemas.reading import (
    PassageResponse,
    PassageListResponse,
    PassageDetailResponse,
    TopicUpdateRequest
)

router = APIRouter()


@router.get("/filters")
async def get_passage_filters(db: AsyncSession = Depends(get_db)):
    """获取文章筛选项（动态从数据库获取）"""
    # 查询所有不重复的年份
    years_query = select(ExamPaper.year).distinct().where(ExamPaper.year.isnot(None)).order_by(ExamPaper.year.desc())
    years_result = await db.execute(years_query)
    years = [y for y in years_result.scalars().all() if y]

    # 查询所有不重复的年级
    grades_query = select(ExamPaper.grade).distinct().where(ExamPaper.grade.isnot(None)).order_by(ExamPaper.grade)
    grades_result = await db.execute(grades_query)
    grades = [g for g in grades_result.scalars().all() if g]

    # 查询所有不重复的考试类型
    exam_types_query = select(ExamPaper.exam_type).distinct().where(ExamPaper.exam_type.isnot(None)).order_by(ExamPaper.exam_type)
    exam_types_result = await db.execute(exam_types_query)
    exam_types = [e for e in exam_types_result.scalars().all() if e]

    # 查询所有不重复的区县
    regions_query = select(ExamPaper.region).distinct().where(ExamPaper.region.isnot(None)).order_by(ExamPaper.region)
    regions_result = await db.execute(regions_query)
    regions = [r for r in regions_result.scalars().all() if r]

    # 查询实际有文章使用的话题
    topics_query = select(ReadingPassage.primary_topic).distinct().where(
        ReadingPassage.primary_topic.isnot(None)
    ).order_by(ReadingPassage.primary_topic)
    topics_result = await db.execute(topics_query)
    topics = [t for t in topics_result.scalars().all() if t]

    # 查询所有不重复的学期
    semesters_query = select(ExamPaper.semester).distinct().where(ExamPaper.semester.isnot(None)).order_by(ExamPaper.semester)
    semesters_result = await db.execute(semesters_query)
    semesters = [s for s in semesters_result.scalars().all() if s]

    return {
        "years": years,
        "grades": grades,
        "exam_types": exam_types,
        "regions": regions,
        "topics": topics,
        "semesters": semesters
    }


@router.get("", response_model=PassageListResponse)
async def list_passages(
    grade: Optional[str] = None,
    topic: Optional[str] = None,
    year: Optional[int] = None,
    region: Optional[str] = None,
    exam_type: Optional[str] = None,
    semester: Optional[str] = None,
    search: Optional[str] = None,
    passage_type: Optional[str] = None,  # C 或 D
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """获取阅读文章列表"""
    query = select(ReadingPassage).options(selectinload(ReadingPassage.paper))

    # 筛选条件
    if grade:
        query = query.join(ReadingPassage.paper).where(ReadingPassage.paper.has(grade=grade))
    if topic:
        query = query.where(ReadingPassage.primary_topic == topic)
    if year:
        query = query.join(ReadingPassage.paper).where(ReadingPassage.paper.has(year=year))
    if region:
        query = query.join(ReadingPassage.paper).where(ReadingPassage.paper.has(region=region))
    if exam_type:
        query = query.join(ReadingPassage.paper).where(ReadingPassage.paper.has(exam_type=exam_type))
    if semester:
        query = query.join(ReadingPassage.paper).where(ReadingPassage.paper.has(semester=semester))
    if passage_type:
        query = query.where(ReadingPassage.passage_type == passage_type)

    # FTS5全文搜索
    if search:
        # 使用FTS5进行全文搜索
        fts_query = text("""
            SELECT rowid FROM reading_passage_fts
            WHERE reading_passage_fts MATCH :search
            ORDER BY rank
        """)
        # TODO: 实现FTS5搜索逻辑

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # 统计 C 篇和 D 篇数量（无筛选时的总数）
    c_count_query = select(func.count()).select_from(
        select(ReadingPassage).where(ReadingPassage.passage_type == 'C').subquery()
    )
    d_count_query = select(func.count()).select_from(
        select(ReadingPassage).where(ReadingPassage.passage_type == 'D').subquery()
    )
    c_count = await db.scalar(c_count_query) or 0
    d_count = await db.scalar(d_count_query) or 0

    # 分页
    query = query.offset((page - 1) * size).limit(size)
    query = query.order_by(ReadingPassage.created_at.desc())

    result = await db.execute(query)
    passages = result.scalars().all()

    # 构建响应数据
    items = []
    for p in passages:
        data = {
            'id': p.id,
            'paper_id': p.paper_id,
            'passage_type': p.passage_type,
            'title': p.title,
            'content': p.content,
            'word_count': p.word_count,
            'primary_topic': p.primary_topic,
            'secondary_topics': p.secondary_topics,
            'topic_confidence': p.topic_confidence,
            'topic_verified': p.topic_verified,
            'source': p.source_info if hasattr(p, 'source_info') else None,
            'created_at': p.created_at,
        }
        items.append(PassageResponse.model_validate(data))

    return PassageListResponse(
        total=total or 0,
        items=items,
        c_count=c_count,
        d_count=d_count
    )


@router.get("/{passage_id}", response_model=PassageDetailResponse)
async def get_passage(
    passage_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取文章详情（含词汇列表和题目）"""
    query = select(ReadingPassage).where(ReadingPassage.id == passage_id)
    query = query.options(
        selectinload(ReadingPassage.paper),
        selectinload(ReadingPassage.questions),
        selectinload(ReadingPassage.vocabulary_occurrences).selectinload(VocabularyPassage.vocabulary)
    )

    result = await db.execute(query)
    passage = result.scalar_one_or_none()

    if not passage:
        raise HTTPException(status_code=404, detail="文章不存在")

    # 构建词汇列表
    vocab_list = []
    seen_words = set()
    for occ in passage.vocabulary_occurrences:
        if occ.vocabulary.word not in seen_words:
            vocab_list.append({
                "id": occ.vocabulary.id,
                "word": occ.vocabulary.word,
                "definition": occ.vocabulary.definition,
                "frequency": occ.vocabulary.frequency,
                "occurrences": [
                    {
                        "sentence": o.sentence,
                        "char_position": o.char_position,
                        "end_position": o.end_position
                    }
                    for o in passage.vocabulary_occurrences
                    if o.vocabulary_id == occ.vocabulary_id
                ]
            })
            seen_words.add(occ.vocabulary.word)

    # 构建题目列表
    questions_list = []
    for q in passage.questions:
        questions_list.append({
            "id": q.id,
            "question_number": q.question_number,
            "question_text": q.question_text,
            "options": {
                "A": q.option_a,
                "B": q.option_b,
                "C": q.option_c,
                "D": q.option_d
            },
            "correct_answer": q.correct_answer,
            "answer_explanation": q.answer_explanation
        })

    # 构建响应数据
    data = {
        'id': passage.id,
        'paper_id': passage.paper_id,
        'passage_type': passage.passage_type,
        'title': passage.title,
        'content': passage.content,
        'word_count': passage.word_count,
        'primary_topic': passage.primary_topic,
        'secondary_topics': passage.secondary_topics,
        'topic_confidence': passage.topic_confidence,
        'topic_verified': passage.topic_verified,
        'source': passage.source_info if hasattr(passage, 'source_info') else None,
        'created_at': passage.created_at,
        'vocabulary': vocab_list,
        'questions': questions_list,
        'has_questions': passage.has_questions,
    }
    response = PassageDetailResponse.model_validate(data)

    return response


@router.put("/{passage_id}/topic")
async def update_topic(
    passage_id: int,
    request: TopicUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """更新文章话题（人工校对）"""
    query = select(ReadingPassage).where(ReadingPassage.id == passage_id)
    result = await db.execute(query)
    passage = result.scalar_one_or_none()

    if not passage:
        raise HTTPException(status_code=404, detail="文章不存在")

    passage.primary_topic = request.primary_topic
    passage.secondary_topics = request.secondary_topics
    passage.topic_verified = True
    passage.verified_by = request.verified_by

    await db.commit()

    return {"message": "话题更新成功", "passage_id": passage_id}


# 导入text用于原生SQL
from sqlalchemy import text


@router.delete("/{passage_id}")
async def delete_passage(
    passage_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除文章"""
    query = select(ReadingPassage).where(ReadingPassage.id == passage_id)
    result = await db.execute(query)
    passage = result.scalar_one_or_none()

    if not passage:
        raise HTTPException(status_code=404, detail="文章不存在")

    paper_id = passage.paper_id
    filename = None

    # 获取试卷信息
    paper_query = select(ExamPaper).where(ExamPaper.id == paper_id)
    paper_result = await db.execute(paper_query)
    paper = paper_result.scalar_one_or_none()
    if paper:
        filename = paper.filename

    # 删除文章
    await db.delete(passage)
    await db.commit()

    # 检查该试卷下是否还有其他文章
    remaining_query = select(func.count()).select_from(ReadingPassage).where(
        ReadingPassage.paper_id == paper_id
    )
    remaining_count = await db.scalar(remaining_query)

    # 如果没有文章了，删除试卷记录
    if remaining_count == 0 and paper:
        await db.delete(paper)
        await db.commit()
        return {
            "message": "删除成功，试卷也已删除",
            "passage_id": passage_id,
            "paper_deleted": True,
            "filename": filename
        }

    return {
        "message": "删除成功",
        "passage_id": passage_id,
        "paper_deleted": False
    }
