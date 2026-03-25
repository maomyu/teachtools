from pathlib import Path

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.services.pdf_generator import PDFGenerator


def _create_multi_page_pdf(pdf_path: Path) -> None:
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    for page_number in range(1, 4):
        c.drawString(72, 800, f"PAGE {page_number} START")
        c.drawString(72, 780, f"Unique content for page {page_number}")
        c.showPage()
    c.save()


def test_add_watermark_preserves_each_page_content(tmp_path: Path) -> None:
    source_pdf = tmp_path / "source.pdf"
    output_pdf = tmp_path / "watermarked.pdf"
    _create_multi_page_pdf(source_pdf)

    PDFGenerator.add_watermark(
        str(source_pdf),
        watermark_text="WM",
        output_path=str(output_pdf),
        density="sparse",
        size="small",
    )

    reader = PdfReader(str(output_pdf))
    assert len(reader.pages) == 3

    page_texts = [page.extract_text() or "" for page in reader.pages]

    for page_number, text in enumerate(page_texts, start=1):
        assert f"PAGE {page_number} START" in text
        assert f"Unique content for page {page_number}" in text

    assert "PAGE 1 START" not in page_texts[1]
    assert "PAGE 1 START" not in page_texts[2]
