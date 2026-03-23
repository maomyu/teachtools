"""
阅读模块API

[INPUT]: 依赖 FastAPI、SQLAlchemy、reading/cloze/vocabulary 模型
[OUTPUT]: 对外提供阅读文章查询、讲义生成等 API 接口
[POS]: backend/app/api 的阅读路由
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.reading import ReadingPassage, Question
from app.models.paper import ExamPaper
from app.models.vocabulary import Vocabulary, VocabularyPassage
from app.models.cloze import ClozePassage
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

    # 查询所有不重复的学校
    schools_query = select(ExamPaper.school).distinct().where(ExamPaper.school.isnot(None)).order_by(ExamPaper.school)
    schools_result = await db.execute(schools_query)
    schools = [s for s in schools_result.scalars().all() if s]

    return {
        "years": years,
        "grades": grades,
        "exam_types": exam_types,
        "regions": regions,
        "schools": schools,
        "topics": topics,
        "semesters": semesters
    }


@router.get("", response_model=PassageListResponse)
async def list_passages(
    grade: Optional[str] = None,
    topic: Optional[str] = None,
    year: Optional[int] = None,
    region: Optional[str] = None,
    school: Optional[str] = None,
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
    if school:
        query = query.join(ReadingPassage.paper).where(ReadingPassage.paper.has(school=school))
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
            # 收集该词汇的所有出现位置，并去重（按 char_position）
            all_occurrences = [
                o for o in passage.vocabulary_occurrences
                if o.vocabulary_id == occ.vocabulary_id
            ]
            # 按 char_position 去重
            unique_occurrences = {}
            for o in all_occurrences:
                key = o.char_position
                if key not in unique_occurrences:
                    unique_occurrences[key] = {
                        "sentence": o.sentence,
                        "char_position": o.char_position,
                        "end_position": o.end_position
                    }

            vocab_list.append({
                "id": occ.vocabulary.id,
                "word": occ.vocabulary.word,
                "definition": occ.vocabulary.definition,
                "frequency": occ.vocabulary.frequency,
                "occurrences": list(unique_occurrences.values())
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


# 导入delete用于级联删除
from sqlalchemy import delete as sql_delete


@router.delete("/{passage_id}")
async def delete_passage(
    passage_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除文章及其关联数据"""
    from sqlalchemy import delete

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

    # 1. 删除关联的词汇出现记录
    result = await db.execute(
        delete(VocabularyPassage).where(VocabularyPassage.passage_id == passage_id)
    )
    deleted_occurrences = result.rowcount if hasattr(result, 'rowcount') else 0

    # 2. 删除关联的题目记录
    result = await db.execute(
        delete(Question).where(Question.passage_id == passage_id)
    )
    deleted_questions = result.rowcount if hasattr(result, 'rowcount') else 0

    # 3. 删除文章本身
    await db.delete(passage)
    await db.commit()

    # 检查该试卷下是否还有其他阅读文章或完形文章
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

    # 如果没有文章了，删除试卷记录（同时清理完形关联数据）
    if remaining_reading == 0 and remaining_cloze == 0 and paper:
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


@router.post("/batch-delete")
async def batch_delete_passages(
    ids: List[int],
    db: AsyncSession = Depends(get_db)
):
    """批量删除文章及其关联数据"""
    from sqlalchemy import delete

    if not ids:
        raise HTTPException(status_code=400, detail="请提供要删除的文章ID")

    # 1. 收集所有受影响的 paper_id
    query = select(ReadingPassage).where(ReadingPassage.id.in_(ids))
    result = await db.execute(query)
    passages = result.scalars().all()

    if not passages:
        raise HTTPException(status_code=404, detail="未找到要删除的文章")

    paper_ids = {p.paper_id for p in passages}

    # 2. 批量删除关联数据
    # 删除词汇出现记录
    await db.execute(
        delete(VocabularyPassage).where(VocabularyPassage.passage_id.in_(ids))
    )
    # 删除题目记录
    await db.execute(
        delete(Question).where(Question.passage_id.in_(ids))
    )
    # 删除文章
    deleted_count = 0
    for passage in passages:
        await db.delete(passage)
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
        "message": f"成功删除 {deleted_count} 篇文章",
        "deleted_count": deleted_count,
        "paper_deleted": paper_deleted_count
    }


# ============================================================================
#  讲义API端点
# ============================================================================

# 导入完形词汇模型用于联合查询
from app.models.vocabulary_cloze import VocabularyCloze


@router.get("/handouts/{grade}")
async def get_grade_handout(
    grade: str,
    edition: str = Query('teacher', pattern='^(teacher|student)$'),
    db: AsyncSession = Depends(get_db)
):
    """
    获取某年级的完整讲义（包含所有主题）

    [INPUT]: 年级参数、版本（teacher/student）
    [OUTPUT]: 年级讲义结构（目录 + 各主题内容）
    [POS]: reading.py 的年级讲义端点
    [PROTOCOL]: 变更时更新此头部
    """
    # 获取主题统计（按考频排序）
    topics = await _get_topic_stats_for_grade(db, grade)

    # 获取每个主题的内容
    content = []
    for topic_info in topics:
        topic = topic_info["topic"]
        topic_content = {
            "topic": topic,
            "part1_article_sources": await _get_article_sources(db, grade, topic),
            "part2_vocabulary": await _get_topic_vocabulary_with_source(db, grade, topic),
            "part3_passages": await _get_topic_passages(db, grade, topic, edition)
        }
        content.append(topic_content)

    return {
        "grade": grade,
        "edition": edition,
        "topics": topics,
        "content": content
    }


async def _get_topic_stats_for_grade(db: AsyncSession, grade: str):
    """
    获取某年级的主题统计（按考频降序）

    [INPUT]: 数据库会话、年级
    [OUTPUT]: 主题统计列表（按考频降序）
    [POS]: reading.py 的私有辅助函数
    [PROTOCOL]: 变更时更新此头部
    """
    query = (
        select(
            ReadingPassage.primary_topic.label('topic'),
            func.count(ReadingPassage.id).label('passage_count'),
            func.group_concat(ExamPaper.year.distinct()).label('years')
        )
        .join(ExamPaper, ReadingPassage.paper_id == ExamPaper.id)
        .where(ExamPaper.grade == grade)
        .where(ReadingPassage.primary_topic.isnot(None))
        .group_by(ReadingPassage.primary_topic)
        .order_by(func.count(ReadingPassage.id).desc())
    )

    result = await db.execute(query)
    topics = []
    for row in result.all():
        years = sorted(set(int(y) for y in row.years.split(',')), reverse=True) if row.years else []
        topics.append({
            "topic": row.topic,
            "passage_count": row.passage_count,
            "recent_years": years[:3]
        })

    return topics


@router.get("/handouts/{grade}/topics")
async def get_topic_stats_for_grade(
    grade: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取某年级的主题统计（按考频降序）

    [INPUT]: 年级参数
    [OUTPUT]: 主题统计列表（按考频降序）
    [POS]: reading.py 的讲义主题统计端点
    [PROTOCOL]: 变更时更新此头部
    """
    topics = await _get_topic_stats_for_grade(db, grade)
    return {"topics": topics}


@router.get("/handouts/{grade}/topics/{topic:path}")
async def get_handout_detail(
    grade: str,
    topic: str,
    edition: str = Query('teacher', pattern='^(teacher|student)$'),
    db: AsyncSession = Depends(get_db)
):
    """
    获取某年级某主题的讲义详情

    [INPUT]: 年级、主题、版本（teacher/student）
    [OUTPUT]: 三段式讲义结构
    [POS]: reading.py 的讲义详情端点
    [PROTOCOL]: 变更时更新此头部
    """
    # 第一部分：文章来源
    article_sources = await _get_article_sources(db, grade, topic)

    # 第二部分：高频词汇（仅阅读）
    vocabulary = await _get_topic_vocabulary(db, grade, topic)

    # 第三部分：阅读文章（含题目）
    passages = await _get_topic_passages(db, grade, topic, edition)

    return {
        "topic": topic,
        "grade": grade,
        "edition": edition,
        "part1_article_sources": article_sources,
        "part2_vocabulary": vocabulary,
        "part3_passages": passages
    }


# ============================================================================
#  讲义辅助函数
# ============================================================================

async def _get_article_sources(db: AsyncSession, grade: str, topic: str):
    """
    获取主题下所有文章来源（按年份+区县分组）

    [INPUT]: 数据库会话、年级、主题
    [OUTPUT]: 文章来源列表（按试卷分组）
    [POS]: reading.py 的私有辅助函数
    [PROTOCOL]: 变更时更新此头部
    """
    query = (
        select(ReadingPassage, ExamPaper)
        .join(ExamPaper, ReadingPassage.paper_id == ExamPaper.id)
        .where(ExamPaper.grade == grade)
        .where(ReadingPassage.primary_topic == topic)
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
            "type": passage.passage_type,
            "id": passage.id,
            "title": passage.title
        })

    return list(sources.values())


async def _get_topic_vocabulary(db: AsyncSession, grade: str, topic: str):
    """
    获取主题高频词汇（仅来自阅读文章，按词频排序）

    [INPUT]: 数据库会话、年级、主题
    [OUTPUT]: 高频词汇列表（按词频降序）
    [POS]: reading.py 的私有辅助函数
    [PROTOCOL]: 变更时更新此头部
    """
    query = (
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
        .order_by(func.count(VocabularyPassage.id).desc())
    )

    result = await db.execute(query)
    vocabulary = []
    for row in result.all():
        vocabulary.append({
            "id": row.id,
            "word": row.word,
            "definition": row.definition,
            "phonetic": row.phonetic,
            "frequency": row.frequency
        })

    return vocabulary


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
    [POS]: reading.py 的私有辅助函数
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
            # 两者都有：词频相加
            source_type = "both"
            freq = reading_vocabs[vid]["frequency"] + cloze_vocabs[vid]["frequency"]
            vocab_data = reading_vocabs[vid]  # 使用阅读的数据（definition 等）
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


async def _get_topic_passages(db: AsyncSession, grade: str, topic: str, edition: str):
    """
    获取主题下的阅读文章（含题目）

    [INPUT]: 数据库会话、年级、主题、版本（teacher/student）
    [OUTPUT]: 文章列表（含题目，根据版本决定是否包含答案）
    [POS]: reading.py 的私有辅助函数
    [PROTOCOL]: 变更时更新此头部
    """
    query = (
        select(ReadingPassage)
        .options(
            selectinload(ReadingPassage.paper),
            selectinload(ReadingPassage.questions),
            selectinload(ReadingPassage.vocabulary_occurrences).selectinload(VocabularyPassage.vocabulary)
        )
        .join(ExamPaper, ReadingPassage.paper_id == ExamPaper.id)
        .where(ExamPaper.grade == grade)
        .where(ReadingPassage.primary_topic == topic)
        .order_by(ExamPaper.year.desc(), ReadingPassage.passage_type)
    )

    result = await db.execute(query)
    passages = result.scalars().all()

    # 构建文章列表
    items = []
    for p in passages:
        # 词汇列表
        vocab_list = []
        seen_words = set()
        for occ in p.vocabulary_occurrences:
            if occ.vocabulary.word not in seen_words:
                # 收集该词汇的所有出现位置，并按 char_position 去重
                all_occurrences = [
                    o for o in p.vocabulary_occurrences
                    if o.vocabulary_id == occ.vocabulary_id
                ]
                unique_occurrences = {}
                for o in all_occurrences:
                    key = o.char_position
                    if key not in unique_occurrences:
                        unique_occurrences[key] = {
                            "sentence": o.sentence,
                            "char_position": o.char_position,
                            "end_position": o.end_position
                        }

                vocab_list.append({
                    "id": occ.vocabulary.id,
                    "word": occ.vocabulary.word,
                    "definition": occ.vocabulary.definition,
                    "frequency": occ.vocabulary.frequency,
                    "occurrences": list(unique_occurrences.values())
                })
                seen_words.add(occ.vocabulary.word)

        passage_data = {
            "id": p.id,
            "type": p.passage_type,
            "title": p.title,
            "content": p.content,
            "word_count": p.word_count,
            "source": p.source_info,
            "vocabulary": vocab_list
        }

        # 教师版包含答案和解析
        if edition == 'teacher':
            passage_data["questions"] = [
                {
                    "number": q.question_number,
                    "text": q.question_text,
                    "options": {
                        "A": q.option_a,
                        "B": q.option_b,
                        "C": q.option_c,
                        "D": q.option_d
                    },
                    "correct_answer": q.correct_answer,
                    "explanation": q.answer_explanation
                }
                for q in p.questions
            ]
        else:
            # 学生版只有题目
            passage_data["questions"] = [
                {
                    "number": q.question_number,
                    "text": q.question_text,
                    "options": {
                        "A": q.option_a,
                        "B": q.option_b,
                        "C": q.option_c,
                        "D": q.option_d
                    }
                }
                for q in p.questions
            ]

        items.append(passage_data)

    return items
