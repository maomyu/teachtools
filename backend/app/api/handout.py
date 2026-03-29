"""
讲义转换 API 路由

[INPUT]: 依赖 HandoutConverter 服务
[OUTPUT]: 对外提供讲义转换 API
[POS]: backend/app/api 的讲义转换路由
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import os
import uuid
import asyncio
import json
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, FileResponse

from app.config import settings
from app.services.handout_converter import HandoutConverter
from app.schemas.handout import UploadResponse, ProcessStatus

router = APIRouter()

# 任务状态存储（生产环境应使用 Redis）
task_status: dict = {}


@router.get("/watermark-image")
async def get_handout_watermark_image():
    """获取讲义图片水印预览。"""
    converter = HandoutConverter()
    image_path = converter.watermark_image_path

    if not image_path.exists():
        raise HTTPException(status_code=404, detail="水印图片不存在")

    return FileResponse(
        image_path,
        media_type="image/png",
        filename=image_path.name,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_handout(file: UploadFile = File(...)):
    """
    上传教师版讲义

    - 接受 .docx 文件
    - 返回 task_id 用于后续处理
    """
    # 验证文件类型
    if not file.filename or not file.filename.endswith('.docx'):
        raise HTTPException(status_code=400, detail="只支持 .docx 文件")

    # 生成任务 ID
    task_id = str(uuid.uuid4())

    # 保存文件
    temp_dir = Path(settings.BASE_DIR) / 'data' / 'temp' / 'handout'
    temp_dir.mkdir(parents=True, exist_ok=True)

    file_path = temp_dir / f"{task_id}_{file.filename}"

    content = await file.read()
    with open(file_path, 'wb') as f:
        f.write(content)

    # 初始化状态
    task_status[task_id] = {
        "status": "uploaded",
        "file_path": str(file_path),
        "filename": file.filename,
        "progress": 0,
        "message": "文件上传成功"
    }

    return UploadResponse(
        task_id=task_id,
        filename=file.filename,
        file_size=len(content)
    )


@router.get("/process")
async def process_handout(
    task_id: str,
    watermark_text: str = "学生版",
    watermark_density: str = "sparse",
    watermark_size: str = "medium"
):
    """
    处理讲义（SSE 流式返回进度）

    Args:
        task_id: 任务 ID
        watermark_text: 兼容旧调用保留的文字参数，图片水印启用时会被忽略
        watermark_density: 水印密度 (sparse/medium/dense)
        watermark_size: 水印大小 (small/medium/large)

    事件流格式：
    event: progress
    data: {"progress": 20, "message": "正在处理..."}

    event: completed
    data: {"download_url": "/api/handout/download/xxx"}
    """
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="任务不存在")

    async def event_stream():
        converter = HandoutConverter()
        progress_queue = asyncio.Queue()

        async def progress_callback(progress: int, message: str):
            await progress_queue.put({"progress": progress, "message": message})
            task_status[task_id]["progress"] = progress
            task_status[task_id]["message"] = message

        # 启动处理任务
        process_task = asyncio.create_task(
            converter.convert_with_details(
                task_status[task_id]["file_path"],
                watermark_text,
                progress_callback,
                watermark_density,
                watermark_size
            )
        )

        # 发送进度事件
        while not process_task.done():
            try:
                update = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                yield f"event: progress\ndata: {json.dumps(update, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                continue

        # 检查结果
        try:
            result = process_task.result()
            task_status[task_id]["pdf_path"] = result['pdf_path']
            task_status[task_id]["status"] = "completed"
            task_status[task_id]["answers_removed"] = result['answers_removed']

            yield f"event: completed\ndata: {json.dumps({'download_url': f'/api/handout/download/{task_id}', 'answers_removed': result['answers_removed']}, ensure_ascii=False)}\n\n"

        except Exception as e:
            task_status[task_id]["status"] = "failed"
            task_status[task_id]["error"] = str(e)
            yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/download/{task_id}")
async def download_handout(task_id: str):
    """下载生成的学生版 PDF"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task_status[task_id].get("status") != "completed":
        raise HTTPException(status_code=400, detail="任务未完成")

    pdf_path = task_status[task_id].get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF 文件不存在")

    filename = task_status[task_id]["filename"].replace('.docx', '_学生版.pdf')

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename
    )


@router.get("/status/{task_id}", response_model=ProcessStatus)
async def get_process_status(task_id: str):
    """查询处理状态"""
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="任务不存在")

    status = task_status[task_id]

    return ProcessStatus(
        task_id=task_id,
        status=status.get("status", "unknown"),
        progress=status.get("progress", 0),
        message=status.get("message", ""),
        download_url=f"/api/handout/download/{task_id}" if status.get("status") == "completed" else None,
        error=status.get("error")
    )
