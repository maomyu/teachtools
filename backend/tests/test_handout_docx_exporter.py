import base64
import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from docx import Document

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.handout_docx_exporter import HandoutDocxExporter


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z0uoAAAAASUVORK5CYII="
)


def test_build_reading_grade_docx_embeds_option_images(tmp_path: Path) -> None:
    static_root = tmp_path / "static"
    image_dir = static_root / "images" / "options"
    image_dir.mkdir(parents=True, exist_ok=True)
    image_path = image_dir / "test_option.png"
    image_path.write_bytes(PNG_1X1)

    exporter = HandoutDocxExporter(static_root=static_root)
    handout = {
        "grade": "初二",
        "edition": "teacher",
        "topics": [{"topic": "太空探索", "passage_count": 1, "recent_years": [2026]}],
        "content": [
            {
                "topic": "太空探索",
                "part1_article_sources": [],
                "part2_vocabulary": [],
                "part3_passages": [
                    {
                        "type": "C",
                        "title": "Black Holes",
                        "source": {"year": 2026, "region": "北京", "grade": "初二", "exam_type": "期中"},
                        "content": "A short reading passage.",
                        "questions": [
                            {
                                "number": 39,
                                "text": "Choose the best answer.",
                                "options": {
                                    "A": "Plain text option",
                                    "B": "Option with image\n[IMAGE:/static/images/options/test_option.png]",
                                },
                                "correct_answer": "B",
                                "explanation": "Because it matches the passage.",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    file_bytes = exporter.build_reading_grade_docx(handout)

    with ZipFile(BytesIO(file_bytes)) as archive:
        media_files = [name for name in archive.namelist() if name.startswith("word/media/")]
        assert media_files, "导出的 docx 应包含嵌入图片"

    document = Document(BytesIO(file_bytes))
    full_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Option with image" in full_text
    assert "[IMAGE:" not in full_text
