#!/usr/bin/env python3
"""
修复试卷数据库中的历史元数据与题型标记。

修复内容：
1. 删除已不在当前 `试卷库/docx-解析版` 中的历史残留试卷记录
2. 依据最新文件名解析逻辑回填 exam_papers 元数据
3. 为历史 questions 回填 question_type（开放题 / 选择题）
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.docx_parser import DocxParser  # noqa: E402


DEFAULT_DB_PATH = REPO_ROOT / "backend" / "database" / "teaching.db"
DEFAULT_IMPORT_DIR = REPO_ROOT / "试卷库" / "docx-解析版"
DEFAULT_LOG_DIR = REPO_ROOT / "logs"


@dataclass
class RepairSummary:
    deleted_papers: int = 0
    updated_papers: int = 0
    updated_questions: int = 0
    open_ended_questions: int = 0
    multiple_choice_questions: int = 0


def connect_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def has_any_option(row: sqlite3.Row) -> bool:
    for key in ("option_a", "option_b", "option_c", "option_d"):
        value = row[key]
        if isinstance(value, str) and value.strip():
            return True
    return False


def count_non_empty_options(row: sqlite3.Row) -> int:
    count = 0
    for key in ("option_a", "option_b", "option_c", "option_d"):
        value = row[key]
        if isinstance(value, str) and value.strip():
            count += 1
    return count


def count_text_options(row: sqlite3.Row) -> int:
    count = 0
    for key in ("option_a", "option_b", "option_c", "option_d"):
        value = row[key]
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


def infer_question_type(row: sqlite3.Row) -> str:
    correct_answer = (row["correct_answer"] or "").strip().upper()
    option_count = count_non_empty_options(row)
    text_option_count = count_text_options(row)
    if (
        looks_like_open_ended_question(row["question_text"])
        and text_option_count == 0
        and (correct_answer not in {"A", "B", "C", "D"} or option_count < 2)
    ):
        return "open_ended"
    if not has_any_option(row) and correct_answer not in {"A", "B", "C", "D"}:
        return "open_ended"
    return "multiple_choice"


def delete_paper(conn: sqlite3.Connection, paper_id: int) -> None:
    reading_ids = [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM reading_passages WHERE paper_id = ?",
            (paper_id,),
        ).fetchall()
    ]
    if reading_ids:
        placeholders = ",".join("?" * len(reading_ids))
        conn.execute(
            f"DELETE FROM vocabulary_passage WHERE passage_id IN ({placeholders})",
            tuple(reading_ids),
        )
        conn.execute(
            f"DELETE FROM questions WHERE passage_id IN ({placeholders})",
            tuple(reading_ids),
        )

    cloze_ids = [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM cloze_passages WHERE paper_id = ?",
            (paper_id,),
        ).fetchall()
    ]
    if cloze_ids:
        cloze_placeholders = ",".join("?" * len(cloze_ids))
        cloze_point_ids = [
            row["id"]
            for row in conn.execute(
                f"SELECT id FROM cloze_points WHERE cloze_id IN ({cloze_placeholders})",
                tuple(cloze_ids),
            ).fetchall()
        ]
        if cloze_point_ids:
            point_placeholders = ",".join("?" * len(cloze_point_ids))
            conn.execute(
                f"DELETE FROM cloze_secondary_points WHERE cloze_point_id IN ({point_placeholders})",
                tuple(cloze_point_ids),
            )
            conn.execute(
                f"DELETE FROM cloze_rejection_points WHERE cloze_point_id IN ({point_placeholders})",
                tuple(cloze_point_ids),
            )
        conn.execute(
            f"DELETE FROM vocabulary_cloze WHERE cloze_id IN ({cloze_placeholders})",
            tuple(cloze_ids),
        )
        conn.execute(
            f"DELETE FROM cloze_points WHERE cloze_id IN ({cloze_placeholders})",
            tuple(cloze_ids),
        )
        conn.execute(
            f"DELETE FROM cloze_passages WHERE id IN ({cloze_placeholders})",
            tuple(cloze_ids),
        )

    task_ids = [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM writing_tasks WHERE paper_id = ?",
            (paper_id,),
        ).fetchall()
    ]
    if task_ids:
        placeholders = ",".join("?" * len(task_ids))
        conn.execute(
            f"DELETE FROM writing_samples WHERE task_id IN ({placeholders})",
            tuple(task_ids),
        )
        conn.execute(
            f"DELETE FROM writing_tasks WHERE id IN ({placeholders})",
            tuple(task_ids),
        )

    conn.execute("DELETE FROM reading_passages WHERE paper_id = ?", (paper_id,))
    conn.execute("DELETE FROM exam_papers WHERE id = ?", (paper_id,))


def repair_database(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    import_dir: Path = DEFAULT_IMPORT_DIR,
    log_dir: Path = DEFAULT_LOG_DIR,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = log_dir / f"db_repair_{timestamp}.json"
    summary = RepairSummary()

    current_filenames = {path.name for path in import_dir.glob("*.docx")}

    with connect_db(db_path) as conn:
        stale_rows = conn.execute(
            "SELECT id, filename FROM exam_papers ORDER BY id"
        ).fetchall()
        stale_to_delete = [
            row for row in stale_rows
            if row["filename"] not in current_filenames
        ]

        deleted_filenames: list[str] = []
        for row in stale_to_delete:
            delete_paper(conn, int(row["id"]))
            deleted_filenames.append(row["filename"])
            summary.deleted_papers += 1

        paper_rows = conn.execute(
            """
            SELECT id, filename, year, region, school, grade, semester, exam_type, version
            FROM exam_papers
            ORDER BY id
            """
        ).fetchall()

        updated_papers: list[dict] = []
        for row in paper_rows:
            parsed = DocxParser(row["filename"]).parse_filename()
            next_values = {
                "year": parsed.get("year", row["year"]),
                "region": parsed.get("region") if parsed.get("region") is not None else row["region"],
                "school": parsed.get("school") if parsed.get("school") is not None else row["school"],
                "grade": parsed.get("grade") if parsed.get("grade") is not None else row["grade"],
                "semester": parsed.get("semester") if parsed.get("semester") is not None else row["semester"],
                "exam_type": parsed.get("exam_type") if parsed.get("exam_type") is not None else row["exam_type"],
                "version": parsed.get("version") if parsed.get("version") is not None else row["version"],
            }

            current_values = {
                "year": row["year"],
                "region": row["region"],
                "school": row["school"],
                "grade": row["grade"],
                "semester": row["semester"],
                "exam_type": row["exam_type"],
                "version": row["version"],
            }

            if next_values != current_values:
                conn.execute(
                    """
                    UPDATE exam_papers
                    SET year = ?, region = ?, school = ?, grade = ?, semester = ?,
                        exam_type = ?, version = ?
                    WHERE id = ?
                    """,
                    (
                        next_values["year"],
                        next_values["region"],
                        next_values["school"],
                        next_values["grade"],
                        next_values["semester"],
                        next_values["exam_type"],
                        next_values["version"],
                        row["id"],
                    ),
                )
                updated_papers.append(
                    {
                        "id": row["id"],
                        "filename": row["filename"],
                        "before": current_values,
                        "after": next_values,
                    }
                )
                summary.updated_papers += 1

        question_rows = conn.execute(
            """
            SELECT id, question_type, question_text, option_a, option_b, option_c, option_d, correct_answer
            FROM questions
            ORDER BY id
            """
        ).fetchall()

        for row in question_rows:
            inferred_type = infer_question_type(row)
            current_type = (row["question_type"] or "").strip()
            if current_type != inferred_type:
                conn.execute(
                    "UPDATE questions SET question_type = ? WHERE id = ?",
                    (inferred_type, row["id"]),
                )
                summary.updated_questions += 1

            if inferred_type == "open_ended":
                summary.open_ended_questions += 1
            else:
                summary.multiple_choice_questions += 1

        conn.commit()

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "db_path": str(db_path),
        "import_dir": str(import_dir),
        "summary": {
            "deleted_papers": summary.deleted_papers,
            "updated_papers": summary.updated_papers,
            "updated_questions": summary.updated_questions,
            "open_ended_questions": summary.open_ended_questions,
            "multiple_choice_questions": summary.multiple_choice_questions,
        },
        "deleted_filenames": deleted_filenames,
        "updated_papers": updated_papers,
    }

    log_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def main() -> int:
    report_path = repair_database()
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
