"""
讲义转换主服务

简化方案：找到"参考答案"关键词，删除之后的所有内容
"""
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional, Callable, Awaitable

from app.config import settings
from app.services.docx_processor import DocxProcessor
from app.services.pdf_generator import PDFGenerator


class HandoutConverter:
    """讲义转换主服务 - 简化版"""

    def __init__(self):
        self.docx_processor = DocxProcessor()
        self.pdf_generator = PDFGenerator()
        self.local_watermark_dir = settings.BASE_DIR / 'data' / 'local' / 'watermarks'
        self.local_watermark_dir.mkdir(parents=True, exist_ok=True)
        self.watermark_image_path = self.local_watermark_dir / 'handout_watermark.png'
        self._ensure_local_watermark_image()

        # 临时文件目录
        self.temp_dir = Path(settings.BASE_DIR) / 'data' / 'temp' / 'handout'
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _ensure_local_watermark_image(self) -> None:
        """确保图片水印存在于本地目录。"""
        if self.watermark_image_path.exists():
            return

        fallback_paths = [
            settings.BASE_DIR / 'static' / 'watermarks' / 'handout_watermark.png',
            PDFGenerator.DEFAULT_WATERMARK_IMAGE,
        ]

        for fallback_path in fallback_paths:
            if fallback_path.exists():
                shutil.copy2(fallback_path, self.watermark_image_path)
                print(f"[HandoutConverter] 已复制本地水印图片: {self.watermark_image_path}")
                return

    async def convert(
        self,
        file_path: str,
        watermark_text: str = "学生版",
        progress_callback: Optional[Callable[[int, str], Awaitable[None]]] = None
    ) -> str:
        """
        完整的转换流程

        Args:
            file_path: 原始 DOCX 文件路径
            watermark_text: 兼容旧调用保留的文字参数，图片水印可用时会被忽略
            progress_callback: 进度回调函数 (progress: int, message: str)

        Returns:
            最终 PDF 文件路径
        """
        result = await self.convert_with_details(file_path, watermark_text, progress_callback)
        return result['pdf_path']

    async def convert_with_details(
        self,
        file_path: str,
        watermark_text: str = "学生版",
        progress_callback: Optional[Callable[[int, str], Awaitable[None]]] = None,
        watermark_density: str = "medium",
        watermark_size: str = "medium"
    ) -> dict:
        """
        转换并返回详细信息

        简化流程（不需要 AI）：
        1. 找到"参考答案"关键词
        2. 删除从该位置开始的所有后续内容
        3. 转 PDF + 水印

        Args:
            file_path: 原文件路径
            watermark_text: 兼容旧调用保留的文字参数，图片水印可用时会被忽略
            progress_callback: 进度回调
            watermark_density: 水印密度 (sparse/medium/dense)
            watermark_size: 水印大小 (small/medium/large)

        Returns:
            {
                'pdf_path': str,
                'answers_removed': int,
                'original_file': str,
                'keyword_found': str
            }
        """
        task_id = str(uuid.uuid4())[:8]
        print(f"[HandoutConverter] 开始处理任务 {task_id}: {file_path}")

        # 1. 删除参考答案部分 (30%)
        if progress_callback:
            await progress_callback(10, "正在分析文档...")
            await progress_callback(20, "正在查找答案部分...")

        student_docx_path = str(self.temp_dir / f"{task_id}_student.docx")
        print(f"[HandoutConverter] 开始删除答案部分...")

        result = self.docx_processor.remove_answers_section(
            file_path,
            student_docx_path
        )

        if progress_callback:
            if result['keyword_found']:
                await progress_callback(30, f"找到 '{result['keyword_found']}'，正在删除答案...")
            else:
                await progress_callback(30, "未找到答案标记，保留全部内容")

        print(f"[HandoutConverter] 删除结果: {result}")

        # 2. 转换为 PDF (70%)
        if progress_callback:
            await progress_callback(50, "正在转换为 PDF...")
            await progress_callback(70, "正在生成 PDF 文件...")

        print("[HandoutConverter] 开始转换为 PDF...")
        try:
            pdf_path = await self.pdf_generator.convert_docx_to_pdf(
                student_docx_path,
                str(self.temp_dir)
            )
            print(f"[HandoutConverter] PDF 已生成: {pdf_path}")
        except Exception as e:
            print(f"[HandoutConverter] PDF 转换失败: {e}")
            raise Exception(f"PDF 转换失败: {str(e)}")

        # 3. 添加水印 (90%)
        if progress_callback:
            await progress_callback(85, "正在添加水印...")

        print(
            "[HandoutConverter] 添加图片水印 "
            f"(密度={watermark_density}, 大小={watermark_size}, 图片={self.watermark_image_path})..."
        )
        final_pdf = self.pdf_generator.add_watermark(
            pdf_path,
            watermark_text,
            str(self.temp_dir / f"{task_id}_final.pdf"),
            watermark_density,
            watermark_size,
            str(self.watermark_image_path),
        )
        print(f"[HandoutConverter] 最终 PDF: {final_pdf}")

        # 4. 完成 (100%)
        if progress_callback:
            await progress_callback(100, "处理完成！")

        return {
            'pdf_path': final_pdf,
            'answers_removed': result['removed_count'],
            'original_file': os.path.basename(file_path),
            'keyword_found': result.get('keyword_found'),
            'answer_section_start': result.get('answer_section_start')
        }

    def cleanup_temp_files(self, task_id: str):
        """清理指定任务的临时文件"""
        patterns = [
            f"{task_id}_student.docx",
            f"{task_id}_student.pdf",
            f"{task_id}_final.pdf"
        ]

        for pattern in patterns:
            file_path = self.temp_dir / pattern
            if file_path.exists():
                os.remove(file_path)
                print(f"[HandoutConverter] 清理临时文件: {file_path}")
