"""
作文模块 API

[INPUT]: 依赖 FastAPI、SQLAlchemy、作文模型和服务
[OUTPUT]: 对外提供作文查询、分类、范文生成与讲义接口
[POS]: backend/app/api 的作文路由
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from io import BytesIO
from typing import List, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.writing import WritingCategory, WritingSample, WritingTask
from app.schemas.writing import (
    BatchGenerateResponse,
    SampleResponse,
    SourceInfo,
    TemplateResponse,
    WritingTemplateListItem,
    WritingTemplateListResponse,
    WritingTemplatePaperDetailResponse,
    WritingTemplatePaperItem,
    WritingTemplatePaperListResponse,
    WritingCategoryResponse,
    WritingFiltersResponse,
    WritingGradeHandoutResponse,
    WritingTaskDetailResponse,
    WritingTaskListResponse,
    WritingTaskResponse,
    WritingTypeDetectResponse,
)
from app.services.handout_docx_exporter import HandoutDocxExporter
from app.services.writing_service import WritingService


router = APIRouter()


def _to_category_response(category: Optional[WritingCategory]) -> Optional[WritingCategoryResponse]:
    if not category:
        return None
    return WritingCategoryResponse(
        id=category.id,
        code=category.code,
        name=category.name,
        level=category.level,
        parent_id=category.parent_id,
        path=category.path,
        template_key=category.template_key,
    )


def _to_source_info(task: WritingTask) -> Optional[SourceInfo]:
    if not task.paper:
        return None
    return SourceInfo(
        year=task.paper.year,
        region=task.paper.region,
        school=task.paper.school,
        grade=task.paper.grade,
        exam_type=task.paper.exam_type,
        semester=task.paper.semester,
        filename=task.paper.filename,
    )


def _to_task_response(task: WritingTask) -> WritingTaskResponse:
    return WritingTaskResponse(
        id=task.id,
        paper_id=task.paper_id,
        task_content=task.task_content,
        requirements=task.requirements,
        word_limit=task.word_limit,
        points_value=task.points_value,
        grade=task.grade,
        semester=task.semester,
        exam_type=task.exam_type,
        group_category=_to_category_response(task.group_category),
        major_category=_to_category_response(task.major_category),
        category=_to_category_response(task.category),
        category_confidence=task.category_confidence or 0.0,
        category_reasoning=task.category_reasoning,
        source=_to_source_info(task),
        created_at=task.created_at,
    )


def _to_template_response(template) -> TemplateResponse:
    return TemplateResponse(
        id=template.id,
        category=_to_category_response(template.category),
        template_name=template.template_name,
        template_content=template.template_content,
        tips=template.tips,
        structure=template.structure,
        template_schema_json=template.template_schema_json,
        template_version=template.template_version or 1,
        quality_status=template.quality_status or "pending",
        representative_sample_content=template.representative_sample_content,
        representative_translation=template.representative_translation,
        representative_rendered_slots_json=template.representative_rendered_slots_json,
        representative_word_count=template.representative_word_count,
        opening_sentences=template.opening_sentences,
        closing_sentences=template.closing_sentences,
        transition_words=template.transition_words,
        advanced_vocabulary=template.advanced_vocabulary,
        grammar_points=template.grammar_points,
        scoring_criteria=template.scoring_criteria,
        created_at=template.created_at,
    )


def _to_sample_response(
    sample: WritingSample,
    *,
    quality_status: Optional[str] = None,
) -> SampleResponse:
    return SampleResponse(
        id=sample.id,
        task_id=sample.task_id,
        template_id=sample.template_id,
        sample_content=sample.sample_content,
        sample_type=sample.sample_type,
        score_level=sample.score_level,
        word_count=sample.word_count,
        translation=sample.translation,
        rendered_slots_json=sample.rendered_slots_json,
        template_version=sample.template_version or 1,
        generation_mode=sample.generation_mode or "slot_fill",
        quality_status=quality_status or sample.quality_status or "pending",
        created_at=sample.created_at,
    )


@router.get("/filters", response_model=WritingFiltersResponse)
async def get_writing_filters(db: AsyncSession = Depends(get_db)):
    """获取作文筛选项。"""
    service = WritingService(db)
    filters = await service.get_filters()
    return WritingFiltersResponse(
        grades=filters["grades"],
        semesters=filters["semesters"],
        exam_types=filters["exam_types"],
        groups=[_to_category_response(item) for item in filters["groups"]],
        major_categories=[_to_category_response(item) for item in filters["major_categories"]],
        categories=[_to_category_response(item) for item in filters["categories"]],
    )


@router.get("", response_model=WritingTaskListResponse)
async def get_writings(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    grade: Optional[str] = Query(None),
    semester: Optional[str] = Query(None),
    exam_type: Optional[str] = Query(None),
    group_category_id: Optional[int] = Query(None),
    major_category_id: Optional[int] = Query(None),
    category_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取作文列表。"""
    service = WritingService(db)
    items, total, grade_counts = await service.get_writings(
        page=page,
        size=size,
        grade=grade,
        semester=semester,
        exam_type=exam_type,
        group_category_id=group_category_id,
        major_category_id=major_category_id,
        category_id=category_id,
        search=search,
    )
    return WritingTaskListResponse(
        total=total,
        items=[_to_task_response(item) for item in items],
        grade_counts=grade_counts,
    )


@router.get("/handouts/{grade}", response_model=WritingGradeHandoutResponse)
async def get_writing_handout(
    grade: str,
    edition: str = Query("teacher", pattern="^(teacher|student)$"),
    paper_ids: Optional[List[int]] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取年级作文讲义。"""
    service = WritingService(db)
    payload = await service.build_grade_handout(grade, edition, paper_ids)
    return WritingGradeHandoutResponse(**payload)


@router.get("/templates", response_model=WritingTemplateListResponse)
async def get_writing_templates(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    grade: Optional[str] = Query(None),
    semester: Optional[str] = Query(None),
    exam_type: Optional[str] = Query(None),
    group_category_id: Optional[int] = Query(None),
    major_category_id: Optional[int] = Query(None),
    category_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """按模板维度获取作文汇编列表。"""
    service = WritingService(db)
    items, total, total_paper_count, total_task_count = await service.get_template_list(
        page=page,
        size=size,
        grade=grade,
        semester=semester,
        exam_type=exam_type,
        group_category_id=group_category_id,
        major_category_id=major_category_id,
        category_id=category_id,
        search=search,
    )
    return WritingTemplateListResponse(
        total=total,
        total_paper_count=total_paper_count,
        total_task_count=total_task_count,
        items=[
            WritingTemplateListItem(
                id=item["template"].id,
                group_category=_to_category_response(item["group_category"]),
                major_category=_to_category_response(item["major_category"]),
                category=_to_category_response(item["category"]),
                template_name=item["template"].template_name,
                template_content=item["template"].template_content,
                structure=item["template"].structure,
                template_schema_json=item["template"].template_schema_json,
                template_version=item["template"].template_version or 1,
                quality_status=item["template"].quality_status or "pending",
                representative_sample_content=item["template"].representative_sample_content,
                representative_translation=item["template"].representative_translation,
                representative_word_count=item["template"].representative_word_count,
                paper_count=item["paper_count"],
                task_count=item["task_count"],
                updated_at=item["template"].updated_at or item["template"].created_at,
            )
            for item in items
        ],
    )


@router.get("/templates/{template_id}/papers", response_model=WritingTemplatePaperListResponse)
async def get_writing_template_papers(template_id: int, db: AsyncSession = Depends(get_db)):
    """获取某个模板下的试卷列表。"""
    service = WritingService(db)
    try:
        payload = await service.get_template_papers(template_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    template = payload["template"]
    return WritingTemplatePaperListResponse(
        template=WritingTemplateListItem(
            id=template.id,
            group_category=_to_category_response(payload["group_category"]),
            major_category=_to_category_response(payload["major_category"]),
            category=_to_category_response(payload["category"]),
            template_name=template.template_name,
            template_content=template.template_content,
            structure=template.structure,
            template_schema_json=template.template_schema_json,
            template_version=template.template_version or 1,
            quality_status=template.quality_status or "pending",
            representative_sample_content=template.representative_sample_content,
            representative_translation=template.representative_translation,
            representative_word_count=template.representative_word_count,
            paper_count=len(payload["papers"]),
            task_count=sum(item["task_count"] for item in payload["papers"]),
            updated_at=template.updated_at or template.created_at,
        ),
        papers=[
            WritingTemplatePaperItem(
                paper_id=item["paper_id"],
                filename=item["filename"],
                year=item["year"],
                region=item["region"],
                school=item["school"],
                grade=item["grade"],
                exam_type=item["exam_type"],
                semester=item["semester"],
                task_count=item["task_count"],
            )
            for item in payload["papers"]
        ],
    )


@router.get("/templates/{template_id}/papers/{paper_id}", response_model=WritingTemplatePaperDetailResponse)
async def get_writing_template_paper_detail(template_id: int, paper_id: int, db: AsyncSession = Depends(get_db)):
    """获取某个模板下某张试卷的全部作文题与正式范文。"""
    service = WritingService(db)
    try:
        payload = await service.get_template_paper_detail(template_id, paper_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    tasks = []
    template_response = _to_template_response(payload["template"])
    for task in payload["tasks"]:
        display_sample = service._select_display_sample(  # noqa: SLF001
            task.samples,
            expected_template_id=payload["template"].id,
            template=payload["template"],
        )
        display_status = service._sample_display_quality_status(  # noqa: SLF001
            display_sample,
            expected_template_id=payload["template"].id,
            template=payload["template"],
        )
        tasks.append(
            WritingTaskDetailResponse(
                **_to_task_response(task).model_dump(),
                templates=[template_response],
                samples=[
                    _to_sample_response(display_sample, quality_status=display_status)
                ] if display_sample else [],
            )
        )

    return WritingTemplatePaperDetailResponse(
        template=template_response,
        paper=_to_source_info(payload["tasks"][0]),
        tasks=tasks,
    )


@router.get("/handouts/{grade}/categories")
async def get_writing_handout_categories(
    grade: str,
    paper_ids: Optional[List[int]] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取讲义子类摘要，供前端目录或筛选使用。"""
    service = WritingService(db)
    payload = await service.build_grade_handout(grade, "teacher", paper_ids)
    flat_categories = []
    for group in payload["groups"]:
        for section in group["sections"]:
            flat_categories.append(section["summary"])
    return {"grade": grade, "categories": flat_categories}


@router.get("/handouts/{grade}/export/docx")
async def export_writing_grade_handout_docx(
    grade: str,
    edition: str = Query("teacher", pattern="^(teacher|student)$"),
    paper_ids: Optional[List[int]] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """导出年级作文讲义 Word。"""
    service = WritingService(db)
    payload = await service.build_grade_handout(grade, edition, paper_ids)
    exporter = HandoutDocxExporter()
    file_bytes = exporter.build_writing_grade_docx(payload, paper_ids=paper_ids)
    filename = exporter.build_filename(f"{grade}作文讲义", edition, paper_ids)
    encoded_filename = quote(filename)
    return StreamingResponse(
        BytesIO(file_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"},
    )


@router.get("/{task_id}", response_model=WritingTaskDetailResponse)
async def get_writing_detail(task_id: int, db: AsyncSession = Depends(get_db)):
    """获取作文详情。"""
    service = WritingService(db)
    task = await service.get_writing_detail(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="作文不存在")

    latest_sample = next(iter(sorted(task.samples or [], key=lambda item: item.id or 0, reverse=True)), None)
    if task.category_id:
        template = await service.get_or_create_template(task.category_id, refresh_if_stale=False)

    templates = []
    if task.category_id:
        templates.append(_to_template_response(template))

    display_sample = None
    display_status = "pending"
    if task.category_id:
        display_sample = service._select_display_sample(  # noqa: SLF001
            task.samples,
            expected_template_id=template.id,
            template=template,
        )
        display_status = service._sample_display_quality_status(  # noqa: SLF001
            display_sample,
            expected_template_id=template.id,
            template=template,
        )
    elif latest_sample:
        display_sample = latest_sample
        display_status = latest_sample.quality_status or "pending"

    samples = [
        _to_sample_response(display_sample, quality_status=display_status)
        for _ in [1]
        if display_sample is not None
    ]

    base = _to_task_response(task)
    return WritingTaskDetailResponse(**base.model_dump(), templates=templates, samples=samples)


@router.post("/{task_id}/detect-type", response_model=WritingTypeDetectResponse)
async def detect_writing_type(task_id: int, db: AsyncSession = Depends(get_db)):
    """重新分类作文。"""
    service = WritingService(db)
    try:
        result = await service.detect_and_update_writing_type(task_id)
        return WritingTypeDetectResponse(
            task_id=result["task_id"],
            group_category=_to_category_response(result["group_category"]),
            major_category=_to_category_response(result["major_category"]),
            category=_to_category_response(result["category"]),
            confidence=result["confidence"],
            reasoning=result["reasoning"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"作文分类失败: {exc}")


class SampleGenerateRequest(BaseModel):
    """范文生成请求。"""

    template_id: Optional[int] = None
    score_level: str = "一档"


@router.post("/{task_id}/generate-sample", response_model=SampleResponse)
async def generate_sample(
    task_id: int,
    request: SampleGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """生成单篇范文。"""
    service = WritingService(db)
    try:
        sample = await service.generate_sample(
            task_id=task_id,
            template_id=request.template_id,
            score_level=request.score_level,
        )
        return SampleResponse(
            **_to_sample_response(sample).model_dump()
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"范文生成失败: {exc}")


class BatchGenerateRequest(BaseModel):
    """批量生成请求。"""

    task_ids: List[int]
    score_level: str = "一档"


@router.post("/batch-generate", response_model=BatchGenerateResponse)
async def batch_generate_samples(
    request: BatchGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """批量生成范文。"""
    if len(request.task_ids) > 100:
        raise HTTPException(status_code=400, detail="批量生成最多支持 100 条")
    if len(request.task_ids) == 0:
        raise HTTPException(status_code=400, detail="请选择至少一条作文")

    service = WritingService(db)
    result = await service.batch_generate_samples(request.task_ids, request.score_level)
    return BatchGenerateResponse(
        success_count=result["success_count"],
        fail_count=result["fail_count"],
        results=result["results"],
    )


@router.delete("/{task_id}/samples/{sample_id}")
async def delete_sample(task_id: int, sample_id: int, db: AsyncSession = Depends(get_db)):
    """删除单个范文。"""
    result = await db.execute(
        select(WritingSample).where(WritingSample.id == sample_id, WritingSample.task_id == task_id)
    )
    sample = result.scalar_one_or_none()
    if not sample:
        raise HTTPException(status_code=404, detail="范文不存在")
    await db.delete(sample)
    await db.commit()
    return {"message": "范文删除成功"}


@router.delete("/{task_id}")
async def delete_writing(task_id: int, db: AsyncSession = Depends(get_db)):
    """删除作文。"""
    result = await db.execute(delete(WritingTask).where(WritingTask.id == task_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="作文不存在")
    await db.commit()
    return {"message": "删除成功"}


class BatchDeleteRequest(BaseModel):
    """批量删除请求。"""

    task_ids: List[int]


@router.post("/batch-delete")
async def batch_delete_writings(request: BatchDeleteRequest, db: AsyncSession = Depends(get_db)):
    """批量删除作文。"""
    if len(request.task_ids) == 0:
        raise HTTPException(status_code=400, detail="请选择至少一条作文")
    result = await db.execute(delete(WritingTask).where(WritingTask.id.in_(request.task_ids)))
    await db.commit()
    return {"message": f"成功删除 {result.rowcount} 条作文"}
