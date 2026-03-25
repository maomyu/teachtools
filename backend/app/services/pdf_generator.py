"""
PDF 生成服务

使用 LibreOffice 将 DOCX 转换为 PDF，并添加水印
"""
import subprocess
import io
import os
from pathlib import Path
from typing import Optional

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


class PDFGenerator:
    """PDF 生成服务"""

    @staticmethod
    async def convert_docx_to_pdf(docx_path: str, output_dir: Optional[str] = None) -> str:
        """
        使用 LibreOffice 将 DOCX 转换为 PDF

        Args:
            docx_path: DOCX 文件路径
            output_dir: 输出目录（可选，默认与源文件同目录）

        Returns:
            PDF 文件路径
        """
        if output_dir is None:
            output_dir = str(Path(docx_path).parent)

        # LibreOffice 无头模式转换
        # 尝试多个可能的命令名称
        libreoffice_cmds = ['libreoffice', 'soffice']
        last_error = None

        for cmd_name in libreoffice_cmds:
            cmd = [
                cmd_name,
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', output_dir,
                docx_path
            ]

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120  # 2分钟超时
                )

                if result.returncode == 0:
                    break  # 成功，退出循环
                else:
                    last_error = RuntimeError(f"PDF 转换失败 ({cmd_name}): {result.stderr}")

            except FileNotFoundError:
                last_error = FileNotFoundError(f"命令 {cmd_name} 未找到")
                continue  # 尝试下一个命令
            except subprocess.TimeoutExpired:
                raise RuntimeError("PDF 转换超时")
        else:
            # 所有命令都失败了
            if isinstance(last_error, FileNotFoundError):
                raise RuntimeError(
                    "LibreOffice 未安装。请安装: \n"
                    "macOS: brew install libreoffice\n"
                    "Ubuntu: apt-get install libreoffice-writer"
                )
            else:
                raise last_error

        # 返回 PDF 路径
        pdf_path = docx_path.replace('.docx', '.pdf')
        if not os.path.exists(pdf_path):
            raise RuntimeError(f"PDF 文件未生成: {pdf_path}")

        return pdf_path

    @staticmethod
    def add_watermark(
        pdf_path: str,
        watermark_text: str = "学生版",
        output_path: Optional[str] = None,
        density: str = "medium",
        size: str = "medium"
    ) -> str:
        """
        添加水印到 PDF（水印在底层，不遮挡文字）

        Args:
            pdf_path: 原 PDF 路径
            watermark_text: 水印文字
            output_path: 输出路径（可选）
            density: 水印密度 (sparse/medium/dense)
            size: 水印大小 (small/medium/large)

        Returns:
            带水印的 PDF 路径
        """
        if output_path is None:
            output_path = pdf_path.replace('.pdf', '_watermarked.pdf')

        # 创建水印 PDF
        watermark_pdf_path = PDFGenerator._create_watermark_pdf(watermark_text, density, size)

        try:
            # 合并水印到原 PDF（水印在底层）
            reader = PdfReader(pdf_path)
            watermark_reader = PdfReader(watermark_pdf_path)
            writer = PdfWriter()

            watermark_page = watermark_reader.pages[0]

            for page in reader.pages:
                # pypdf 会原地修改 self；如果直接复用同一个模板页，容易让所有输出页
                # 指向同一份内容。这里先把原页面加入 writer，再仅修改该页。
                writer.add_page(page)
                writer.pages[-1].merge_page(watermark_page, over=False)

            # 保存
            with open(output_path, 'wb') as f:
                writer.write(f)

            print(f"[PDFGenerator] 水印已添加（底层）: {output_path}")
            return output_path

        finally:
            # 清理临时水印文件
            if os.path.exists(watermark_pdf_path):
                os.remove(watermark_pdf_path)

    @staticmethod
    def _create_watermark_pdf(
        text: str,
        density: str = "medium",
        size: str = "medium"
    ) -> str:
        """
        创建水印 PDF 模板

        Args:
            text: 水印文字
            density: 水印密度 (sparse/medium/dense)
            size: 水印大小 (small/medium/large)

        Returns:
            水印 PDF 文件路径
        """
        # 密度配置：控制水印的间距和数量
        density_config = {
            'sparse': {'x_count': 3, 'y_count': 4, 'x_step': 250, 'y_step': 180},
            'medium': {'x_count': 5, 'y_count': 6, 'x_step': 180, 'y_step': 130},
            'dense': {'x_count': 7, 'y_count': 9, 'x_step': 120, 'y_step': 90},
        }

        # 大小配置：控制水印字体大小
        size_config = {
            'small': 30,
            'medium': 40,
            'large': 55,
        }

        config = density_config.get(density, density_config['medium'])
        font_size = size_config.get(size, size_config['medium'])

        watermark_path = '/tmp/handout_watermark.pdf'

        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=A4)

        width, height = A4

        # 尝试注册中文字体
        font_name = 'Helvetica'

        # 尝试多种中文字体路径
        chinese_fonts = [
            # macOS
            ('/System/Library/Fonts/STHeiti Light.ttc', 'STHeiti', 0),
            ('/System/Library/Fonts/PingFang.ttc', 'PingFang', 0),
            ('/Library/Fonts/Arial Unicode.ttf', 'ArialUnicode', None),
            # Linux
            ('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', 'WQY', None),
            ('/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf', 'Droid', None),
        ]

        for font_path, name, subfont_idx in chinese_fonts:
            try:
                if os.path.exists(font_path):
                    if subfont_idx is not None:
                        pdfmetrics.registerFont(TTFont(name, font_path, subfontIndex=subfont_idx))
                    else:
                        pdfmetrics.registerFont(TTFont(name, font_path))
                    font_name = name
                    print(f"[PDFGenerator] 使用字体: {name} ({font_path})")
                    break
            except Exception as e:
                print(f"[PDFGenerator] 字体 {font_path} 加载失败: {e}")
                continue

        c.setFont(font_name, font_size)

        # 设置水印样式 - 浅灰色
        c.setFillColorRGB(0.8, 0.8, 0.8)

        # 旋转并居中绘制
        c.translate(width / 2, height / 2)
        c.rotate(45)

        # 根据配置绘制水印
        x_count = config['x_count']
        y_count = config['y_count']
        x_step = config['x_step']
        y_step = config['y_step']

        x_start = -(x_count // 2)
        x_end = x_count // 2 + 1
        y_start = -(y_count // 2)
        y_end = y_count // 2 + 1

        for i in range(x_start, x_end):
            for j in range(y_start, y_end):
                c.drawString(i * x_step, j * y_step, text)

        c.save()

        # 移动到开头
        packet.seek(0)

        # 保存水印 PDF
        with open(watermark_path, 'wb') as f:
            f.write(packet.read())

        print(f"[PDFGenerator] 水印 PDF 已创建 (密度={density}, 大小={size}): {watermark_path}")
        return watermark_path

    @staticmethod
    def check_libreoffice() -> bool:
        """检查 LibreOffice 是否可用"""
        try:
            result = subprocess.run(
                ['libreoffice', '--version'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            try:
                result = subprocess.run(
                    ['soffice', '--version'],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            except FileNotFoundError:
                return False
