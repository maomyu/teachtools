#!/usr/bin/env python3
"""
定向修复剩余问题试卷。

修复范围：
1. 2010 中考卷缺阅读
2. 少量试卷缺作文
3. 少量完形缺主题、考点分析或高频词
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, select


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.papers import infer_question_type_from_payload  # noqa: E402
from app.database import async_session_factory  # noqa: E402
from app.models.paper import ExamPaper  # noqa: E402
from app.models.reading import ReadingPassage, Question  # noqa: E402
from app.models.vocabulary import Vocabulary, VocabularyPassage  # noqa: E402
from app.models.cloze import ClozePassage, ClozePoint, ClozeSecondaryPoint, ClozeRejectionPoint  # noqa: E402
from app.models.vocabulary_cloze import VocabularyCloze  # noqa: E402
from app.models.writing import WritingTask  # noqa: E402
from app.services.cloze_analyzer import ClozeAnalyzerV5, NEW_CODE_TO_LEGACY  # noqa: E402
from app.services.image_extractor import ImageExtractor  # noqa: E402
from app.services.llm_parser import LLMDocumentParser  # noqa: E402
from app.services.topic_classifier import TopicClassifier  # noqa: E402
from app.services.vocab_extractor import ExtractedWord, VocabExtractor  # noqa: E402
from app.services.writing_service import WritingService  # noqa: E402
from app.services.writing_topic_classifier import WritingTopicClassifier  # noqa: E402
from scripts.import_papers_via_frontend import infer_source_expectations  # noqa: E402


TARGETS = [
    "2010年北京市中考英语试题（解析版）.docx",
    "2022北京景山学校初二（下）期中英语（教师版）.docx",
    "2023北京人大附中初二（上）期中英语（教师版）.docx",
    "2024北京铁二中初二（下）期中英语（教师版）.docx",
    "2025北京一六六中初二（上）期中英语（教师版）.docx",
    "2025北京通州初二（下）期中英语（教师版）.docx",
]
DOCX_DIR = REPO_ROOT / "试卷库" / "docx-解析版"
LOG_DIR = REPO_ROOT / "logs"


@dataclass
class RepairLog:
    filename: str
    actions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


async def get_paper(session, filename: str) -> ExamPaper:
    result = await session.execute(
        select(ExamPaper).where(ExamPaper.filename == filename).order_by(ExamPaper.id.desc())
    )
    paper = result.scalars().first()
    if not paper:
        raise ValueError(f"未找到试卷记录: {filename}")
    return paper


async def repair_reading(session, paper: ExamPaper, file_path: Path, log: RepairLog) -> None:
    result = await session.execute(
        select(ReadingPassage).where(ReadingPassage.paper_id == paper.id)
    )
    if result.scalars().first():
        return

    parser = LLMDocumentParser()
    llm_result = await parser.parse_document(str(file_path), use_fileid=True)
    if not llm_result.success or not llm_result.passages:
        raise ValueError(f"阅读解析失败: {llm_result.error}")

    try:
        ImageExtractor().enrich_passages_with_images(str(file_path), paper.id, llm_result.passages)
    except Exception:
        pass

    for passage_data in llm_result.passages:
        passage = ReadingPassage(
            paper_id=paper.id,
            passage_type=passage_data.get("passage_type", "C"),
            title=passage_data.get("title"),
            content=passage_data.get("content", ""),
            word_count=passage_data.get("word_count") or 0,
            has_questions=bool(passage_data.get("questions")),
        )
        session.add(passage)
        await session.flush()

        for q_data in passage_data.get("questions", []):
            options = q_data.get("options", {})
            question = Question(
                passage_id=passage.id,
                question_number=q_data.get("question_number"),
                question_text=q_data.get("question_text", ""),
                option_a=options.get("A"),
                option_b=options.get("B"),
                option_c=options.get("C"),
                option_d=options.get("D"),
                correct_answer=q_data.get("correct_answer"),
                answer_explanation=q_data.get("answer_explanation"),
                question_type=infer_question_type_from_payload(q_data),
            )
            session.add(question)

    log.actions.append("补齐阅读文章与题目")


async def get_or_create_vocabulary(session, word_data) -> Vocabulary:
    result = await session.execute(
        select(Vocabulary).where(Vocabulary.word == word_data.word)
    )
    vocab = result.scalar_one_or_none()
    if not vocab:
        vocab = Vocabulary(
            word=word_data.word,
            lemma=word_data.lemma,
            frequency=0,
            definition=word_data.definition,
        )
        session.add(vocab)
        await session.flush()
    elif not vocab.definition and word_data.definition:
        vocab.definition = word_data.definition
    return vocab


STOPWORDS = {
    "the", "and", "that", "with", "from", "this", "have", "will", "were", "your",
    "their", "they", "there", "when", "what", "where", "which", "would", "could",
    "about", "into", "then", "than", "them", "been", "because", "after", "before",
    "while", "over", "very", "much", "just", "also", "some", "only", "been", "being",
}


def build_frequency_fallback_words(content: str, extractor: VocabExtractor) -> list[ExtractedWord]:
    tokens = re.findall(r"[A-Za-z][A-Za-z'-]+", content.lower())
    counts = Counter(
        token for token in tokens
        if len(token) >= 4 and token not in STOPWORDS
    )
    words: list[ExtractedWord] = []
    for word, _ in counts.most_common(12):
        occurrences = extractor._find_word_occurrences(word, content)
        if not occurrences:
            continue
        words.append(
            ExtractedWord(
                word=word,
                lemma=word,
                frequency=len(occurrences),
                definition="",
                occurrences=occurrences,
            )
        )
    return words


async def repair_reading_enrichment(session, paper: ExamPaper, log: RepairLog) -> None:
    result = await session.execute(
        select(ReadingPassage).where(ReadingPassage.paper_id == paper.id).order_by(ReadingPassage.id)
    )
    passages = result.scalars().all()
    if not passages:
        return

    classifier = TopicClassifier()
    extractor = VocabExtractor()
    topics_updated = 0
    vocab_added = 0

    for passage in passages:
        if passage.content and len(passage.content) > 50 and not (passage.primary_topic or "").strip():
            topic_result = await classifier.classify(passage.content, paper.grade or "初二")
            if topic_result.success and topic_result.primary_topic:
                passage.primary_topic = topic_result.primary_topic
                passage.secondary_topics = json.dumps([], ensure_ascii=False)
                passage.topic_confidence = topic_result.confidence
                if topic_result.keywords:
                    passage.keywords = json.dumps(topic_result.keywords, ensure_ascii=False)
                topics_updated += 1

        existing_links = await session.execute(
            select(VocabularyPassage.vocabulary_id, VocabularyPassage.char_position).where(
                VocabularyPassage.passage_id == passage.id
            )
        )
        seen_occurrences = {(row[0], row[1]) for row in existing_links.all()}
        if seen_occurrences or not passage.content or len(passage.content) < 50:
            continue

        extracted_words = await extractor.extract_async(passage.content)
        if not extracted_words:
            extracted_words = build_frequency_fallback_words(passage.content, extractor)
        for word_data in extracted_words:
            vocab = await get_or_create_vocabulary(session, word_data)
            for occ in word_data.occurrences:
                occ_key = (vocab.id, occ.char_position)
                if occ_key in seen_occurrences:
                    continue
                session.add(
                    VocabularyPassage(
                        vocabulary_id=vocab.id,
                        passage_id=passage.id,
                        sentence=occ.sentence,
                        char_position=occ.char_position,
                        end_position=occ.end_position,
                        word_position=occ.word_position,
                    )
                )
                seen_occurrences.add(occ_key)
                vocab_added += 1

    if topics_updated:
        log.actions.append(f"补齐 {topics_updated} 篇阅读主话题")
    if vocab_added:
        log.actions.append(f"补齐 {vocab_added} 条阅读高频词关联")


async def repair_writing(session, paper: ExamPaper, file_path: Path, log: RepairLog) -> None:
    result = await session.execute(
        select(WritingTask).where(WritingTask.paper_id == paper.id)
    )
    task = result.scalars().first()
    if task:
        if task.primary_topic:
            return
        classifier = WritingTopicClassifier()
        topic_result = await classifier.classify(
            content=task.task_content,
            requirements=task.requirements or "",
        )
        if topic_result.success and topic_result.primary_topic:
            task.primary_topic = topic_result.primary_topic
            log.actions.append("补齐作文主话题")
        return

    parser = LLMDocumentParser()
    fileid = await parser.upload_file(str(file_path))
    writing_result = await parser.extract_writing(fileid, file_path=str(file_path))
    if not writing_result.success or not writing_result.content:
        raise ValueError(f"作文提取失败: {writing_result.error}")

    classifier = WritingTopicClassifier()
    topic_result = await classifier.classify(
        content=writing_result.content,
        requirements=writing_result.requirements or "",
    )
    primary_topic = topic_result.primary_topic if topic_result.success else None

    task = WritingTask(
        paper_id=paper.id,
        task_content=writing_result.content,
        requirements=writing_result.requirements,
        word_limit=writing_result.word_limit,
        writing_type=writing_result.writing_type,
        application_type=writing_result.application_type,
        primary_topic=primary_topic,
        grade=paper.grade,
        semester=paper.semester,
        exam_type=paper.exam_type,
    )
    session.add(task)
    await session.flush()

    writing_service = WritingService(session)
    await writing_service.generate_sample(task_id=task.id, score_level="一档")
    log.actions.append("补齐作文题目与范文")


async def repair_cloze_topic(session, paper: ExamPaper, log: RepairLog) -> ClozePassage | None:
    result = await session.execute(
        select(ClozePassage).where(ClozePassage.paper_id == paper.id)
    )
    cloze = result.scalars().first()
    if not cloze:
        return None
    if cloze.primary_topic:
        return cloze

    classifier = TopicClassifier()
    topic_result = await classifier.classify(cloze.original_content or cloze.content, paper.grade or "初二")
    if topic_result.success and topic_result.primary_topic:
        cloze.primary_topic = topic_result.primary_topic
        cloze.topic_confidence = topic_result.confidence
        cloze.secondary_topics = json.dumps([], ensure_ascii=False)
        log.actions.append("补齐完形主话题")
    return cloze


async def repair_cloze_points(session, paper: ExamPaper, log: RepairLog) -> ClozePassage | None:
    result = await session.execute(
        select(ClozePassage).where(ClozePassage.paper_id == paper.id)
    )
    cloze = result.scalars().first()
    if not cloze:
        return None

    result = await session.execute(
        select(ClozePoint).where(ClozePoint.cloze_id == cloze.id).order_by(ClozePoint.blank_number)
    )
    points = result.scalars().all()
    missing_points = [
        point for point in points
        if not (
            (point.primary_point_code or "").strip()
            and (point.translation or "").strip()
            and (point.explanation or "").strip()
            and (point.sentence or "").strip()
        )
    ]
    if not missing_points:
        return cloze

    analyzer = ClozeAnalyzerV5()
    analyzed = 0
    for point in missing_points:
        try:
            options = json.loads(point.options) if isinstance(point.options, str) and point.options else {}
        except json.JSONDecodeError:
            options = {}
        textbook_info = await analyzer.lookup_textbook_definition(point.correct_word, session)
        context = analyzer.extract_context(cloze.content, point.blank_number)
        analysis_result = None
        for attempt in range(3):
            analysis_result = await analyzer.analyze_point(
                blank_number=point.blank_number,
                correct_word=point.correct_word,
                options=options,
                context=context,
                textbook_info=textbook_info,
            )
            if analysis_result.success:
                break
            if attempt < 2:
                await asyncio.sleep(1.5 * (attempt + 1))
        if not analysis_result.success:
            continue

        await session.execute(
            delete(ClozeSecondaryPoint).where(ClozeSecondaryPoint.cloze_point_id == point.id)
        )
        await session.execute(
            delete(ClozeRejectionPoint).where(ClozeRejectionPoint.cloze_point_id == point.id)
        )

        if analysis_result.primary_point:
            point.primary_point_code = analysis_result.primary_point.get("code")
            if point.primary_point_code in NEW_CODE_TO_LEGACY:
                point.point_type = NEW_CODE_TO_LEGACY[point.primary_point_code]
                point.legacy_point_type = point.point_type
        point.translation = analysis_result.translation
        point.explanation = analysis_result.explanation
        point.sentence = context

        if analysis_result.confusion_words:
            point.confusion_words = json.dumps(analysis_result.confusion_words, ensure_ascii=False)
        if analysis_result.tips:
            point.tips = analysis_result.tips
        if analysis_result.phrase:
            point.phrase = analysis_result.phrase
        if analysis_result.similar_phrases:
            point.similar_phrases = json.dumps(analysis_result.similar_phrases, ensure_ascii=False)
        if analysis_result.word_analysis:
            point.word_analysis = json.dumps(analysis_result.word_analysis, ensure_ascii=False)
        if analysis_result.dictionary_source:
            point.dictionary_source = analysis_result.dictionary_source
        if analysis_result.is_rare_meaning:
            point.is_rare_meaning = True
        if analysis_result.textbook_meaning:
            point.textbook_meaning = analysis_result.textbook_meaning
        if analysis_result.textbook_source:
            point.textbook_source = analysis_result.textbook_source
        if analysis_result.context_meaning:
            point.context_meaning = analysis_result.context_meaning
        if analysis_result.similar_words:
            point.similar_words = json.dumps(analysis_result.similar_words, ensure_ascii=False)

        for idx, sp in enumerate(analysis_result.secondary_points or []):
            point_code = sp.get("code") or sp.get("point_code") or "D1"
            session.add(
                ClozeSecondaryPoint(
                    cloze_point_id=point.id,
                    point_code=point_code,
                    explanation=sp.get("explanation"),
                    sort_order=idx,
                )
            )
        for rp in analysis_result.rejection_points or []:
            rejection_code = rp.get("rejection_code") or rp.get("code") or rp.get("point_code") or "D1"
            rejection_reason = rp.get("rejection_reason") or rp.get("explanation") or ""
            session.add(
                ClozeRejectionPoint(
                    cloze_point_id=point.id,
                    option_word=rp.get("option_word"),
                    point_code=rejection_code,
                    rejection_code=rejection_code,
                    explanation=rejection_reason,
                    rejection_reason=rejection_reason,
                )
            )
        analyzed += 1
        print(
            f"[POINT] {paper.filename} blank={point.blank_number} code={point.primary_point_code}",
            flush=True,
        )

    if analyzed:
        log.actions.append(f"补齐 {analyzed} 个完形空考点分析")
    return cloze


async def repair_cloze_vocab(session, paper: ExamPaper, log: RepairLog) -> None:
    result = await session.execute(
        select(ClozePassage).where(ClozePassage.paper_id == paper.id)
    )
    cloze = result.scalars().first()
    if not cloze:
        return

    result = await session.execute(
        select(VocabularyCloze).where(VocabularyCloze.cloze_id == cloze.id)
    )
    if result.scalars().first():
        return

    extractor = VocabExtractor()
    extracted_words = await extractor.extract_async(cloze.content)
    if not extracted_words:
        extracted_words = build_frequency_fallback_words(cloze.content, extractor)
    added = 0
    for word_data in extracted_words:
        vocab = await get_or_create_vocabulary(session, word_data)

        for occ in word_data.occurrences:
            session.add(
                VocabularyCloze(
                    vocabulary_id=vocab.id,
                    cloze_id=cloze.id,
                    sentence=occ.sentence,
                    char_position=occ.char_position,
                    end_position=occ.end_position,
                    word_position=occ.word_position,
                )
            )
            added += 1

    if added:
        log.actions.append(f"补齐 {added} 条完形高频词关联")


async def finalize_paper(session, paper: ExamPaper) -> None:
    paper.import_status = "completed"
    paper.error_message = None


async def repair_target(filename: str) -> RepairLog:
    log = RepairLog(filename=filename)
    file_path = DOCX_DIR / filename
    source_expectations = infer_source_expectations(file_path)
    async with async_session_factory() as session:
        try:
            print(f"[START] {filename}", flush=True)
            paper = await get_paper(session, filename)

            if source_expectations["expects_reading"]:
                await repair_reading(session, paper, file_path, log)
                await repair_reading_enrichment(session, paper, log)
                await session.commit()
                print(f"[STEP] {filename} reading_done", flush=True)

            if source_expectations["expects_cloze"]:
                await repair_cloze_points(session, paper, log)
                await repair_cloze_topic(session, paper, log)
                await repair_cloze_vocab(session, paper, log)
                await session.commit()
                print(f"[STEP] {filename} cloze_done", flush=True)

            if source_expectations["expects_writing"]:
                await repair_writing(session, paper, file_path, log)
                await session.commit()
                print(f"[STEP] {filename} writing_done", flush=True)

            await finalize_paper(session, paper)
            await session.commit()
            print(
                f"[DONE] {filename} | actions={'; '.join(log.actions) if log.actions else '无变更'}",
                flush=True,
            )
        except Exception as exc:
            await session.rollback()
            log.errors.append(str(exc))
            print(f"[FAIL] {filename} | {exc}", flush=True)
    return log


async def main() -> int:
    results = []
    targets = sys.argv[1:] or TARGETS
    for filename in targets:
        results.append(asdict(await repair_target(filename)))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = LOG_DIR / f"remaining_papers_repair_{timestamp}.json"
    report_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(report_path, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
