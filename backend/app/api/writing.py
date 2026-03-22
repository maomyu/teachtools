"""
作文模块 API

[INPUT]: 依赖 FastAPI、SQLAlchemy、writing 模型和服务
[OUTPUT]: 对外提供作文查询、文体识别、范文生成等 API 接口
[POS]: backend/app/api 的作文路由
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models.writing import WritingTask, WritingTemplate, WritingSample
from app.schemas.writing import (
    WritingTaskResponse,
    WritingTaskListResponse,
    WritingTaskDetailResponse,
    WritingFilter,
    WritingTypeDetectResponse,
    BatchGenerateResponse,
    WritingFiltersResponse,
    TemplateResponse,
    SampleResponse,
    # 讲义相关
    WritingHandoutTopicStats,
    WritingHandoutDetailResponse,
    WritingGradeHandoutResponse,
)
from app.services.writing_service import WritingService

router = APIRouter()


# ==============================================================================
#                              筛选项
# ==============================================================================

@router.get("/filters", response_model=WritingFiltersResponse)
async def get_writing_filters(db: AsyncSession = Depends(get_db)):
    """获取作文筛选项（动态从数据库获取）"""
    service = WritingService(db)
    filters = await service.get_filters()
    return WritingFiltersResponse(**filters)


# ==============================================================================
#                              列表查询
# ==============================================================================

@router.get("", response_model=WritingTaskListResponse)
async def get_writings(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    grade: Optional[str] = Query(None),
    semester: Optional[str] = Query(None),
    exam_type: Optional[str] = Query(None),
    writing_type: Optional[str] = Query(None),
    application_type: Optional[str] = Query(None),
    topic: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    获取作文列表

    支持按年级、学期、考试类型、文体类型、应用文子类型、话题筛选
    """
    service = WritingService(db)
    items, total, grade_counts = await service.get_writings(
        page=page,
        size=size,
        grade=grade,
        semester=semester,
        exam_type=exam_type,
        writing_type=writing_type,
        application_type=application_type,
        topic=topic,
        search=search
    )

    # 构建响应
    response_items = []
    for task in items:
        source = None
        if task.paper:
            source = {
                "year": task.paper.year,
                "region": task.paper.region,
                "school": task.paper.school,
                "grade": task.paper.grade,
                "exam_type": task.paper.exam_type,
                "semester": task.paper.semester,
                "filename": task.paper.filename,
            }

        response_items.append(WritingTaskResponse(
            id=task.id,
            paper_id=task.paper_id,
            task_content=task.task_content,
            requirements=task.requirements,
            word_limit=task.word_limit,
            points_value=task.points_value,
            grade=task.grade,
            semester=task.semester,
            exam_type=task.exam_type,
            writing_type=task.writing_type,
            application_type=task.application_type,
            primary_topic=task.primary_topic,
            topic_verified=task.topic_verified,
            source=source,
            created_at=task.created_at,
        ))

    return WritingTaskListResponse(
        total=total,
        items=response_items,
        grade_counts=grade_counts,
    )


# ==============================================================================
#                              讲义功能（放在 /{task_id} 之前）
# ==============================================================================

@router.get("/handouts/{grade}/topics")
async def get_writing_handout_topics(
    grade: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取年级话题统计（按题目数量排序）

    Args:
        grade: 年级（初一/初二/初三）
    """
    service = WritingService(db)
    topics = await service.get_topic_stats_for_grade(grade)
    return {"grade": grade, "topics": topics}


@router.get("/handouts/{grade}/topics/{topic:path}")
async def get_writing_handout_detail(
    grade: str,
    topic: str,
    edition: str = Query('teacher', pattern='^(teacher|student)$'),
    db: AsyncSession = Depends(get_db)
):
    """
    获取单话题作文讲义详情（四段式）

    Args:
        grade: 年级
        topic: 话题名称（URL编码）
        edition: teacher/student
    """
    from urllib.parse import unquote
    topic = unquote(topic)

    service = WritingService(db)
    content = await service.get_topic_handout_content(grade, topic, edition)

    return WritingHandoutDetailResponse(
        topic=content["topic"],
        grade=content["grade"],
        edition=content["edition"],
        part1_topic_stats=content["part1_topic_stats"],
        part2_frameworks=content["part2_frameworks"],
        part3_expressions=content["part3_expressions"],
        part4_samples=content["part4_samples"]
    )


@router.get("/handouts/{grade}")
async def get_writing_handout(
    grade: str,
    edition: str = Query('teacher', pattern='^(teacher|student)$'),
    db: AsyncSession = Depends(get_db)
):
    """
    获取年级完整作文讲义（含所有话题）

    Args:
        grade: 年级
        edition: teacher/student
    """
    service = WritingService(db)

    # 获取话题统计
    topics = await service.get_topic_stats_for_grade(grade)

    # 获取每个话题的讲义内容
    content = []
    for topic_info in topics:
        topic_content = await service.get_topic_handout_content(
            grade,
            topic_info["topic"],
            edition
        )
        content.append(WritingHandoutDetailResponse(
            topic=topic_content["topic"],
            grade=topic_content["grade"],
            edition=topic_content["edition"],
            part1_topic_stats=topic_content["part1_topic_stats"],
            part2_frameworks=topic_content["part2_frameworks"],
            part3_expressions=topic_content["part3_expressions"],
            part4_samples=topic_content["part4_samples"]
        ))

    return WritingGradeHandoutResponse(
        grade=grade,
        edition=edition,
        topics=topics,
        content=content
    )


# ==============================================================================
#                              详情查询
# ==============================================================================

@router.get("/{task_id}", response_model=WritingTaskDetailResponse)
async def get_writing_detail(
    task_id: int,
    db: AsyncSession = Depends(get_db)
):
    """获取作文详情（含模板和范文）"""
    service = WritingService(db)
    task = await service.get_writing_detail(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="作文不存在")

    # 构建响应
    source = None
    if task.paper:
        source = {
            "year": task.paper.year,
            "region": task.paper.region,
            "school": task.paper.school,
            "grade": task.paper.grade,
            "exam_type": task.paper.exam_type,
            "semester": task.paper.semester,
            "filename": task.paper.filename,
        }

    # 获取模板（如果有）
    templates = []
    if task.writing_type:
        try:
            template = await service.get_or_create_template(
                task.writing_type,
                task.application_type
            )
            templates.append(TemplateResponse(
                id=template.id,
                writing_type=template.writing_type,
                application_type=template.application_type,
                template_name=template.template_name,
                template_content=template.template_content,
                tips=template.tips,
                structure=template.structure,
                created_at=template.created_at,
            ))
        except Exception as e:
            # 模板获取失败不影响主流程
            pass

    # 获取范文
    samples = [
        SampleResponse(
            id=s.id,
            task_id=s.task_id,
            template_id=s.template_id,
            sample_content=s.sample_content,
            sample_type=s.sample_type,
            score_level=s.score_level,
            word_count=s.word_count,
            translation=s.translation,
            created_at=s.created_at,
        )
        for s in (task.samples or [])
    ]

    return WritingTaskDetailResponse(
        id=task.id,
        paper_id=task.paper_id,
        task_content=task.task_content,
        requirements=task.requirements,
        word_limit=task.word_limit,
        points_value=task.points_value,
        grade=task.grade,
        semester=task.semester,
        exam_type=task.exam_type,
        writing_type=task.writing_type,
        application_type=task.application_type,
        primary_topic=task.primary_topic,
        topic_verified=task.topic_verified,
        source=source,
        created_at=task.created_at,
        templates=templates,
        samples=samples,
    )


# ==============================================================================
#                              文体识别
# ==============================================================================

@router.post("/{task_id}/detect-type", response_model=WritingTypeDetectResponse)
async def detect_writing_type(
    task_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    智能文体识别

    使用规则 + AI 混合方式判断文体类型
    """
    service = WritingService(db)

    try:
        result = await service.detect_and_update_writing_type(task_id)
        return WritingTypeDetectResponse(
            task_id=result["task_id"],
            writing_type=result["writing_type"],
            application_type=result["application_type"],
            confidence=result["confidence"],
            reasoning=result["reasoning"],
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文体识别失败: {str(e)}")


# ==============================================================================
#                              范文生成
# ==============================================================================

class SampleGenerateRequest(BaseModel):
    """范文生成请求"""
    template_id: Optional[int] = None
    score_level: str = "一档"  # 一档/二档/三档


@router.post("/{task_id}/generate-sample", response_model=SampleResponse)
async def generate_sample(
    task_id: int,
    request: SampleGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    生成单篇范文

    Args:
        task_id: 作文 ID
        request: 包含 template_id 和 score_level
    """
    service = WritingService(db)

    try:
        sample = await service.generate_sample(
            task_id=task_id,
            template_id=request.template_id,
            score_level=request.score_level,
        )
        return SampleResponse(
            id=sample.id,
            task_id=sample.task_id,
            template_id=sample.template_id,
            sample_content=sample.sample_content,
            sample_type=sample.sample_type,
            score_level=sample.score_level,
            word_count=sample.word_count,
            translation=sample.translation,
            created_at=sample.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"范文生成失败: {str(e)}")


class BatchGenerateRequest(BaseModel):
    """批量生成请求"""
    task_ids: List[int]
    score_level: str = "一档"


@router.post("/batch-generate", response_model=BatchGenerateResponse)
async def batch_generate_samples(
    request: BatchGenerateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    批量生成范文（串行处理）

    限制：最多 100 条
    """
    if len(request.task_ids) > 100:
        raise HTTPException(status_code=400, detail="批量生成最多支持 100 条")

    if len(request.task_ids) == 0:
        raise HTTPException(status_code=400, detail="请选择至少一条作文")

    service = WritingService(db)

    try:
        result = await service.batch_generate_samples(
            task_ids=request.task_ids,
            score_level=request.score_level,
        )
        return BatchGenerateResponse(
            success_count=result["success_count"],
            fail_count=result["fail_count"],
            results=result["results"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量生成失败: {str(e)}")


# ==============================================================================
#                              范文删除
# ==============================================================================

@router.delete("/{task_id}/samples/{sample_id}")
async def delete_sample(
    task_id: int,
    sample_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    删除单个范文

    Args:
        task_id: 作文 ID
        sample_id: 范文 ID
    """
    result = await db.execute(
        select(WritingSample).where(
            WritingSample.id == sample_id,
            WritingSample.task_id == task_id
        )
    )
    sample = result.scalar_one_or_none()

    if not sample:
        raise HTTPException(status_code=404, detail="范文不存在")

    await db.delete(sample)
    await db.commit()
    return {"message": "范文删除成功"}


# ==============================================================================
#                              删除
# ==============================================================================

@router.delete("/{task_id}")
async def delete_writing(
    task_id: int,
    db: AsyncSession = Depends(get_db)
):
    """删除作文"""
    from sqlalchemy import delete

    result = await db.execute(
        delete(WritingTask).where(WritingTask.id == task_id)
    )

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="作文不存在")

    await db.commit()
    return {"message": "删除成功"}


# ==============================================================================
#                              批量删除
# ==============================================================================

class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    task_ids: List[int]


@router.post("/batch-delete")
async def batch_delete_writings(
    request: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db)
):
    """批量删除作文"""
    from sqlalchemy import delete

    if len(request.task_ids) == 0:
        raise HTTPException(status_code=400, detail="请选择至少一条作文")

    result = await db.execute(
        delete(WritingTask).where(WritingTask.id.in_(request.task_ids))
    )

    await db.commit()
    return {"message": f"成功删除 {result.rowcount} 条作文"}
