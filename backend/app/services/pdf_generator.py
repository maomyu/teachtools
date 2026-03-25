"""
PDF 生成服务

使用 LibreOffice 将 DOCX 转换为 PDF，并添加水印
"""
import subprocess
import io
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

RESAMPLING_LANCZOS = getattr(getattr(Image, "Resampling", Image), "LANCZOS")


class PDFGenerator:
    """PDF 生成服务"""

    DEFAULT_WATERMARK_IMAGE = Path(__file__).resolve().parents[2] / "data" / "local" / "watermarks" / "handout_watermark.png"
    LEGACY_WATERMARK_IMAGE = Path(__file__).resolve().parents[2] / "static" / "watermarks" / "handout_watermark.png"

    @staticmethod
    def _get_libreoffice_executable() -> str:
        """返回可用的 LibreOffice 可执行文件路径。"""
        candidates = []

        for cmd_name in ("libreoffice", "soffice"):
            resolved = shutil.which(cmd_name)
            if resolved:
                candidates.append(resolved)

        caskroom_root = Path("/opt/homebrew/Caskroom/libreoffice")
        if caskroom_root.exists():
            for app_path in sorted(caskroom_root.glob("*/LibreOffice.app/Contents/MacOS/soffice"), reverse=True):
                candidates.append(str(app_path))

        candidates.extend([
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            "/Applications/LibreOffice.app/Contents/MacOS/soffice.bin",
        ])

        checked = []
        for candidate in candidates:
            if candidate in checked:
                continue
            checked.append(candidate)

            if not os.path.exists(candidate):
                continue

            try:
                result = subprocess.run(
                    [candidate, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return candidate
            except Exception:
                continue

        raise RuntimeError(
            "LibreOffice 未正确安装或命令链接已损坏。"
            " 当前检测到的 soffice 包装脚本不可用，请重新安装或重新链接 LibreOffice。"
        )

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

        libreoffice_exec = PDFGenerator._get_libreoffice_executable()
        cmd = [
            libreoffice_exec,
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
        except subprocess.TimeoutExpired:
            raise RuntimeError("PDF 转换超时")

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            detail = stderr or stdout or "未知错误"
            raise RuntimeError(f"PDF 转换失败 ({libreoffice_exec}): {detail}")

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
        size: str = "medium",
        watermark_image_path: Optional[str] = None,
    ) -> str:
        """
        添加水印到 PDF（水印在底层，不遮挡文字）

        Args:
            pdf_path: 原 PDF 路径
            watermark_text: 兼容旧调用保留的文字参数，图片水印可用时会被忽略
            output_path: 输出路径（可选）
            density: 水印密度 (sparse/medium/dense)
            size: 水印大小 (small/medium/large)
            watermark_image_path: 水印图片路径（可选，默认使用内置图片）

        Returns:
            带水印的 PDF 路径
        """
        if output_path is None:
            output_path = pdf_path.replace('.pdf', '_watermarked.pdf')

        # 创建水印 PDF
        watermark_pdf_path = PDFGenerator._create_watermark_pdf(
            watermark_text,
            density,
            size,
            watermark_image_path,
        )

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
        size: str = "medium",
        watermark_image_path: Optional[str] = None,
    ) -> str:
        """创建水印 PDF 模板，优先使用图片水印。"""
        image_path = PDFGenerator._resolve_watermark_image_path(watermark_image_path)
        if image_path is not None:
            return PDFGenerator._create_image_watermark_pdf(image_path, density, size)

        return PDFGenerator._create_text_watermark_pdf(text, density, size)

    @staticmethod
    def _resolve_watermark_image_path(watermark_image_path: Optional[str] = None) -> Optional[Path]:
        """解析可用的图片水印路径。"""
        candidates = []
        if watermark_image_path:
            candidates.append(Path(watermark_image_path))
        candidates.append(PDFGenerator.DEFAULT_WATERMARK_IMAGE)
        candidates.append(PDFGenerator.LEGACY_WATERMARK_IMAGE)

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None

    @staticmethod
    def _create_temp_watermark_path() -> str:
        """创建临时水印文件路径。"""
        fd, watermark_path = tempfile.mkstemp(prefix="handout_watermark_", suffix=".pdf")
        os.close(fd)
        return watermark_path

    @staticmethod
    def _create_image_watermark_pdf(
        image_path: Path,
        density: str = "medium",
        size: str = "medium",
    ) -> str:
        """
        创建图片水印 PDF 模板。

        这里会裁掉原图透明边缘，并整体降低透明度，避免深色 Logo 压住正文。
        """
        density_config = {
            'sparse': {'x_count': 2, 'y_count': 4, 'x_gap': 120, 'y_gap': 120},
            'medium': {'x_count': 3, 'y_count': 5, 'x_gap': 80, 'y_gap': 92},
            'dense': {'x_count': 4, 'y_count': 6, 'x_gap': 55, 'y_gap': 74},
        }

        size_config = {
            'small': 170,
            'medium': 220,
            'large': 270,
        }

        config = density_config.get(density, density_config['medium'])
        image_width = size_config.get(size, size_config['medium'])
        opacity = 0.11
        watermark_path = PDFGenerator._create_temp_watermark_path()

        with Image.open(image_path) as source:
            processed = source.convert("RGBA")
            alpha_bbox = processed.getchannel("A").getbbox()
            if alpha_bbox:
                processed = processed.crop(alpha_bbox)

            if processed.width > 900:
                scale = 900 / processed.width
                processed = processed.resize(
                    (int(processed.width * scale), int(processed.height * scale)),
                    RESAMPLING_LANCZOS,
                )

            red, green, blue, alpha = processed.split()
            alpha = alpha.point(lambda value: int(value * opacity))
            processed = Image.merge("RGBA", (red, green, blue, alpha))
            watermark_image = ImageReader(processed)

            packet = io.BytesIO()
            c = canvas.Canvas(packet, pagesize=A4)
            width, height = A4

            image_height = image_width * (processed.height / processed.width)
            x_step = image_width + config['x_gap']
            y_step = image_height + config['y_gap']

            c.saveState()
            c.translate(width / 2, height / 2)
            c.rotate(28)

            x_offset = (config['x_count'] - 1) / 2
            y_offset = (config['y_count'] - 1) / 2

            for i in range(config['x_count']):
                for j in range(config['y_count']):
                    x = (i - x_offset) * x_step - image_width / 2
                    y = (j - y_offset) * y_step - image_height / 2
                    c.drawImage(
                        watermark_image,
                        x,
                        y,
                        width=image_width,
                        height=image_height,
                        mask='auto',
                    )

            c.restoreState()
            c.save()

            packet.seek(0)
            with open(watermark_path, 'wb') as f:
                f.write(packet.read())

        print(
            "[PDFGenerator] 图片水印 PDF 已创建 "
            f"(图片={image_path.name}, 密度={density}, 大小={size}): {watermark_path}"
        )
        return watermark_path

    @staticmethod
    def _create_text_watermark_pdf(
        text: str,
        density: str = "medium",
        size: str = "medium",
    ) -> str:
        """
        创建文字水印 PDF 模板。

        仅作为图片资源缺失时的兜底方案保留。

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

        watermark_path = PDFGenerator._create_temp_watermark_path()

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
            exec_path = PDFGenerator._get_libreoffice_executable()
            result = subprocess.run(
                [exec_path, '--version'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False
