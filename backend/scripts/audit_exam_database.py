#!/usr/bin/env python3
"""
审计当前解析版试卷库与数据库的一致性。
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

from import_papers_via_frontend import connect_db, verify_paper_in_db


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / "backend" / "database" / "teaching.db"
DEFAULT_IMPORT_DIR = REPO_ROOT / "试卷库" / "docx-解析版"
DEFAULT_LOG_DIR = REPO_ROOT / "logs"


def fetch_scalar(conn: sqlite3.Connection, query: str, params: tuple = ()) -> int:
    row = conn.execute(query, params).fetchone()
    if row is None:
        return 0
    return int(row[0])


def classify_issue(issue: str) -> str:
    if "四个选项都为空" in issue:
        return "选项缺失/异常"
    if "correct_answer 为空" in issue:
        return "答案缺失"
    if "未找到 cloze_passages" in issue or "完形" in issue:
        if "primary_topic 为空" in issue or "没有主考点" in issue:
            return "话题/考点缺失"
        if "translation 为空" in issue or "explanation 为空" in issue or "sentence 为空" in issue:
            return "完形分析字段缺失"
        if "vocabulary_cloze" in issue:
            return "高频词缺失"
        if "content 为空" in issue or "word_count <= 0" in issue:
            return "正文/词数异常"
        return "完形缺失"
    if "未找到 reading_passages" in issue or "篇" in issue:
        if "primary_topic 为空" in issue:
            return "话题/考点缺失"
        if "vocabulary_passage" in issue:
            return "高频词缺失"
        if "content 为空" in issue or "word_count <= 0" in issue:
            return "正文/词数异常"
        return "阅读缺失"
    if "作文" in issue:
        return "作文缺失"
    return "其他"


def audit_database(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    import_dir: Path = DEFAULT_IMPORT_DIR,
    log_dir: Path = DEFAULT_LOG_DIR,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = log_dir / f"db_audit_{timestamp}.json"

    file_paths = sorted(import_dir.glob("*.docx"))
    filesystem_filenames = [path.name for path in file_paths]
    filesystem_set = set(filesystem_filenames)

    with connect_db(db_path) as conn:
        db_filenames = [
            row["filename"]
            for row in conn.execute(
                "SELECT filename FROM exam_papers ORDER BY filename"
            ).fetchall()
        ]
        db_set = set(db_filenames)

        failed_verifications = []
        bucket_counter: Counter[str] = Counter()
        for file_path in file_paths:
            verification = verify_paper_in_db(
                conn,
                file_path.name,
                None,
                source_file_path=file_path,
            )
            if not verification["ok"]:
                failed_verifications.append(
                    {
                        "filename": file_path.name,
                        "issues": verification["issues"],
                        "checks": verification["checks"],
                    }
                )
                for issue in verification["issues"]:
                    bucket_counter[classify_issue(issue)] += 1

        duplicate_filename_groups = fetch_scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM (
                SELECT filename
                FROM exam_papers
                GROUP BY filename
                HAVING COUNT(*) > 1
            )
            """,
        )

        metadata_null_counts = {
            "year": fetch_scalar(conn, "SELECT COUNT(*) FROM exam_papers WHERE year IS NULL"),
            "grade": fetch_scalar(conn, "SELECT COUNT(*) FROM exam_papers WHERE grade IS NULL"),
            "semester": fetch_scalar(conn, "SELECT COUNT(*) FROM exam_papers WHERE semester IS NULL"),
            "exam_type": fetch_scalar(conn, "SELECT COUNT(*) FROM exam_papers WHERE exam_type IS NULL"),
        }
        version_mismatch_counts = {
            "teacher_in_name_but_not_teacher_version": fetch_scalar(
                conn,
                "SELECT COUNT(*) FROM exam_papers WHERE filename LIKE '%教师版%' AND version != '教师版'",
            ),
            "analysis_in_name_but_not_analysis_version": fetch_scalar(
                conn,
                "SELECT COUNT(*) FROM exam_papers WHERE filename LIKE '%解析版%' AND version != '解析版'",
            ),
            "original_in_name_but_not_original_version": fetch_scalar(
                conn,
                "SELECT COUNT(*) FROM exam_papers WHERE filename LIKE '%原卷版%' AND version != '原卷版'",
            ),
        }
        question_type_counts = {
            "open_ended": fetch_scalar(
                conn,
                "SELECT COUNT(*) FROM questions WHERE question_type = 'open_ended'",
            ),
            "multiple_choice": fetch_scalar(
                conn,
                "SELECT COUNT(*) FROM questions WHERE question_type = 'multiple_choice'",
            ),
            "empty": fetch_scalar(
                conn,
                "SELECT COUNT(*) FROM questions WHERE IFNULL(TRIM(question_type), '') = ''",
            ),
        }
        orphan_checks = {
            "questions_without_passage": fetch_scalar(
                conn,
                "SELECT COUNT(*) FROM questions q LEFT JOIN reading_passages rp ON rp.id = q.passage_id WHERE rp.id IS NULL",
            ),
            "reading_passages_without_paper": fetch_scalar(
                conn,
                "SELECT COUNT(*) FROM reading_passages rp LEFT JOIN exam_papers ep ON ep.id = rp.paper_id WHERE ep.id IS NULL",
            ),
            "cloze_passages_without_paper": fetch_scalar(
                conn,
                "SELECT COUNT(*) FROM cloze_passages cp LEFT JOIN exam_papers ep ON ep.id = cp.paper_id WHERE ep.id IS NULL",
            ),
            "cloze_points_without_cloze": fetch_scalar(
                conn,
                "SELECT COUNT(*) FROM cloze_points p LEFT JOIN cloze_passages cp ON cp.id = p.cloze_id WHERE cp.id IS NULL",
            ),
            "cloze_secondary_without_point": fetch_scalar(
                conn,
                "SELECT COUNT(*) FROM cloze_secondary_points sp LEFT JOIN cloze_points p ON p.id = sp.cloze_point_id WHERE p.id IS NULL",
            ),
            "cloze_rejection_without_point": fetch_scalar(
                conn,
                "SELECT COUNT(*) FROM cloze_rejection_points rp LEFT JOIN cloze_points p ON p.id = rp.cloze_point_id WHERE p.id IS NULL",
            ),
            "vocabulary_passage_without_passage": fetch_scalar(
                conn,
                "SELECT COUNT(*) FROM vocabulary_passage vp LEFT JOIN reading_passages rp ON rp.id = vp.passage_id WHERE rp.id IS NULL",
            ),
            "vocabulary_cloze_without_cloze": fetch_scalar(
                conn,
                "SELECT COUNT(*) FROM vocabulary_cloze vc LEFT JOIN cloze_passages cp ON cp.id = vc.cloze_id WHERE cp.id IS NULL",
            ),
            "writing_tasks_without_paper": fetch_scalar(
                conn,
                "SELECT COUNT(*) FROM writing_tasks wt LEFT JOIN exam_papers ep ON ep.id = wt.paper_id WHERE ep.id IS NULL",
            ),
            "writing_samples_without_task": fetch_scalar(
                conn,
                "SELECT COUNT(*) FROM writing_samples ws LEFT JOIN writing_tasks wt ON wt.id = ws.task_id WHERE wt.id IS NULL",
            ),
        }

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "import_dir": str(import_dir),
        "db_path": str(db_path),
        "filesystem_docx_parse_count": len(filesystem_filenames),
        "db_exam_papers_count": len(db_filenames),
        "db_completed_count": None,
        "duplicate_filename_groups": duplicate_filename_groups,
        "fs_only_filenames": sorted(filesystem_set - db_set),
        "db_only_filenames": sorted(db_set - filesystem_set),
        "verification_ok_count": len(filesystem_filenames) - len(failed_verifications),
        "verification_failed_count": len(failed_verifications),
        "failed_files": failed_verifications,
        "issue_buckets": dict(bucket_counter),
        "metadata_null_counts": metadata_null_counts,
        "version_mismatch_counts": version_mismatch_counts,
        "question_type_counts": question_type_counts,
        "orphan_checks": orphan_checks,
    }

    with connect_db(db_path) as conn:
        report["db_completed_count"] = fetch_scalar(
            conn,
            "SELECT COUNT(*) FROM exam_papers WHERE import_status = 'completed'",
        )

    log_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report_path


def main() -> int:
    report_path = audit_database()
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
