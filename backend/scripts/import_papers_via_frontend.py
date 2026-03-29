#!/usr/bin/env python3
"""
批量模拟前端试卷导入脚本

能力：
1. 按前端同样的 SSE 接口批量上传 docx 试卷
2. 单文件失败自动重试，默认最多 3 次
3. 导入失败和校验失败均写入日志
4. 导入成功后校验数据库是否完整落库

默认导入目录：
    试卷库/docx-解析版

示例：
    python backend/scripts/import_papers_via_frontend.py
    python backend/scripts/import_papers_via_frontend.py --limit 10
    python backend/scripts/import_papers_via_frontend.py --base-url http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sqlite3
import sys
import time
import traceback
from functools import lru_cache
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError as exc:  # pragma: no cover - CLI import guard
    raise SystemExit(
        "缺少依赖 httpx，请先安装 backend/requirements.txt，"
        "或使用 backend/.venv/bin/python 运行此脚本。"
    ) from exc

try:
    from docx import Document
except ImportError as exc:  # pragma: no cover - CLI import guard
    raise SystemExit(
        "缺少依赖 python-docx，请先安装 backend/requirements.txt。"
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IMPORT_DIR = REPO_ROOT / "试卷库" / "docx-解析版"
DEFAULT_DB_PATH = REPO_ROOT / "backend" / "database" / "teaching.db"
DEFAULT_LOG_DIR = REPO_ROOT / "logs"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_CHECKPOINT_FILE = REPO_ROOT / "data" / "import_checkpoint.json"
UPLOAD_PATH = "/api/papers/upload-with-progress"
READING_SECTION_KEYWORDS = ("阅读理解", "阅读下列短文", "阅读短文", "阅读表达", "阅读还原")
CLOZE_SECTION_KEYWORDS = ("完形填空", "完型填空")
WRITING_SECTION_KEYWORDS = ("书面表达", "文段表达", "作文", "写作")
ANSWER_SHEET_KEYWORDS = ("参考答案", "答案及评分标准", "答案及评分参考", "英语答案")


@dataclass
class UploadAttemptResult:
    ok: bool
    error: str | None
    failed_step: dict[str, Any] | None
    final_event: dict[str, Any] | None
    result: dict[str, Any] | None
    steps: list[dict[str, Any]]
    duration_seconds: float


@dataclass
class ImportCheckpoint:
    records: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, checkpoint_path: Path) -> "ImportCheckpoint":
        if not checkpoint_path.exists():
            return cls()
        try:
            data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            records = data.get("records", {})
            if isinstance(records, dict):
                return cls(records=records)
        except Exception:
            pass
        return cls()

    def save(self, checkpoint_path: Path) -> None:
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "records": self.records,
        }
        tmp_path = checkpoint_path.with_suffix(f"{checkpoint_path.suffix}.tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(checkpoint_path)

    def should_skip(self, file_path: Path) -> bool:
        key = str(file_path.resolve())
        record = self.records.get(key)
        if not record:
            return False
        return (
            record.get("status") == "success"
            and record.get("signature") == file_signature(file_path)
        )

    def update_with_result(self, file_path: Path, result: dict[str, Any]) -> None:
        key = str(file_path.resolve())
        self.records[key] = {
            "filename": file_path.name,
            "status": result.get("final_status"),
            "signature": file_signature(file_path),
            "attempts_used": result.get("attempts_used"),
            "failure_reason": result.get("failure_reason"),
            "paper_id": result.get("paper_id"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量模拟前端导入解析版试卷")
    parser.add_argument(
        "--import-dir",
        type=Path,
        default=DEFAULT_IMPORT_DIR,
        help=f"待导入目录，默认: {DEFAULT_IMPORT_DIR}",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"SQLite 数据库路径，默认: {DEFAULT_DB_PATH}",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"后端服务地址，默认: {DEFAULT_BASE_URL}",
    )
    parser.add_argument(
        "--pattern",
        default="*.docx",
        help="导入文件匹配模式，默认: *.docx",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="限制导入数量，默认不限制",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="单文件最大尝试次数，默认: 3",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=2.0,
        help="重试前等待秒数，默认: 2",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=1800.0,
        help="单次请求总超时秒数，默认: 1800",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="并发导入的试卷数，默认: 3",
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help=f"日志目录，默认: {DEFAULT_LOG_DIR}",
    )
    parser.add_argument(
        "--no-force",
        action="store_true",
        help="关闭 force=true。默认行为与前端一致，始终强制重新导入。",
    )
    parser.add_argument(
        "--checkpoint-file",
        type=Path,
        default=DEFAULT_CHECKPOINT_FILE,
        help=f"断点续传 checkpoint 文件，默认: {DEFAULT_CHECKPOINT_FILE}",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="禁用断点续传，忽略已有 checkpoint。",
    )
    return parser.parse_args()


def discover_files(import_dir: Path, pattern: str, limit: int | None) -> list[Path]:
    if not import_dir.exists():
        raise FileNotFoundError(f"导入目录不存在: {import_dir}")

    files = sorted(
        p for p in import_dir.glob(pattern)
        if p.is_file() and p.suffix.lower() == ".docx"
    )
    if limit is not None:
        files = files[:limit]
    return files


def file_signature(file_path: Path) -> dict[str, int]:
    stat = file_path.stat()
    return {
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def ensure_backend_alive(client: httpx.Client, base_url: str) -> None:
    probe_urls = [
        f"{base_url.rstrip('/')}/api/papers/?page=1&size=1",
        f"{base_url.rstrip('/')}/docs",
    ]
    last_error = None
    for url in probe_urls:
        try:
            response = client.get(url)
            if 200 <= response.status_code < 400:
                return
        except Exception as exc:  # pragma: no cover - network variability
            last_error = exc
    raise RuntimeError(f"无法连接后端服务: {base_url}. 上一次错误: {last_error}")


def parse_sse_event(line: str) -> dict[str, Any] | None:
    if not line.startswith("data: "):
        return None
    payload = line[6:].strip()
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def extract_failed_step(steps: list[dict[str, Any]]) -> dict[str, Any] | None:
    for step in steps:
        if step.get("status") == "failed":
            return step
    return None


def upload_once(
    client: httpx.Client,
    base_url: str,
    file_path: Path,
    force: bool,
) -> UploadAttemptResult:
    url = f"{base_url.rstrip('/')}{UPLOAD_PATH}"
    params = {"force": "false" if not force else "true"}
    started_at = time.time()
    steps: list[dict[str, Any]] = []
    final_event: dict[str, Any] | None = None
    last_failed_step: dict[str, Any] | None = None

    try:
        with file_path.open("rb") as file_obj:
            files = {
                "file": (
                    file_path.name,
                    file_obj,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            }
            headers = {"Accept": "text/event-stream"}
            with client.stream("POST", url, params=params, files=files, headers=headers) as response:
                response.raise_for_status()

                for line in response.iter_lines():
                    if not line:
                        continue
                    event = parse_sse_event(line)
                    if not event:
                        continue

                    steps = event.get("steps", []) or steps
                    failed_step = extract_failed_step(steps)
                    if failed_step:
                        last_failed_step = failed_step

                    if event.get("type") == "completed":
                        final_event = event

        duration_seconds = round(time.time() - started_at, 2)
        if final_event and final_event.get("result", {}).get("status") == "success":
            return UploadAttemptResult(
                ok=True,
                error=None,
                failed_step=last_failed_step,
                final_event=final_event,
                result=final_event.get("result"),
                steps=steps,
                duration_seconds=duration_seconds,
            )

        error_message = "未收到 completed 事件"
        if last_failed_step:
            error_message = (
                f"步骤失败: {last_failed_step.get('id')} - "
                f"{last_failed_step.get('error') or last_failed_step.get('message') or '未知错误'}"
            )

        return UploadAttemptResult(
            ok=False,
            error=error_message,
            failed_step=last_failed_step,
            final_event=final_event,
            result=final_event.get("result") if final_event else None,
            steps=steps,
            duration_seconds=duration_seconds,
        )
    except Exception as exc:
        return UploadAttemptResult(
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            failed_step=last_failed_step,
            final_event=final_event,
            result=final_event.get("result") if final_event else None,
            steps=steps,
            duration_seconds=round(time.time() - started_at, 2),
        )


def connect_db(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"数据库不存在: {db_path}")
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_one(conn: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> sqlite3.Row | None:
    cursor = conn.execute(query, params)
    return cursor.fetchone()


def fetch_all(conn: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> list[sqlite3.Row]:
    cursor = conn.execute(query, params)
    return cursor.fetchall()


def has_any_option(question_row: sqlite3.Row) -> bool:
    for key in ("option_a", "option_b", "option_c", "option_d"):
        value = question_row[key]
        if isinstance(value, str) and value.strip():
            return True
    return False


def count_non_empty_db_options(question_row: sqlite3.Row) -> int:
    count = 0
    for key in ("option_a", "option_b", "option_c", "option_d"):
        value = question_row[key]
        if isinstance(value, str) and value.strip():
            count += 1
    return count


def count_text_db_options(question_row: sqlite3.Row) -> int:
    count = 0
    for key in ("option_a", "option_b", "option_c", "option_d"):
        value = question_row[key]
        if not isinstance(value, str):
            continue
        value = value.strip()
        if not value:
            continue
        if re.fullmatch(r"\[IMAGE(?::[^\]]+)?\]", value):
            continue
        count += 1
    return count


def looks_like_open_ended_question(question_text: str | None) -> bool:
    normalized = re.sub(r"\s*\[IMAGE(?::[^\]]+)?\]", "", question_text or "").strip()
    if not normalized:
        return False
    return bool(
        re.match(
            r"(?i)^(what|why|how|when|where|who|whom|whose|which|is|are|was|were|do|does|did|can|could|would|will|should|please)\b",
            normalized,
        )
    )


def safe_json_loads(text: str | None) -> Any:
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def infer_question_type(question_row: sqlite3.Row) -> str:
    stored_type = (question_row["question_type"] or "").strip()
    if stored_type:
        return stored_type

    correct_answer = (question_row["correct_answer"] or "").strip().upper()
    option_count = count_non_empty_db_options(question_row)
    text_option_count = count_text_db_options(question_row)
    if (
        looks_like_open_ended_question(question_row["question_text"])
        and text_option_count == 0
        and (correct_answer not in {"A", "B", "C", "D"} or option_count < 2)
    ):
        return "open_ended"
    if not has_any_option(question_row) and correct_answer not in {"A", "B", "C", "D"}:
        return "open_ended"
    return "multiple_choice"


def has_meaningful_json_options(options: Any) -> bool:
    if not isinstance(options, dict):
        return False
    for value in options.values():
        if isinstance(value, str) and value.strip():
            return True
    return False


def is_open_form_cloze_point(point_row: sqlite3.Row, options: Any) -> bool:
    correct_word = (point_row["correct_word"] or "").strip()
    correct_answer = (point_row["correct_answer"] or "").strip().upper()
    if not correct_word:
        return False
    if correct_answer in {"A", "B", "C", "D"}:
        return False
    return isinstance(options, dict) and not has_meaningful_json_options(options)


@lru_cache(maxsize=1024)
def load_docx_text(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        return ""
    try:
        document = Document(str(path))
    except Exception:
        return ""
    return "\n".join(
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.text and paragraph.text.strip()
    )


def infer_source_expectations(source_file_path: Path | None) -> dict[str, Any]:
    filename = source_file_path.name if source_file_path else ""
    normalized_filename = filename.replace("（", "(").replace("）", ")").replace(" ", "")

    if source_file_path is None:
        return {
            "is_non_english": False,
            "is_answer_sheet": False,
            "is_reading_only": False,
            "expects_reading": True,
            "expects_cloze": True,
            "expects_writing": True,
        }

    text = load_docx_text(str(source_file_path))
    source_body = text.split("参考答案", 1)[0] if "参考答案" in text else text
    normalized_text = re.sub(r"\s+", "", text)
    normalized_source_body = re.sub(r"\s+", "", source_body)
    head_text = normalized_text[:2000]

    is_non_english = ("英语" not in normalized_filename) or ("历史" in normalized_filename)
    is_reading_only = "英语(阅读)" in normalized_filename
    is_answer_sheet = (
        not is_reading_only
        and any(keyword in head_text for keyword in ANSWER_SHEET_KEYWORDS)
    )

    has_reading_structure = bool(
        re.search(r"阅读理解.*?(?:^|\n)[A-D](?:\s*\n|\s)", source_body, re.DOTALL | re.MULTILINE)
    )

    expects_reading = (
        not is_non_english
        and not is_answer_sheet
        and any(keyword in normalized_source_body for keyword in READING_SECTION_KEYWORDS)
        and has_reading_structure
    )
    expects_cloze = (
        not is_non_english
        and not is_reading_only
        and not is_answer_sheet
        and any(keyword in normalized_source_body for keyword in CLOZE_SECTION_KEYWORDS)
    )
    expects_writing = (
        not is_non_english
        and not is_reading_only
        and not is_answer_sheet
        and any(keyword in normalized_source_body for keyword in WRITING_SECTION_KEYWORDS)
    )

    return {
        "is_non_english": is_non_english,
        "is_answer_sheet": is_answer_sheet,
        "is_reading_only": is_reading_only,
        "expects_reading": expects_reading,
        "expects_cloze": expects_cloze,
        "expects_writing": expects_writing,
    }


def verify_paper_in_db(
    conn: sqlite3.Connection,
    filename: str,
    upload_result: dict[str, Any] | None,
    source_file_path: Path | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    checks: dict[str, Any] = {}
    source_expectations = infer_source_expectations(source_file_path)
    checks["source_expectations"] = source_expectations

    paper = fetch_one(
        conn,
        """
        SELECT *
        FROM exam_papers
        WHERE filename = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (filename,),
    )
    if paper is None:
        return {
            "ok": False,
            "issues": [f"exam_papers 中找不到试卷记录: {filename}"],
            "checks": {},
        }

    paper_id = int(paper["id"])
    checks["paper_id"] = paper_id
    checks["paper"] = {
        "import_status": paper["import_status"],
        "parse_strategy": paper["parse_strategy"],
        "confidence": paper["confidence"],
        "error_message": paper["error_message"],
        "year": paper["year"],
        "grade": paper["grade"],
        "version": paper["version"],
    }

    if paper["import_status"] != "completed":
        issues.append(f"试卷 import_status 不是 completed，而是 {paper['import_status']}")
    if paper["parse_strategy"] != "llm":
        issues.append(f"试卷 parse_strategy 不是 llm，而是 {paper['parse_strategy']}")
    if paper["error_message"]:
        issues.append(f"试卷 error_message 非空: {paper['error_message']}")
    if paper["confidence"] is None or float(paper["confidence"]) < 0.9:
        issues.append(f"试卷 confidence 过低: {paper['confidence']}")

    reading_passages = fetch_all(
        conn,
        """
        SELECT *
        FROM reading_passages
        WHERE paper_id = ?
        ORDER BY passage_type
        """,
        (paper_id,),
    )
    checks["reading_passages_count"] = len(reading_passages)
    expected_passages = None
    expected_questions = None
    if upload_result:
        expected_passages = upload_result.get("passages_created")
        expected_questions = upload_result.get("questions_created")

    should_check_reading = bool(
        source_expectations["expects_reading"]
        or reading_passages
        or ((expected_passages or 0) > 0)
        or ((expected_questions or 0) > 0)
    )
    if should_check_reading and not reading_passages:
        issues.append("未找到 reading_passages 记录")

    total_questions = 0
    total_vocab_passage = 0
    total_open_ended_questions = 0
    reading_details: list[dict[str, Any]] = []
    for passage in reading_passages if should_check_reading else []:
        passage_id = int(passage["id"])
        questions = fetch_all(
            conn,
            """
            SELECT *
            FROM questions
            WHERE passage_id = ?
            ORDER BY question_number, id
            """,
            (passage_id,),
        )
        vocab_occurrences = fetch_one(
            conn,
            """
            SELECT COUNT(*) AS count
            FROM vocabulary_passage
            WHERE passage_id = ?
            """,
            (passage_id,),
        )
        vocab_count = int(vocab_occurrences["count"]) if vocab_occurrences else 0
        total_questions += len(questions)
        total_vocab_passage += vocab_count

        passage_issues = []
        if not (passage["content"] or "").strip():
            passage_issues.append(f"{passage['passage_type']}篇 content 为空")
        if (passage["word_count"] or 0) <= 0:
            passage_issues.append(f"{passage['passage_type']}篇 word_count <= 0")
        if not (passage["primary_topic"] or "").strip():
            passage_issues.append(f"{passage['passage_type']}篇 primary_topic 为空")
        if not questions:
            passage_issues.append(f"{passage['passage_type']}篇没有 questions")
        if vocab_count <= 0:
            passage_issues.append(f"{passage['passage_type']}篇没有 vocabulary_passage 记录")

        for question in questions:
            q_num = question["question_number"] or question["id"]
            question_type = infer_question_type(question)
            if question_type == "open_ended":
                total_open_ended_questions += 1
            if not (question["question_text"] or "").strip():
                passage_issues.append(f"{passage['passage_type']}篇第{q_num}题 question_text 为空")
            if question_type != "open_ended":
                if not (question["correct_answer"] or "").strip():
                    passage_issues.append(f"{passage['passage_type']}篇第{q_num}题 correct_answer 为空")
                if not has_any_option(question):
                    passage_issues.append(f"{passage['passage_type']}篇第{q_num}题四个选项都为空")
            if not (question["answer_explanation"] or "").strip():
                passage_issues.append(f"{passage['passage_type']}篇第{q_num}题 answer_explanation 为空")

        reading_details.append(
            {
                "passage_id": passage_id,
                "passage_type": passage["passage_type"],
                "questions_count": len(questions),
                "vocabulary_passage_count": vocab_count,
                "open_ended_questions_count": sum(
                    1 for question in questions if infer_question_type(question) == "open_ended"
                ),
                "issues": passage_issues,
            }
        )
        issues.extend(passage_issues)

    checks["reading_details"] = reading_details
    checks["questions_count"] = total_questions
    checks["open_ended_questions_count"] = total_open_ended_questions
    checks["vocabulary_passage_count"] = total_vocab_passage
    if expected_passages is not None and should_check_reading and expected_passages != len(reading_passages):
        issues.append(
            f"阅读文章数不一致: SSE={expected_passages}, DB={len(reading_passages)}"
        )
    if expected_questions is not None and should_check_reading and expected_questions != total_questions:
        issues.append(
            f"阅读题目数不一致: SSE={expected_questions}, DB={total_questions}"
        )

    cloze_passages = fetch_all(
        conn,
        """
        SELECT *
        FROM cloze_passages
        WHERE paper_id = ?
        ORDER BY id
        """,
        (paper_id,),
    )
    checks["cloze_passages_count"] = len(cloze_passages)
    should_check_cloze = bool(source_expectations["expects_cloze"] or cloze_passages)
    if should_check_cloze and not cloze_passages:
        issues.append("未找到 cloze_passages 记录")

    cloze_details: list[dict[str, Any]] = []
    total_cloze_points = 0
    total_vocab_cloze = 0
    total_open_form_cloze_points = 0
    for cloze in cloze_passages if should_check_cloze else []:
        cloze_id = int(cloze["id"])
        points = fetch_all(
            conn,
            """
            SELECT *
            FROM cloze_points
            WHERE cloze_id = ?
            ORDER BY blank_number, id
            """,
            (cloze_id,),
        )
        vocab_occurrences = fetch_one(
            conn,
            """
            SELECT COUNT(*) AS count
            FROM vocabulary_cloze
            WHERE cloze_id = ?
            """,
            (cloze_id,),
        )
        vocab_count = int(vocab_occurrences["count"]) if vocab_occurrences else 0
        total_cloze_points += len(points)
        total_vocab_cloze += vocab_count

        cloze_issues = []
        if not (cloze["content"] or "").strip():
            cloze_issues.append("完形 content 为空")
        if (cloze["word_count"] or 0) <= 0:
            cloze_issues.append("完形 word_count <= 0")
        if not (cloze["primary_topic"] or "").strip():
            cloze_issues.append("完形 primary_topic 为空")
        if not points:
            cloze_issues.append("完形没有 cloze_points")
        if vocab_count <= 0:
            cloze_issues.append("完形没有 vocabulary_cloze 记录")

        for point in points:
            blank_number = point["blank_number"] or point["id"]
            options = safe_json_loads(point["options"])
            open_form = is_open_form_cloze_point(point, options)
            if open_form:
                total_open_form_cloze_points += 1
            if not point["blank_number"]:
                cloze_issues.append(f"完形空{blank_number} blank_number 为空")
            if not (point["correct_word"] or "").strip():
                cloze_issues.append(f"完形空{blank_number} correct_word 为空")
            if not isinstance(options, dict):
                cloze_issues.append(f"完形空{blank_number} options 不是有效 JSON")
            elif not open_form and not has_meaningful_json_options(options):
                cloze_issues.append(f"完形空{blank_number} options 不是有效 JSON")
            if not open_form and not (point["correct_answer"] or "").strip():
                cloze_issues.append(f"完形空{blank_number} correct_answer 为空")
            if not ((point["primary_point_code"] or "").strip() or (point["point_type"] or "").strip()):
                cloze_issues.append(f"完形空{blank_number} 没有主考点")
            if not (point["translation"] or "").strip():
                cloze_issues.append(f"完形空{blank_number} translation 为空")
            if not (point["explanation"] or "").strip():
                cloze_issues.append(f"完形空{blank_number} explanation 为空")
            if not (point["sentence"] or "").strip():
                cloze_issues.append(f"完形空{blank_number} sentence 为空")

        cloze_details.append(
            {
                "cloze_id": cloze_id,
                "points_count": len(points),
                "vocabulary_cloze_count": vocab_count,
                "open_form_points_count": sum(
                    1 for point in points if is_open_form_cloze_point(point, safe_json_loads(point["options"]))
                ),
                "issues": cloze_issues,
            }
        )
        issues.extend(cloze_issues)

    checks["cloze_details"] = cloze_details
    checks["cloze_points_count"] = total_cloze_points
    checks["open_form_cloze_points_count"] = total_open_form_cloze_points
    checks["vocabulary_cloze_count"] = total_vocab_cloze

    writing_tasks = fetch_all(
        conn,
        """
        SELECT *
        FROM writing_tasks
        WHERE paper_id = ?
        ORDER BY id
        """,
        (paper_id,),
    )
    checks["writing_tasks_count"] = len(writing_tasks)
    should_check_writing = bool(source_expectations["expects_writing"] or writing_tasks)
    checks["effective_expectations"] = {
        "expects_reading": should_check_reading,
        "expects_cloze": should_check_cloze,
        "expects_writing": should_check_writing,
    }
    if should_check_writing and not writing_tasks:
        issues.append("未找到 writing_tasks 记录")

    writing_details: list[dict[str, Any]] = []
    for task in writing_tasks if should_check_writing else []:
        task_id = int(task["id"])
        samples = fetch_all(
            conn,
            """
            SELECT *
            FROM writing_samples
            WHERE task_id = ?
            ORDER BY id
            """,
            (task_id,),
        )
        task_issues = []
        if not (task["task_content"] or "").strip():
            task_issues.append("作文 task_content 为空")
        if not task["group_category_id"]:
            task_issues.append("作文 group_category_id 为空")
        if not task["major_category_id"]:
            task_issues.append("作文 major_category_id 为空")
        if not task["category_id"]:
            task_issues.append("作文 category_id 为空")
        if not samples:
            task_issues.append("作文没有 writing_samples")
        for sample in samples:
            if not (sample["sample_content"] or "").strip():
                task_issues.append("作文范文 sample_content 为空")

        writing_details.append(
            {
                "task_id": task_id,
                "samples_count": len(samples),
                "issues": task_issues,
            }
        )
        issues.extend(task_issues)

    checks["writing_details"] = writing_details
    return {
        "ok": not issues,
        "issues": issues,
        "checks": checks,
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def print_file_result(index: int, total: int, result: dict[str, Any]) -> None:
    status = result["final_status"]
    filename = result["filename"]
    attempts = result["attempts_used"]
    if status == "success":
        print(f"[{index}/{total}] SUCCESS {filename} (attempts={attempts})")
    else:
        print(f"[{index}/{total}] FAILED  {filename} (attempts={attempts})")
        print(f"  reason: {result['failure_reason']}")


def process_file(
    client: httpx.Client,
    conn: sqlite3.Connection,
    file_path: Path,
    base_url: str,
    retries: int,
    sleep_seconds: float,
    force: bool,
) -> dict[str, Any]:
    file_record: dict[str, Any] = {
        "filename": file_path.name,
        "path": str(file_path),
        "attempts": [],
        "attempts_used": 0,
        "final_status": "failed",
        "failure_reason": None,
        "paper_id": None,
        "metadata": None,
        "final_checks": None,
    }

    for attempt in range(1, retries + 1):
        attempt_started_at = datetime.now().isoformat(timespec="seconds")
        upload = upload_once(client, base_url, file_path, force=force)

        attempt_record: dict[str, Any] = {
            "attempt": attempt,
            "started_at": attempt_started_at,
            "upload_ok": upload.ok,
            "upload_duration_seconds": upload.duration_seconds,
            "upload_error": upload.error,
            "failed_step": upload.failed_step,
            "result": upload.result,
            "steps": upload.steps,
            "verification": None,
        }

        if upload.ok:
            verification = verify_paper_in_db(
                conn,
                file_path.name,
                upload.result,
                source_file_path=file_path,
            )
            attempt_record["verification"] = verification
            if verification["ok"]:
                file_record["attempts"].append(attempt_record)
                file_record["attempts_used"] = attempt
                file_record["final_status"] = "success"
                file_record["paper_id"] = verification["checks"].get("paper_id")
                file_record["metadata"] = (upload.result or {}).get("metadata")
                file_record["final_checks"] = verification
                return file_record

            attempt_record["upload_error"] = (
                "数据库校验失败: " + "; ".join(verification["issues"][:10])
            )

        file_record["attempts"].append(attempt_record)
        file_record["attempts_used"] = attempt

        if attempt < retries:
            retry_delay = sleep_seconds * (2 ** (attempt - 1))
            time.sleep(retry_delay)

    last_attempt = file_record["attempts"][-1]
    file_record["failure_reason"] = last_attempt.get("upload_error") or "未知失败"
    file_record["paper_id"] = (
        (last_attempt.get("verification") or {}).get("checks", {}).get("paper_id")
    )
    file_record["metadata"] = (
        (last_attempt.get("result") or {}).get("metadata")
        if last_attempt.get("result")
        else None
    )
    file_record["final_checks"] = last_attempt.get("verification")
    return file_record


def process_file_in_worker(
    *,
    file_path: Path,
    db_path: Path,
    base_url: str,
    retries: int,
    sleep_seconds: float,
    force: bool,
    timeout: httpx.Timeout,
) -> dict[str, Any]:
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        with connect_db(db_path) as conn:
            return process_file(
                client=client,
                conn=conn,
                file_path=file_path,
                base_url=base_url,
                retries=retries,
                sleep_seconds=sleep_seconds,
                force=force,
            )


def summarize(run_records: list[dict[str, Any]]) -> dict[str, Any]:
    success = [r for r in run_records if r["final_status"] == "success"]
    skipped = [r for r in run_records if r["final_status"] == "skipped"]
    failed = [r for r in run_records if r["final_status"] != "success"]
    failed = [r for r in failed if r["final_status"] != "skipped"]
    validation_failed = [
        r for r in failed
        if r.get("final_checks") and not r["final_checks"].get("ok", False)
    ]

    return {
        "total_files": len(run_records),
        "success_count": len(success),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "validation_failed_count": len(validation_failed),
        "failed_files": [r["filename"] for r in failed],
    }


def main() -> int:
    args = parse_args()
    import_dir = args.import_dir.resolve()
    db_path = args.db_path.resolve()
    log_dir = args.log_dir.resolve()
    checkpoint_path = args.checkpoint_file.resolve()
    force = not args.no_force

    files = discover_files(import_dir, args.pattern, args.limit)
    if not files:
        print(f"没有找到可导入的 docx 文件: {import_dir}")
        return 1

    checkpoint = ImportCheckpoint() if args.no_resume else ImportCheckpoint.load(checkpoint_path)
    skipped_records: list[dict[str, Any]] = []
    pending_files: list[Path] = []
    for file_path in files:
        if checkpoint.should_skip(file_path):
            skipped_records.append(
                {
                    "filename": file_path.name,
                    "path": str(file_path),
                    "attempts": [],
                    "attempts_used": checkpoint.records[str(file_path.resolve())].get("attempts_used", 0),
                    "final_status": "skipped",
                    "failure_reason": None,
                    "paper_id": checkpoint.records[str(file_path.resolve())].get("paper_id"),
                    "metadata": None,
                    "final_checks": None,
                }
            )
            continue
        pending_files.append(file_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = log_dir / f"frontend_import_report_{timestamp}.json"
    failures_path = log_dir / f"frontend_import_failures_{timestamp}.jsonl"

    timeout = httpx.Timeout(
        connect=10.0,
        read=args.request_timeout,
        write=args.request_timeout,
        pool=args.request_timeout,
    )

    print("=" * 88)
    print("前端导入模拟脚本")
    print("=" * 88)
    print(f"导入目录: {import_dir}")
    print(f"数据库:   {db_path}")
    print(f"后端地址: {args.base_url}")
    print(f"文件数量: {len(files)}")
    print(f"跳过已完成: {len(skipped_records)}")
    print(f"待处理数: {len(pending_files)}")
    print(f"重试次数: {args.retries}")
    print(f"并发数:   {args.concurrency}")
    print(f"强制导入: {force}")
    print(f"断点续传: {not args.no_resume}")
    print(f"Checkpoint:{checkpoint_path}")
    print()

    run_started_at = datetime.now().isoformat(timespec="seconds")
    run_records: list[dict[str, Any]] = list(skipped_records)

    try:
        # 禁用 trust_env，避免本地 SSE 请求被系统代理接管而卡住或中断。
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            ensure_backend_alive(client, args.base_url)
        if pending_files:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
                future_to_file: dict[concurrent.futures.Future, Path] = {}
                for file_path in pending_files:
                    print(f"[QUEUE] {file_path.name}")
                    future = executor.submit(
                        process_file_in_worker,
                        file_path=file_path,
                        db_path=db_path,
                        base_url=args.base_url,
                        retries=args.retries,
                        sleep_seconds=args.sleep_seconds,
                        force=force,
                        timeout=timeout,
                    )
                    future_to_file[future] = file_path

                for completed_index, future in enumerate(
                    concurrent.futures.as_completed(future_to_file),
                    start=1,
                ):
                    file_path = future_to_file[future]
                    try:
                        record = future.result()
                    except Exception as exc:
                        record = {
                            "filename": file_path.name,
                            "path": str(file_path),
                            "attempts": [],
                            "attempts_used": 0,
                            "final_status": "failed",
                            "failure_reason": f"{type(exc).__name__}: {exc}",
                            "paper_id": None,
                            "metadata": None,
                            "final_checks": None,
                        }
                    run_records.append(record)
                    checkpoint.update_with_result(file_path, record)
                    if not args.no_resume:
                        checkpoint.save(checkpoint_path)
                    print_file_result(completed_index, len(pending_files), record)

    except KeyboardInterrupt:
        print("\n用户中断，正在保存已完成结果...")
    except Exception as exc:
        print(f"\n运行异常: {type(exc).__name__}: {exc}")
        print(traceback.format_exc())
        run_records.append(
            {
                "filename": "__runtime__",
                "path": "",
                "attempts": [],
                "attempts_used": 0,
                "final_status": "failed",
                "failure_reason": f"{type(exc).__name__}: {exc}",
                "paper_id": None,
                "metadata": None,
                "final_checks": None,
            }
        )
    finally:
        if not args.no_resume:
            checkpoint.save(checkpoint_path)

    summary = summarize(run_records)
    report_data = {
        "started_at": run_started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "config": {
            "import_dir": str(import_dir),
            "db_path": str(db_path),
            "base_url": args.base_url,
            "pattern": args.pattern,
            "limit": args.limit,
            "retries": args.retries,
            "sleep_seconds": args.sleep_seconds,
            "concurrency": args.concurrency,
            "force": force,
            "resume": not args.no_resume,
            "checkpoint_file": str(checkpoint_path),
        },
        "summary": summary,
        "results": run_records,
    }

    failed_records = [
        r for r in run_records
        if r["final_status"] not in {"success", "skipped"}
    ]
    write_json(report_path, report_data)
    write_jsonl(failures_path, failed_records)

    print()
    print("=" * 88)
    print("运行完成")
    print("=" * 88)
    print(f"总文件数:   {summary['total_files']}")
    print(f"成功数:     {summary['success_count']}")
    print(f"跳过数:     {summary['skipped_count']}")
    print(f"失败数:     {summary['failed_count']}")
    print(f"校验失败数: {summary['validation_failed_count']}")
    print(f"总报告:     {report_path}")
    print(f"失败日志:   {failures_path}")

    return 0 if summary["failed_count"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
