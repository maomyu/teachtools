"""
作文服务

[INPUT]: 依赖 ai_service.py、writing 模型、作文分类树分类器
[OUTPUT]: 对外提供作文列表、分类、模板、范文和讲义聚合能力
[POS]: backend/app/services 的作文业务逻辑层
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from __future__ import annotations

import json
import logging
import re
from copy import deepcopy
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.paper import ExamPaper
from app.models.writing import GRADE_OPTIONS, WritingCategory, WritingSample, WritingTask, WritingTemplate
from app.services.ai_service import QwenService
from app.services.writing_category_classifier import WritingCategoryClassifier, WritingCategoryResult


logger = logging.getLogger(__name__)

DEFAULT_WORD_TARGET = 150
SAMPLE_MIN_WORDS = 130
SAMPLE_MAX_WORDS = 170
LETTER_CATEGORY_KEYWORDS = ("信", "邮件", "回信")
SPEECH_CATEGORY_KEYWORDS = ("演讲稿", "发言稿", "倡议书", "通知")
OFFICIAL_GENERATION_MODE = "slot_fill"
QUALITY_PENDING = "pending"
QUALITY_PASSED = "passed"
QUALITY_FAILED = "failed"
PROHIBITED_PHRASE_PATTERNS = (
    r"(?i)\bDear the\b",
    r"(?i)\bI hope my ideas can be taken\b",
    r"(?i)\bis my dream and goal\b",
)
CANONICAL_TEMPLATE_CATEGORIES = {
    "活动邀请邮件",
    "建议信",
    "回信",
    "介绍信",
    "人物介绍",
    "活动介绍",
    "演讲稿",
    "通知",
    "倡议书",
    "问题解决建议",
    "意见反馈",
    "规则说明",
    "行程安排",
}


class WritingService:
    """作文服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai_service = QwenService()

    async def classify_task(
        self,
        task_or_id: WritingTask | int,
        extracted_writing_type: Optional[str] = None,
        extracted_application_type: Optional[str] = None,
    ) -> WritingCategoryResult:
        """根据数据库分类树为作文题归类。"""
        if isinstance(task_or_id, WritingTask):
            task = task_or_id
        else:
            result = await self.db.execute(select(WritingTask).where(WritingTask.id == task_or_id))
            task = result.scalar_one_or_none()

        if not task:
            return WritingCategoryResult(success=False, error="作文不存在")

        classifier = WritingCategoryClassifier(self.db)
        result = await classifier.classify(
            content=task.task_content or "",
            requirements=task.requirements or "",
            extracted_writing_type=extracted_writing_type,
            extracted_application_type=extracted_application_type,
        )

        if result.success and result.category and result.major_category and result.group_category:
            task.group_category_id = result.group_category.id
            task.major_category_id = result.major_category.id
            task.category_id = result.category.id
            task.category_confidence = result.confidence
            task.category_reasoning = result.reasoning
            task.group_category = result.group_category
            task.major_category = result.major_category
            task.category = result.category

            await self.db.flush()

        return result

    async def detect_and_update_writing_type(self, task_id: int) -> Dict:
        """重新执行作文分类并写回数据库。"""
        result = await self.classify_task(task_id)
        if not result.success:
            raise ValueError(result.error or "作文分类失败")

        await self.db.commit()
        return {
            "task_id": task_id,
            "group_category": result.group_category,
            "major_category": result.major_category,
            "category": result.category,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
        }

    def _build_sample_prompt(
        self,
        task: WritingTask,
        category: WritingCategory,
        major_category: Optional[WritingCategory],
        group_category: Optional[WritingCategory],
        template_content: str = "",
        tips: str = "",
        structure: str = "",
    ) -> str:
        """构建中考 150 词左右范文生成 Prompt。"""
        category_path = category.path
        structure_hint = f"\n通用模板：\n{template_content}\n" if template_content else ""
        structure_para_hint = f"\n模板段落结构：\n{structure}\n" if structure else ""
        tips_hint = f"\n写作提醒：\n{tips}\n" if tips else ""
        original_limit = task.word_limit or "以题目原始要求为准"
        return f"""你是北京中考英语写作教研专家。请根据下面的作文题，生成一篇适合初中生背诵迁移的高质量英文范文，并附中文翻译。

## 分类信息
- 文体组：{group_category.name if group_category else "未分类"}
- 主类：{major_category.name if major_category else "未分类"}
- 子类：{category.name}
- 分类路径：{category_path}
- 训练范文字数目标：约 {DEFAULT_WORD_TARGET} 词
- 原题字数要求：{original_limit}

## 作文题目
{task.task_content}

## 写作要求
{task.requirements or "无"}
{structure_hint}{structure_para_hint}{tips_hint}
## 生成要求
1. 输出必须是英文范文 + 中文翻译。
2. 英文部分请严格控制在 130-170 词之间，理想目标约 150 词；最佳输出区间是 145-155 词。
3. 必须覆盖题目所有关键信息点，不能遗漏原题要求。
4. 必须明显体现“{category.name}”这一子类的常见结构与表达方式。
5. 如果是信件/邮件类，必须保留称呼、正文、结尾、署名等格式感。
6. 范文要自然、地道、可迁移，适合学生背诵模板后灵活套用。
7. 即使原题只要求“不少于50词”，训练范文也必须写成 145-155 词左右的完整中考示范文，不能偷短。
8. 非书信类请优先写成 3 段、11-13 个完整英文句子；书信类请在称呼和署名之间保持 10-12 个完整英文句子。
9. 不要输出点评、不要输出字数统计、不要输出额外说明。

## 输出格式
### English Essay
[英文范文]

### Chinese Translation
[中文翻译]
"""

    def _parse_essay_with_translation(self, text: str) -> tuple[str, Optional[str]]:
        """解析 AI 返回的英文范文与中文翻译。"""
        english_essay: Optional[str] = None
        chinese_translation: Optional[str] = None

        if "### Chinese Translation" in text or "### English Essay" in text:
            essay_match = re.search(
                r"###\s*English\s*Essay\s*\n(.*?)(?=###\s*Chinese\s*Translation|$)",
                text,
                re.DOTALL | re.IGNORECASE,
            )
            translation_match = re.search(
                r"###\s*Chinese\s*Translation\s*\n(.*?)$",
                text,
                re.DOTALL | re.IGNORECASE,
            )
            if essay_match:
                english_essay = essay_match.group(1).strip()
            if translation_match:
                chinese_translation = translation_match.group(1).strip()
        elif "中文翻译" in text or "翻译" in text:
            parts = re.split(r"(?:中文翻译|翻译)\s*[:：\n]", text, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) > 1:
                english_essay = parts[0].strip()
                chinese_translation = parts[1].strip()

        if not english_essay:
            english_essay = text.strip()

        return english_essay, chinese_translation

    def _count_english_words(self, text: str) -> int:
        return len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text or ""))

    def _normalize_similarity_text(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
        normalized = re.sub(r"[^a-z0-9 ,.?!']", "", normalized)
        return normalized.strip()

    def _essay_similarity(self, left: str, right: str) -> float:
        left_normalized = self._normalize_similarity_text(left)
        right_normalized = self._normalize_similarity_text(right)
        if not left_normalized or not right_normalized:
            return 0.0
        return SequenceMatcher(None, left_normalized, right_normalized).ratio()

    async def _load_peer_sample_contexts(
        self,
        *,
        category_id: int,
        exclude_task_id: Optional[int] = None,
        limit: int = 3,
    ) -> List[Dict[str, str]]:
        """加载同子类下已通过质检的其他真题范文，用于避免不同试卷生成出近似文章。"""
        query = (
            select(
                WritingSample.sample_content,
                WritingTask.task_content,
                WritingTask.requirements,
                WritingTask.id.label("task_id"),
            )
            .join(WritingTask, WritingTask.id == WritingSample.task_id)
            .where(WritingTask.category_id == category_id)
            .where(WritingSample.quality_status == QUALITY_PASSED)
            .where(WritingSample.generation_mode == OFFICIAL_GENERATION_MODE)
            .order_by(WritingSample.id.desc())
            .limit(max(limit * 2, limit))
        )
        if exclude_task_id is not None:
            query = query.where(WritingTask.id != exclude_task_id)

        result = await self.db.execute(query)
        items: List[Dict[str, str]] = []
        for sample_content, task_content, requirements, task_id in result.all():
            if not (sample_content or "").strip():
                continue
            items.append(
                {
                    "task_id": str(task_id),
                    "task_content": self._shorten(re.sub(r"\s+", " ", task_content or ""), 120),
                    "requirements": self._shorten(re.sub(r"\s+", " ", requirements or ""), 100),
                    "sample_excerpt": self._shorten(re.sub(r"\s+", " ", sample_content or ""), 180),
                }
            )
            if len(items) >= limit:
                break
        return items

    def _parse_json_value(self, raw_value: Any) -> Any:
        if raw_value is None:
            return None
        if isinstance(raw_value, (dict, list)):
            return raw_value
        if isinstance(raw_value, str):
            stripped = raw_value.strip()
            if not stripped:
                return None
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return None
        return None

    def _extract_placeholder_labels(self, text: str) -> List[str]:
        return re.findall(r"\[[^\]]+\]", text or "")

    def _split_template_sentences(self, paragraph_text: str) -> List[str]:
        lines = [line.strip() for line in re.split(r"\n+", paragraph_text or "") if line.strip()]
        if len(lines) > 1:
            return lines
        text = (paragraph_text or "").strip()
        if not text:
            return []
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]

    def _split_essay_sentences(self, paragraph_text: str) -> List[str]:
        text = (paragraph_text or "").strip()
        if text.lower().startswith("dear "):
            text = re.sub(r"^(Dear [^,\n]+,)\s+", r"\1\n", text, count=1, flags=re.IGNORECASE)
        text = re.sub(
            r"\s+(Yours sincerely,|Best wishes,|Yours,|Sincerely,)",
            r"\n\1",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"(Yours sincerely,|Best wishes,|Yours,|Sincerely,)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)$",
            r"\1\n\2",
            text,
            flags=re.IGNORECASE,
        )
        lines = [line.strip() for line in re.split(r"\n+", text) if line.strip()]
        if len(lines) > 1:
            return lines
        if not text:
            return []
        parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
        return parts or [text]

    def _expand_segments_to_target(self, segments: List[str], target: int) -> List[str]:
        expanded = [segment.strip() for segment in segments if segment and segment.strip()]
        while len(expanded) < target and expanded:
            longest_index = max(range(len(expanded)), key=lambda index: len(expanded[index]))
            longest = expanded[longest_index]
            split_candidates = [
                part.strip()
                for part in re.split(r"(?<=[,;:])\s+|\s+(?=and\b|but\b|so\b|because\b)", longest, maxsplit=1, flags=re.IGNORECASE)
                if part.strip()
            ]
            if len(split_candidates) < 2:
                break
            expanded = expanded[:longest_index] + split_candidates + expanded[longest_index + 1:]
        return expanded

    def _distribute_segments_to_slot_count(self, segments: List[str], slot_count: int) -> List[str]:
        if slot_count <= 0:
            return []
        prepared = self._expand_segments_to_target(segments, slot_count)
        prepared = prepared or [""]
        if len(prepared) < slot_count:
            prepared.extend([prepared[-1]] * (slot_count - len(prepared)))

        if len(prepared) == slot_count:
            return prepared

        groups: List[str] = []
        total_segments = len(prepared)
        base = total_segments // slot_count
        remainder = total_segments % slot_count
        cursor = 0
        for index in range(slot_count):
            take = base + (1 if index < remainder else 0)
            chunk = prepared[cursor: cursor + take]
            cursor += take
            groups.append(" ".join(chunk).strip())
        return groups

    def _build_rendered_slots_from_essay(
        self,
        schema: Dict[str, Any],
        essay: str,
    ) -> Dict[str, Any]:
        essay_paragraphs = [part.strip() for part in re.split(r"\n\s*\n", essay or "") if part.strip()]
        schema_paragraphs = schema.get("paragraphs") or []
        rendered_paragraphs: List[Dict[str, Any]] = []

        if len(essay_paragraphs) == len(schema_paragraphs):
            paragraph_sentence_groups = [
                self._split_essay_sentences(paragraph_text)
                for paragraph_text in essay_paragraphs
            ]
        else:
            flat_sentences: List[str] = []
            for paragraph_text in essay_paragraphs:
                flat_sentences.extend(self._split_essay_sentences(paragraph_text))
            paragraph_sentence_groups = []
            cursor = 0
            remaining_sentences = list(flat_sentences)
            for index, schema_paragraph in enumerate(schema_paragraphs):
                slot_count = len(schema_paragraph.get("slots") or [])
                remaining_paragraphs = len(schema_paragraphs) - index
                take = max(slot_count, len(remaining_sentences) // max(remaining_paragraphs, 1))
                current = remaining_sentences[:take]
                remaining_sentences = remaining_sentences[take:]
                paragraph_sentence_groups.append(current)

        for schema_paragraph, paragraph_sentences in zip(schema_paragraphs, paragraph_sentence_groups):
            schema_slots = schema_paragraph.get("slots") or []
            grouped_sentences = self._distribute_segments_to_slot_count(paragraph_sentences, len(schema_slots))
            rendered_paragraphs.append(
                {
                    "paragraph": int(schema_paragraph.get("paragraph") or 0),
                    "slots": [
                        {
                            "slot_key": str(schema_slot.get("slot_key") or ""),
                            "rendered_text": grouped_sentences[index].strip(),
                            "placeholder_values": {},
                        }
                        for index, schema_slot in enumerate(schema_slots)
                    ],
                }
            )

        return {"paragraphs": rendered_paragraphs}

    def _build_schema_from_text_template(
        self,
        template_content: str,
        structure_text: str = "",
    ) -> Dict[str, Any]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", template_content or "") if part.strip()]
        structure_lines = [line.strip() for line in (structure_text or "").splitlines() if line.strip()]
        schema_paragraphs: List[Dict[str, Any]] = []

        for index, paragraph_text in enumerate(paragraphs, start=1):
            purpose = ""
            word_range = ""
            if index - 1 < len(structure_lines):
                structure_line = structure_lines[index - 1]
                purpose_match = re.search(r"第\d+段[:：]?\s*(.+?)(?:（|$)", structure_line)
                if purpose_match:
                    purpose = purpose_match.group(1).strip()
                range_match = re.search(r"(\d+\s*-\s*\d+)", structure_line)
                if range_match:
                    word_range = range_match.group(1).replace(" ", "")

            sentences = self._split_template_sentences(paragraph_text)
            slots = []
            for sentence_index, sentence in enumerate(sentences, start=1):
                slot_key = f"p{index}_s{sentence_index}"
                slots.append(
                    {
                        "slot_key": slot_key,
                        "purpose": purpose or f"第{index}段第{sentence_index}句",
                        "required_points": [purpose] if purpose else [],
                        "fallback_pattern": sentence,
                        "placeholder_labels": self._extract_placeholder_labels(sentence),
                    }
                )

            schema_paragraphs.append(
                {
                    "paragraph": index,
                    "purpose": purpose or f"第{index}段",
                    "word_range": word_range,
                    "slots": slots,
                }
            )

        return {"format": "slot_template_v1", "paragraphs": schema_paragraphs}

    def _normalize_template_schema(
        self,
        raw_schema: Any,
        *,
        fallback_content: str = "",
        fallback_structure: str = "",
    ) -> Dict[str, Any]:
        parsed = self._parse_json_value(raw_schema)
        if not isinstance(parsed, dict):
            parsed = {}

        paragraphs = parsed.get("paragraphs")
        normalized_paragraphs: List[Dict[str, Any]] = []
        if isinstance(paragraphs, list):
            for paragraph_index, paragraph in enumerate(paragraphs, start=1):
                if not isinstance(paragraph, dict):
                    continue
                slots = []
                for slot_index, slot in enumerate(paragraph.get("slots") or [], start=1):
                    if not isinstance(slot, dict):
                        continue
                    fallback_pattern = str(slot.get("fallback_pattern") or "").strip()
                    if not fallback_pattern:
                        continue
                    # 只信任 fallback_pattern 中真实存在的占位符，避免 AI 输出伪占位符。
                    placeholder_labels = self._extract_placeholder_labels(fallback_pattern)
                    slots.append(
                        {
                            "slot_key": str(slot.get("slot_key") or f"p{paragraph_index}_s{slot_index}"),
                            "purpose": str(slot.get("purpose") or f"第{paragraph_index}段第{slot_index}句"),
                            "required_points": [str(item) for item in (slot.get("required_points") or []) if str(item).strip()],
                            "fallback_pattern": fallback_pattern,
                            "placeholder_labels": [str(item) for item in placeholder_labels if str(item).strip()],
                        }
                    )

                if slots:
                    normalized_paragraphs.append(
                        {
                            "paragraph": int(paragraph.get("paragraph") or paragraph_index),
                            "purpose": str(paragraph.get("purpose") or f"第{paragraph_index}段"),
                            "word_range": str(paragraph.get("word_range") or "").strip(),
                            "slots": slots,
                        }
                    )

        if not normalized_paragraphs:
            fallback_schema = self._build_schema_from_text_template(fallback_content, fallback_structure)
            normalized_paragraphs = fallback_schema.get("paragraphs", [])

        return {"format": "slot_template_v1", "paragraphs": normalized_paragraphs}

    def _render_template_content_from_schema(self, schema: Dict[str, Any]) -> str:
        paragraphs = []
        for paragraph in schema.get("paragraphs", []):
            slots = paragraph.get("slots") or []
            lines = [str(slot.get("fallback_pattern") or "").strip() for slot in slots if str(slot.get("fallback_pattern") or "").strip()]
            if lines:
                paragraphs.append("\n".join(lines))
        return "\n\n".join(paragraphs).strip()

    def _render_structure_text_from_schema(self, schema: Dict[str, Any]) -> str:
        lines = []
        for paragraph in schema.get("paragraphs", []):
            index = paragraph.get("paragraph")
            purpose = str(paragraph.get("purpose") or "").strip()
            word_range = str(paragraph.get("word_range") or "").strip()
            line = f"第{index}段"
            if purpose:
                line = f"{line}：{purpose}"
            if word_range:
                line = f"{line}（建议 {word_range} 词）"
            lines.append(line)
        return "\n".join(lines).strip()

    def _extract_sentence_bank_from_schema(self, schema: Dict[str, Any]) -> tuple[List[str], List[str]]:
        sentences: List[str] = []
        for paragraph in schema.get("paragraphs", []):
            for slot in paragraph.get("slots", []):
                sentence = str(slot.get("fallback_pattern") or "").strip()
                if sentence:
                    sentences.append(sentence)
        opening = sentences[: min(3, len(sentences))]
        closing = sentences[-min(3, len(sentences)):] if sentences else []
        return opening, closing

    def _count_template_slots(self, schema: Dict[str, Any]) -> int:
        return sum(len(paragraph.get("slots") or []) for paragraph in schema.get("paragraphs", []))

    def _minimum_slot_count(self, category: WritingCategory) -> int:
        path = category.path or category.name
        if any(keyword in path for keyword in LETTER_CATEGORY_KEYWORDS):
            return 10
        return 9

    def _cleanup_rendered_text(self, text: str) -> str:
        cleaned = (text or "").strip()
        cleaned = re.sub(r"(?i)^Dear the ([^,\n]+),$", r"Dear members of the \1,", cleaned)
        cleaned = re.sub(r"\s+,", ",", cleaned)
        return cleaned.strip()

    def _should_keep_multiline_paragraph(self, lines: List[str]) -> bool:
        cues = ("dear ", "best wishes", "yours", "sincerely", "li hua", "best regards")
        return any("\n" in line for line in lines) or any(
            line.strip().lower().startswith(cue)
            for line in lines
            for cue in cues
        )

    def _build_density_slots(
        self,
        category: WritingCategory,
        count: int,
    ) -> List[Dict[str, Any]]:
        path = category.path or category.name
        if any(keyword in path for keyword in LETTER_CATEGORY_KEYWORDS):
            patterns = [
                ("补充活动背景或联系场景", "In addition, [background detail] is also important for this topic."),
                ("补充具体安排或示例", "For example, [specific arrangement or example] can make the message clearer."),
                ("补充预期结果或收获", "In this way, [expected result or personal gain] can be achieved."),
                ("补充请求或期待回复", "I would really appreciate it if [specific request or expected reply]."),
            ]
        else:
            patterns = [
                ("补充背景细节", "To begin with, [background detail] made the whole experience more meaningful."),
                ("补充具体例子", "For example, [specific example or action] showed me what to do next."),
                ("补充感受或变化", "Because of this, [feeling or personal change] became stronger and clearer."),
                ("补充收获与启发", "As a result, [lesson or result] has stayed in my mind ever since."),
            ]

        slots: List[Dict[str, Any]] = []
        for index in range(count):
            purpose, fallback_pattern = patterns[index % len(patterns)]
            slots.append(
                {
                    "purpose": purpose,
                    "required_points": [purpose],
                    "fallback_pattern": fallback_pattern,
                    "placeholder_labels": self._extract_placeholder_labels(fallback_pattern),
                }
            )
        return slots

    def _ensure_minimum_slot_density(
        self,
        schema: Dict[str, Any],
        category: WritingCategory,
    ) -> Dict[str, Any]:
        minimum = self._minimum_slot_count(category)
        current = self._count_template_slots(schema)
        if current >= minimum:
            return schema

        normalized = deepcopy(schema)
        paragraphs = normalized.get("paragraphs") or []
        if not paragraphs:
            return normalized

        target_index = 1 if len(paragraphs) >= 2 else 0
        target_paragraph = paragraphs[target_index]
        existing_slots = target_paragraph.get("slots") or []
        next_slot_index = len(existing_slots) + 1
        for offset, slot in enumerate(self._build_density_slots(category, minimum - current), start=0):
            existing_slots.append(
                {
                    "slot_key": f"p{target_paragraph.get('paragraph')}_s{next_slot_index + offset}",
                    **slot,
                }
            )
        target_paragraph["slots"] = existing_slots
        return normalized

    def _normalize_placeholder_key(self, key: str) -> str:
        normalized = str(key or "").strip()
        if not normalized:
            return ""
        if normalized.startswith("[") and normalized.endswith("]"):
            return normalized
        return f"[{normalized.strip('[]')}]"

    def _normalize_placeholder_values(self, raw_values: Any) -> Dict[str, str]:
        if not isinstance(raw_values, dict):
            return {}
        normalized: Dict[str, str] = {}
        for key, value in raw_values.items():
            normalized_key = self._normalize_placeholder_key(str(key))
            normalized_value = str(value or "").strip()
            if normalized_key and normalized_value:
                normalized[normalized_key] = normalized_value
        return normalized

    def _infer_placeholder_values_from_rendered_text(
        self,
        schema_slot: Dict[str, Any],
        rendered_text: str,
    ) -> Dict[str, str]:
        fallback_pattern = str(schema_slot.get("fallback_pattern") or "").strip()
        placeholder_labels = [
            self._normalize_placeholder_key(str(label))
            for label in (schema_slot.get("placeholder_labels") or [])
            if str(label).strip()
        ]
        if not fallback_pattern or not placeholder_labels or not (rendered_text or "").strip():
            return {}

        escaped_pattern_parts: List[str] = []
        cursor = 0
        group_names: List[str] = []
        for index, placeholder in enumerate(placeholder_labels):
            placeholder_index = fallback_pattern.find(placeholder, cursor)
            if placeholder_index < 0:
                return {}
            static_text = fallback_pattern[cursor:placeholder_index]
            escaped_pattern_parts.append(re.escape(static_text))
            group_name = f"slot_{index}"
            group_names.append(group_name)
            escaped_pattern_parts.append(f"(?P<{group_name}>.+?)")
            cursor = placeholder_index + len(placeholder)
        escaped_pattern_parts.append(re.escape(fallback_pattern[cursor:]))
        regex = "^" + "".join(escaped_pattern_parts) + "$"
        match = re.match(regex, rendered_text.strip(), flags=re.DOTALL)
        if not match:
            return {}

        inferred: Dict[str, str] = {}
        for placeholder, group_name in zip(placeholder_labels, group_names):
            value = str(match.group(group_name) or "").strip()
            if value:
                inferred[placeholder] = value
        return inferred

    def _render_slot_text_from_template(
        self,
        schema_slot: Dict[str, Any],
        placeholder_values: Dict[str, str],
        source_rendered_text: str = "",
    ) -> str:
        fallback_pattern = str(schema_slot.get("fallback_pattern") or "").strip()
        placeholder_labels = [
            self._normalize_placeholder_key(str(label))
            for label in (schema_slot.get("placeholder_labels") or [])
            if str(label).strip()
        ]

        if placeholder_labels:
            rendered_text = fallback_pattern
            for placeholder in placeholder_labels:
                rendered_text = rendered_text.replace(
                    placeholder,
                    placeholder_values.get(placeholder) or placeholder,
                )
            return self._cleanup_rendered_text(rendered_text.strip())

        if source_rendered_text.strip():
            return self._cleanup_rendered_text(source_rendered_text.strip())

        return self._cleanup_rendered_text(fallback_pattern)

    def _hydrate_rendered_slots(
        self,
        schema: Dict[str, Any],
        rendered_slots: Dict[str, Any],
    ) -> Dict[str, Any]:
        paragraph_map = {
            int(paragraph.get("paragraph") or 0): paragraph
            for paragraph in rendered_slots.get("paragraphs", [])
            if isinstance(paragraph, dict)
        }
        normalized_paragraphs: List[Dict[str, Any]] = []

        for schema_paragraph in schema.get("paragraphs", []):
            paragraph_index = int(schema_paragraph.get("paragraph") or 0)
            source_paragraph = paragraph_map.get(paragraph_index, {})
            source_slot_map = {
                str(slot.get("slot_key") or ""): slot
                for slot in source_paragraph.get("slots", [])
                if isinstance(slot, dict)
            }

            normalized_slots: List[Dict[str, Any]] = []
            for schema_slot in schema_paragraph.get("slots", []):
                slot_key = str(schema_slot.get("slot_key") or "")
                source_slot = source_slot_map.get(slot_key, {})
                placeholder_values = self._normalize_placeholder_values(source_slot.get("placeholder_values"))
                source_rendered_text = str(source_slot.get("rendered_text") or "").strip()
                if not placeholder_values and source_rendered_text:
                    placeholder_values = self._infer_placeholder_values_from_rendered_text(
                        schema_slot,
                        source_rendered_text,
                    )

                rendered_text = self._render_slot_text_from_template(
                    schema_slot,
                    placeholder_values,
                    source_rendered_text,
                )

                normalized_slots.append(
                    {
                        "slot_key": slot_key,
                        "rendered_text": rendered_text,
                        "placeholder_values": placeholder_values,
                    }
                )

            normalized_paragraphs.append(
                {
                    "paragraph": paragraph_index,
                    "slots": normalized_slots,
                }
            )

        return {"paragraphs": normalized_paragraphs}

    def _render_essay_from_schema(
        self,
        schema: Dict[str, Any],
        rendered_slots: Dict[str, Any],
    ) -> str:
        rendered_slots = self._hydrate_rendered_slots(schema, rendered_slots)
        paragraph_map = {
            int(paragraph.get("paragraph") or 0): paragraph
            for paragraph in rendered_slots.get("paragraphs", [])
            if isinstance(paragraph, dict)
        }
        rendered_paragraphs: List[str] = []

        for schema_paragraph in schema.get("paragraphs", []):
            paragraph_index = int(schema_paragraph.get("paragraph") or 0)
            rendered_paragraph = paragraph_map.get(paragraph_index, {})
            slot_map = {
                str(slot.get("slot_key") or ""): slot
                for slot in rendered_paragraph.get("slots", [])
                if isinstance(slot, dict)
            }
            lines: List[str] = []
            for slot in schema_paragraph.get("slots", []):
                slot_key = str(slot.get("slot_key") or "")
                rendered_slot = slot_map.get(slot_key, {})
                rendered_text = str(rendered_slot.get("rendered_text") or "").strip()
                if rendered_text:
                    lines.append(rendered_text)
            cleaned_lines = [line.strip() for line in lines if line and line.strip()]
            if not cleaned_lines:
                continue
            if len(cleaned_lines) == 1:
                paragraph_text = cleaned_lines[0]
            elif self._should_keep_multiline_paragraph(cleaned_lines):
                paragraph_text = "\n".join(cleaned_lines)
            else:
                paragraph_text = " ".join(cleaned_lines)
            rendered_paragraphs.append(paragraph_text.strip())

        return "\n\n".join([paragraph for paragraph in rendered_paragraphs if paragraph.strip()]).strip()

    def _build_slot_fill_prompt(
        self,
        task: WritingTask,
        category: WritingCategory,
        major_category: Optional[WritingCategory],
        group_category: Optional[WritingCategory],
        template: WritingTemplate,
        template_schema: Dict[str, Any],
        peer_samples: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        original_limit = task.word_limit or "以题目原始要求为准"
        schema_text = json.dumps(template_schema, ensure_ascii=False, indent=2)
        peer_sample_block = ""
        if peer_samples:
            peer_lines = []
            for index, item in enumerate(peer_samples, start=1):
                peer_lines.append(
                    f"{index}. 真题：{item['task_content']}\n"
                    f"   要求：{item['requirements'] or '无'}\n"
                    f"   已有范文片段：{item['sample_excerpt']}"
                )
            peer_sample_block = (
                "\n## 同子类已有真题范文（只用于避免写得太像）\n"
                + "\n".join(peer_lines)
                + "\n"
            )
        return f"""你是北京中考英语写作模板填充专家。请严格根据给定模板骨架，为这道作文题逐槽位填充值。

## 分类信息
- 文体组：{group_category.name if group_category else "未分类"}
- 主类：{major_category.name if major_category else "未分类"}
- 子类：{category.name}
- 分类路径：{category.path}
- 训练范文字数目标：约 {DEFAULT_WORD_TARGET} 词
- 原题字数要求：{original_limit}

## 作文题目
{task.task_content}

## 写作要求
{task.requirements or "无"}

## 子类模板名称
{template.template_name}

## 严格模板骨架
```json
{schema_text}
```
{peer_sample_block}

## 填充要求
1. 你只能按上面的 paragraph 和 slot_key 顺序输出，不能新增、删除或改名。
2. 对于带占位符的模板句，你必须保留模板句骨架本身，只能填写 placeholder_values；rendered_text 必须等于“fallback_pattern 替换占位符后的最终句子”，不能改写句骨架。
3. 对于没有占位符的模板句，rendered_text 必须保留该模板句本身，或只做极少量格式性调整。
4. placeholder_values 里只能放“纯占位内容”，不能把模板里已经存在的引导词重复写进去。
5. 最终渲染出的整篇英文作文必须能覆盖题目要求，并且整体字数要落在 130-170 词之间。
6. 书信/邮件类必须保留称呼、正文、结尾、署名槽位；不能把书信写成普通短文。
7. 除标题、日期、称呼、署名外，其余正文信息 slot 请尽量写成 12-24 个英文词的完整表达，优先补足原因、细节、感受、结果和期待，避免只写空泛套话。
8. 绝对不要写出 Dear the ...、I hope my ideas can be taken、My dream school is my dream and goal 这类不自然表达。
9. 如果上面给了“同子类已有真题范文”，你必须写出明显不同的场景细节、理由、例子和感受，不能只是改几个词后复用同一篇内容。
10. 只输出 JSON，不要输出解释。

## 输出格式
```json
{{
  "paragraphs": [
    {{
      "paragraph": 1,
      "slots": [
        {{
          "slot_key": "p1_s1",
          "rendered_text": "Dear Peter,",
          "placeholder_values": {{"[recipient]": "Peter"}}
        }},
        {{
          "slot_key": "p1_s2",
          "rendered_text": "I am writing to invite you to our English festival next Friday.",
          "placeholder_values": {{"[purpose]": "invite you to our English festival next Friday"}}
        }}
      ]
    }}
  ]
}}
```"""

    def _build_slot_expand_prompt(
        self,
        task: WritingTask,
        template_schema: Dict[str, Any],
        rendered_slots: Dict[str, Any],
        current_word_count: int,
    ) -> str:
        target_low = max(SAMPLE_MIN_WORDS, DEFAULT_WORD_TARGET - 5)
        target_high = min(SAMPLE_MAX_WORDS, DEFAULT_WORD_TARGET + 10)
        missing_words = max(0, target_low - current_word_count)
        current_essay = self._render_essay_from_schema(template_schema, rendered_slots)
        return f"""你是北京中考英语写作扩写专家。下面这道作文已经按固定模板槽位填好，但当前渲染后只有 {current_word_count} 词，偏短。

请在不改变 paragraph 数量、slot_key、slot 顺序的前提下，只通过扩充 placeholder_values 或 rendered_text，让最终英文作文达到 {target_low}-{target_high} 词，理想约 {DEFAULT_WORD_TARGET} 词。
当前至少还需要补足约 {missing_words} 个英文词。

## 原题
{task.task_content}

## 写作要求
{task.requirements or "无"}

## 当前英文成文
```text
{current_essay}
```

## 模板骨架
```json
{json.dumps(template_schema, ensure_ascii=False, indent=2)}
```

## 当前槽位填充
```json
{json.dumps(rendered_slots, ensure_ascii=False, indent=2)}
```

## 扩写要求
1. 不能新增、删除、重排任何 paragraph 或 slot_key。
2. 对于带占位符的模板句，只能扩充 placeholder_values，让 rendered_text 继续等于“模板句骨架 + 替换后的占位内容”。
3. 尽量补足背景、原因、细节、感受、结果、期待。
4. 不能把模板句骨架整体改写成另一种句子。
5. 标题、日期、称呼、署名类 slot 可以简短；其余正文信息 slot 请尽量扩到 12-24 个英文词，并优先写成“信息 + 细节/原因/结果”的完整表达。
6. 如果是通知、演讲稿、倡议书、建议信、回信等应用文，请把“原因、安排、规则、建议、期待”写得更具体，避免只写一句很短的泛泛提醒。
7. 只输出更新后的 JSON，不要解释。
"""

    async def _expand_rendered_slots_to_target(
        self,
        *,
        task_content: str,
        requirements: str,
        word_limit: Optional[str],
        category: WritingCategory,
        major_category: Optional[WritingCategory],
        group_category: Optional[WritingCategory],
        template_schema: Dict[str, Any],
        rendered_slots: Dict[str, Any],
        current_word_count: int,
        operation_prefix: str,
        peer_samples: Optional[List[Dict[str, str]]] = None,
    ) -> tuple[Dict[str, Any], str, int, List[str]]:
        """在不改模板骨架的前提下，多轮扩充 slot 填充值直到达到目标字数。"""
        latest_slots = rendered_slots
        latest_essay = self._render_essay_from_schema(template_schema, latest_slots)
        latest_word_count = current_word_count
        latest_issues = self._detect_quality_issues(
            essay=latest_essay,
            category=category,
            template_schema=template_schema,
            rendered_slots=latest_slots,
            peer_samples=peer_samples,
        )
        expand_prompt = self._build_slot_expand_prompt(
            task=WritingTask(
                task_content=task_content,
                requirements=requirements,
                word_limit=word_limit,
            ),
            template_schema=template_schema,
            rendered_slots=latest_slots,
            current_word_count=current_word_count,
        )

        for attempt in range(3):
            expand_text = await self.ai_service.chat_async(
                expand_prompt,
                system_prompt="你是严格保持模板槽位不变的英文扩写专家。",
                operation=f"{operation_prefix}.expand_slots_{attempt + 1}",
            )
            expanded_slots = self._hydrate_rendered_slots(
                template_schema,
                self._parse_slot_fill_result(expand_text),
            )
            if not self._validate_rendered_slots(template_schema, expanded_slots, category=category):
                expand_prompt += "\n\n⚠️ 上一次扩写没有保持模板槽位和句骨架完全一致，请只扩充占位内容后重试。"
                continue

            hydrated_slots = expanded_slots
            expanded_essay = self._render_essay_from_schema(template_schema, hydrated_slots)
            expanded_word_count = self._count_english_words(expanded_essay)
            expanded_issues = self._detect_quality_issues(
                essay=expanded_essay,
                category=category,
                template_schema=template_schema,
                rendered_slots=hydrated_slots,
                peer_samples=peer_samples,
            )

            latest_slots = hydrated_slots
            latest_essay = expanded_essay
            latest_word_count = expanded_word_count
            latest_issues = expanded_issues

            if not any("字数不在" in issue for issue in expanded_issues):
                return latest_slots, latest_essay, latest_word_count, latest_issues

            expand_prompt = self._build_slot_expand_prompt(
                task=WritingTask(
                    task_content=task_content,
                    requirements=requirements,
                    word_limit=word_limit,
                ),
                template_schema=template_schema,
                rendered_slots=latest_slots,
                current_word_count=latest_word_count,
            )
            expand_prompt += (
                "\n\n⚠️ 这次扩写后仍然没有进入 130-170 词。"
                "请继续保持模板句骨架不变，只把各 slot 的占位内容写得更具体、更完整。"
            )

        return latest_slots, latest_essay, latest_word_count, latest_issues

    def _parse_slot_fill_result(self, result_text: str) -> Dict[str, Any]:
        if not result_text:
            return {}
        json_match = re.search(r"\{.*\}", result_text, re.DOTALL)
        if not json_match:
            return {}
        try:
            parsed = json.loads(json_match.group())
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _validate_rendered_slots(
        self,
        template_schema: Dict[str, Any],
        rendered_slots: Dict[str, Any],
        *,
        category: Optional[WritingCategory] = None,
    ) -> bool:
        rendered_paragraphs = rendered_slots.get("paragraphs")
        if not isinstance(rendered_paragraphs, list):
            return False

        schema_paragraphs = template_schema.get("paragraphs", [])
        if len(rendered_paragraphs) != len(schema_paragraphs):
            return False

        paragraph_map = {
            int(item.get("paragraph") or 0): item
            for item in rendered_paragraphs
            if isinstance(item, dict)
        }

        ordered_slot_texts: List[str] = []
        for schema_paragraph in schema_paragraphs:
            paragraph_index = int(schema_paragraph.get("paragraph") or 0)
            rendered_paragraph = paragraph_map.get(paragraph_index)
            if not rendered_paragraph:
                return False

            rendered_slot_items = [
                slot
                for slot in rendered_paragraph.get("slots", [])
                if isinstance(slot, dict)
            ]
            schema_slots = schema_paragraph.get("slots") or []
            if len(rendered_slot_items) != len(schema_slots):
                return False

            for index, schema_slot in enumerate(schema_slots):
                slot_key = str(schema_slot.get("slot_key") or "")
                rendered_slot = rendered_slot_items[index]
                if str(rendered_slot.get("slot_key") or "") != slot_key:
                    return False
                rendered_text = str(rendered_slot.get("rendered_text") or "").strip()
                if not rendered_text:
                    return False
                if self._extract_placeholder_labels(rendered_text):
                    return False
                placeholder_values = self._normalize_placeholder_values(rendered_slot.get("placeholder_values"))
                if not placeholder_values:
                    placeholder_values = self._infer_placeholder_values_from_rendered_text(
                        schema_slot,
                        rendered_text,
                    )
                expected_text = self._render_slot_text_from_template(
                    schema_slot,
                    placeholder_values,
                    rendered_text,
                )
                if expected_text != self._cleanup_rendered_text(rendered_text):
                    return False
                if any(
                    not placeholder_values.get(self._normalize_placeholder_key(str(label)))
                    for label in (schema_slot.get("placeholder_labels") or [])
                    if str(label).strip()
                ):
                    return False
                ordered_slot_texts.append(rendered_text)

        if category:
            ordered_text = "\n".join(ordered_slot_texts)
            is_letter = any(keyword in (category.path or category.name) for keyword in LETTER_CATEGORY_KEYWORDS)
            is_speech = any(keyword in (category.path or category.name) for keyword in SPEECH_CATEGORY_KEYWORDS)
            if is_letter:
                if not ordered_slot_texts or not re.match(r"(?i)^Dear\b.+,$", ordered_slot_texts[0].strip()):
                    return False
                if not any(
                    re.match(
                        r"(?is)^(Best wishes,|Yours sincerely,|Yours,|Sincerely,|Best regards,)(\s*\n.+)?$",
                        text.strip(),
                    )
                    for text in ordered_slot_texts[-3:]
                ):
                    return False
            else:
                if re.search(r"(?i)^Dear\b", ordered_text):
                    return False
            if is_speech and re.search(r"(?i)^Dear\b", ordered_text):
                return False
        return True

    def _detect_quality_issues(
        self,
        *,
        essay: str,
        category: WritingCategory,
        template_schema: Dict[str, Any],
        rendered_slots: Dict[str, Any],
        peer_samples: Optional[List[Dict[str, str]]] = None,
    ) -> List[str]:
        issues: List[str] = []
        if not essay.strip():
            return ["英文范文为空"]

        if self._extract_placeholder_labels(essay):
            issues.append("仍有未替换占位符")

        for pattern in PROHIBITED_PHRASE_PATTERNS:
            if re.search(pattern, essay):
                issues.append(f"命中禁用表达: {pattern}")

        for exact_phrase in (
            "I would like to mention It",
            "is also worth noting.",
            "I hope my ideas can be taken.",
            "My dream school is my dream and goal.",
        ):
            if exact_phrase in essay:
                issues.append(f"命中不自然表达: {exact_phrase}")

        sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", essay) if sentence.strip()]
        duplicates = [sentence for sentence in set(sentences) if sentences.count(sentence) > 1]
        if duplicates:
            issues.append("存在重复句")

        is_letter = any(keyword in (category.path or category.name) for keyword in LETTER_CATEGORY_KEYWORDS)
        if is_letter:
            if not essay.strip().startswith("Dear "):
                issues.append("书信类缺少自然称呼")
            if "Dear the " in essay:
                issues.append("书信称呼不自然")
            if not re.search(r"(?im)^(Best wishes,|Yours sincerely,|Yours,|Sincerely,|Best regards,)\s*$", essay):
                issues.append("书信类缺少自然收尾")
        else:
            if re.search(r"(?im)^Dear\b", essay):
                issues.append("非书信类误用了书信格式")

        if not self._validate_rendered_slots(template_schema, rendered_slots, category=category):
            issues.append("槽位结构与模板骨架不一致")

        word_count = self._count_english_words(essay)
        if word_count < SAMPLE_MIN_WORDS or word_count > SAMPLE_MAX_WORDS:
            issues.append(f"字数不在 {SAMPLE_MIN_WORDS}-{SAMPLE_MAX_WORDS} 词之间")

        if peer_samples:
            highest_similarity = 0.0
            for item in peer_samples:
                similarity = self._essay_similarity(essay, item.get("sample_excerpt") or "")
                highest_similarity = max(highest_similarity, similarity)
            if highest_similarity >= 0.86:
                issues.append(f"与同子类既有真题范文过于相似（{highest_similarity:.2f}）")

        return list(dict.fromkeys(issues))

    def _build_slot_review_prompt(
        self,
        *,
        task_content: str,
        requirements: str,
        category: WritingCategory,
        major_category: Optional[WritingCategory],
        group_category: Optional[WritingCategory],
        template_schema: Dict[str, Any],
        rendered_slots: Dict[str, Any],
        issues: List[str],
        word_count: int,
        peer_samples: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        peer_sample_block = ""
        if peer_samples:
            peer_lines = []
            for index, item in enumerate(peer_samples, start=1):
                peer_lines.append(
                    f"{index}. 真题：{item['task_content']}\n"
                    f"   范文片段：{item['sample_excerpt']}"
                )
            peer_sample_block = (
                "\n## 同子类已有真题范文（请避免写得过于相似）\n"
                + "\n".join(peer_lines)
                + "\n"
            )
        return f"""你是北京中考英语写作教研审稿专家。下面这篇作文已经按固定模板槽位填充完成，但还需要做最终英语质检。

请只修改各 slot 的 rendered_text，使最终作文：
1. 继续完全遵守原 paragraph 和 slot_key；
2. 英语自然、地道、适合初中生背诵迁移；
3. 严格符合“{category.path}”这个子类；
4. 最终字数保持在 {SAMPLE_MIN_WORDS}-{SAMPLE_MAX_WORDS} 词之间，理想约 {DEFAULT_WORD_TARGET} 词；
5. 不能出现 Dear the、I hope my ideas can be taken、My dream school is my dream and goal 这类表达。

## 分类信息
- 文体组：{group_category.name if group_category else "未分类"}
- 主类：{major_category.name if major_category else "未分类"}
- 子类：{category.name}
- 分类路径：{category.path}

## 题目
{task_content}

## 写作要求
{requirements or "无"}

## 模板骨架
```json
{json.dumps(template_schema, ensure_ascii=False, indent=2)}
```

## 当前槽位填充
```json
{json.dumps(rendered_slots, ensure_ascii=False, indent=2)}
```
{peer_sample_block}

## 当前问题
- 当前字数：{word_count}
- 需要修正：{"；".join(issues) if issues else "无，但请继续提升为教研级英文"}

## 输出要求
1. 只能输出 JSON。
2. 不能新增、删除、重排 paragraph 或 slot。
3. 对于带占位符的模板句，只能修正 placeholder_values，并让 rendered_text 严格等于模板句骨架填充后的结果。
4. 每个 slot 都必须是完整、自然、功能明确的英文句子或格式行。
5. 如果给了同子类其他真题范文，请确保本题的细节、理由、事件安排、情感变化和结尾表达与它们明显不同。
"""

    async def _generate_slot_filled_official_sample(
        self,
        *,
        task_content: str,
        requirements: str,
        word_limit: Optional[str],
        category: WritingCategory,
        major_category: Optional[WritingCategory],
        group_category: Optional[WritingCategory],
        template: WritingTemplate,
        template_schema: Dict[str, Any],
        operation_prefix: str,
        peer_samples: Optional[List[Dict[str, str]]] = None,
        allow_peerless_fallback: bool = True,
    ) -> tuple[Dict[str, Any], str, int, str]:
        prompt = self._build_slot_fill_prompt(
            task=WritingTask(
                task_content=task_content,
                requirements=requirements,
                word_limit=word_limit,
            ),
            category=category,
            major_category=major_category,
            group_category=group_category,
            template=template,
            template_schema=template_schema,
            peer_samples=peer_samples,
        )

        last_issues: List[str] = []
        for attempt in range(3):
            result_text = await self.ai_service.chat_async(
                prompt,
                system_prompt="你是严格执行模板骨架的北京中考英语写作专家。",
                operation=f"{operation_prefix}.generate_slots",
            )
            rendered_slots = self._hydrate_rendered_slots(
                template_schema,
                self._parse_slot_fill_result(result_text),
            )
            if not self._validate_rendered_slots(template_schema, rendered_slots, category=category):
                prompt += "\n\n⚠️ 上一次输出没有严格遵守模板槽位顺序，请逐 paragraph / slot_key 原样重试。"
                continue

            essay = self._render_essay_from_schema(template_schema, rendered_slots)
            word_count = self._count_english_words(essay)
            issues = self._detect_quality_issues(
                essay=essay,
                category=category,
                template_schema=template_schema,
                rendered_slots=rendered_slots,
                peer_samples=peer_samples,
            )
            if any("字数不在" in issue for issue in issues):
                rendered_slots, essay, word_count, issues = await self._expand_rendered_slots_to_target(
                    task_content=task_content,
                    requirements=requirements,
                    word_limit=word_limit,
                    category=category,
                    major_category=major_category,
                    group_category=group_category,
                    template_schema=template_schema,
                    rendered_slots=rendered_slots,
                    current_word_count=word_count,
                    operation_prefix=operation_prefix,
                    peer_samples=peer_samples,
                )
            if issues:
                review_prompt = self._build_slot_review_prompt(
                    task_content=task_content,
                    requirements=requirements,
                    category=category,
                    major_category=major_category,
                    group_category=group_category,
                    template_schema=template_schema,
                    rendered_slots=rendered_slots,
                    issues=issues,
                    word_count=word_count,
                    peer_samples=peer_samples,
                )
                review_text = await self.ai_service.chat_async(
                    review_prompt,
                    system_prompt="你是只允许改写槽位文本的英语写作审稿专家。",
                    operation=f"{operation_prefix}.review_slots",
                )
                reviewed_slots = self._hydrate_rendered_slots(
                    template_schema,
                    self._parse_slot_fill_result(review_text),
                )
                if self._validate_rendered_slots(template_schema, reviewed_slots, category=category):
                    rendered_slots = reviewed_slots
                    essay = self._render_essay_from_schema(template_schema, rendered_slots)
                    word_count = self._count_english_words(essay)
                    issues = self._detect_quality_issues(
                        essay=essay,
                        category=category,
                        template_schema=template_schema,
                        rendered_slots=rendered_slots,
                        peer_samples=peer_samples,
                    )
            if not issues:
                translation = await self._translate_essay(essay)
                if not translation or not translation.strip():
                    raise ValueError("AI 生成范文失败：中文翻译为空")
                return rendered_slots, essay, word_count, translation

            last_issues = issues
            prompt += (
                "\n\n⚠️ 上一次结果仍未达标："
                + "；".join(issues)
                + "。请继续保持 paragraph 和 slot_key 完全不变，只修正 rendered_text。"
            )

        if allow_peerless_fallback and peer_samples:
            logger.info(
                "正式范文生成退回无同类参考模式 category=%s template_id=%s",
                category.path,
                template.id,
            )
            return await self._generate_slot_filled_official_sample(
                task_content=task_content,
                requirements=requirements,
                word_limit=word_limit,
                category=category,
                major_category=major_category,
                group_category=group_category,
                template=template,
                template_schema=template_schema,
                operation_prefix=operation_prefix,
                peer_samples=None,
                allow_peerless_fallback=False,
            )

        raise ValueError("AI 生成范文失败：" + ("；".join(last_issues) if last_issues else "槽位输出未通过质检"))

    async def _translate_essay(self, essay: str) -> str:
        prompt = f"请将下面英文范文翻译成自然流畅的中文，保持段落对应，并只输出中文翻译：\n\n{essay}"
        return await self.ai_service.chat_async(
            prompt,
            system_prompt="你是专业英汉翻译。",
            operation="writing_service.translate_sample",
        )

    def _sample_meets_quality_bar(
        self,
        sample: Optional[WritingSample],
        *,
        expected_template_id: Optional[int] = None,
        template: Optional[WritingTemplate] = None,
    ) -> bool:
        """判断现有范文是否满足当前质量门槛。"""
        if not sample:
            return False

        if expected_template_id and sample.template_id != expected_template_id:
            return False

        if not sample.sample_content or not sample.sample_content.strip():
            return False

        if not sample.translation or not sample.translation.strip():
            return False

        if (sample.generation_mode or "").strip() != OFFICIAL_GENERATION_MODE:
            return False

        if (sample.quality_status or "").strip() != QUALITY_PASSED:
            return False

        actual_word_count = sample.word_count or self._count_english_words(sample.sample_content)
        if not (SAMPLE_MIN_WORDS <= actual_word_count <= SAMPLE_MAX_WORDS):
            return False

        if template is not None:
            if sample.template_version != (template.template_version or 1):
                return False
            template_schema = self._normalize_template_schema(
                template.template_schema_json,
                fallback_content=template.template_content or "",
                fallback_structure=template.structure or "",
            )
            rendered_slots = self._hydrate_rendered_slots(
                template_schema,
                self._parse_json_value(sample.rendered_slots_json) or {},
            )
            if not isinstance(rendered_slots, dict):
                return False
            if not self._validate_rendered_slots(template_schema, rendered_slots, category=template.category):
                return False
            rendered_essay = self._render_essay_from_schema(template_schema, rendered_slots)
            if rendered_essay.strip() != (sample.sample_content or "").strip():
                return False
            if self._detect_quality_issues(
                essay=rendered_essay,
                category=template.category,
                template_schema=template_schema,
                rendered_slots=rendered_slots,
            ):
                return False

        return True

    def _select_official_sample(
        self,
        samples: Optional[List[WritingSample]],
        *,
        template: Optional[WritingTemplate] = None,
        expected_template_id: Optional[int] = None,
    ) -> Optional[WritingSample]:
        ordered_samples = sorted(samples or [], key=lambda item: item.id or 0, reverse=True)
        for sample in ordered_samples:
            if self._sample_meets_quality_bar(
                sample,
                expected_template_id=expected_template_id,
                template=template,
            ):
                return sample
        return None

    def _select_display_sample(
        self,
        samples: Optional[List[WritingSample]],
        *,
        template: Optional[WritingTemplate] = None,
        expected_template_id: Optional[int] = None,
    ) -> Optional[WritingSample]:
        """读接口只返回当前模板版本下的正式范文。"""
        return self._select_official_sample(
            samples,
            template=template,
            expected_template_id=expected_template_id,
        )

    def _sample_display_quality_status(
        self,
        sample: Optional[WritingSample],
        *,
        template: Optional[WritingTemplate] = None,
        expected_template_id: Optional[int] = None,
    ) -> str:
        if not sample:
            return QUALITY_PENDING
        if self._sample_meets_quality_bar(
            sample,
            expected_template_id=expected_template_id,
            template=template,
        ):
            return sample.quality_status or QUALITY_PASSED
        return QUALITY_PENDING

    def _repair_sample_from_rendered_slots(
        self,
        sample: WritingSample,
        template: WritingTemplate,
    ) -> bool:
        template_schema = self._normalize_template_schema(
            template.template_schema_json,
            fallback_content=template.template_content or "",
            fallback_structure=template.structure or "",
        )
        rendered_slots = self._hydrate_rendered_slots(
            template_schema,
            self._parse_json_value(sample.rendered_slots_json) or {},
        )
        if not isinstance(rendered_slots, dict):
            return False
        if not self._validate_rendered_slots(template_schema, rendered_slots, category=template.category):
            return False

        rendered_essay = self._render_essay_from_schema(template_schema, rendered_slots)
        word_count = self._count_english_words(rendered_essay)
        if (
            not rendered_essay.strip()
            or not (SAMPLE_MIN_WORDS <= word_count <= SAMPLE_MAX_WORDS)
            or self._detect_quality_issues(
                essay=rendered_essay,
                category=template.category,
                template_schema=template_schema,
                rendered_slots=rendered_slots,
            )
        ):
            return False

        sample.sample_content = rendered_essay
        sample.word_count = word_count
        sample.template_id = template.id
        sample.template_version = template.template_version or 1
        sample.generation_mode = OFFICIAL_GENERATION_MODE
        sample.quality_status = QUALITY_PASSED
        return True

    async def _revise_essay_length(
        self,
        essay: str,
        task: WritingTask,
        category: WritingCategory,
        major_category: Optional[WritingCategory],
        group_category: Optional[WritingCategory],
        min_words: int = SAMPLE_MIN_WORDS,
        max_words: int = SAMPLE_MAX_WORDS,
    ) -> tuple[str, int]:
        """在首轮生成不达标时，强制扩写/压缩到目标字数范围。"""
        if not essay:
            return essay, 0

        current_word_count = self._count_english_words(essay)
        if min_words <= current_word_count <= max_words:
            return essay, current_word_count

        action = "扩写" if current_word_count < min_words else "压缩"
        length_guidance = (
            "请增加必要的背景、原因、细节、感受或期待，确保至少 11 个完整英文句子，并且最终不少于 "
            f"{min_words} 词，理想区间为 145-155 词。"
            if current_word_count < min_words
            else f"请在保留要点的前提下删去冗余表达，确保最终不超过 {max_words} 词，理想区间为 145-155 词。"
        )
        prompt = f"""你是北京中考英语写作改写专家。请在不改变作文任务和文体格式的前提下，把下面这篇英文作文{action}到 {min_words}-{max_words} 词之间。

## 分类信息
- 文体组：{group_category.name if group_category else "未分类"}
- 主类：{major_category.name if major_category else "未分类"}
- 子类：{category.name}
- 分类路径：{category.path}

## 原题
{task.task_content}

## 写作要求
{task.requirements or "无"}

## 当前作文
{essay}

## 改写要求
1. 只输出英文作文，不要输出中文翻译、标题、字数统计或解释。
2. 保留该子类应有的格式感，比如信件称呼、正文、结尾、署名。
3. 不要丢失原题关键信息点。
4. 最终控制在 {min_words}-{max_words} 词之间，理想目标约 150 词，最佳区间 145-155 词。
5. 非书信类优先保持 3 段、11-13 个完整英文句子；书信类保持 10-12 个完整英文句子。
6. {length_guidance}
"""

        revised_text = await self.ai_service.chat_async(
            prompt,
            system_prompt="你是严格控制中考英语作文篇幅的英文改写专家。",
            operation="writing_service.revise_sample_length",
        )
        revised_essay, _ = self._parse_essay_with_translation(revised_text or "")
        revised_word_count = self._count_english_words(revised_essay)
        return revised_essay or essay, revised_word_count or current_word_count

    async def generate_sample(
        self,
        task_id: int,
        template_id: Optional[int] = None,
        score_level: str = "一档",
        force_template_refresh: bool = False,
    ) -> WritingSample:
        """按作文子类模板逐槽位生成正式范文。"""
        result = await self.db.execute(
            select(WritingTask)
            .options(
                selectinload(WritingTask.samples),
                selectinload(WritingTask.paper),
                selectinload(WritingTask.category),
                selectinload(WritingTask.major_category),
                selectinload(WritingTask.group_category),
            )
            .where(WritingTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"作文不存在: {task_id}")

        if not task.category_id:
            category_result = await self.classify_task(task)
            if not category_result.success or not category_result.category:
                raise ValueError(category_result.error or "作文分类失败")

        category = task.category
        if category is None and task.category_id:
            category = await self.db.get(WritingCategory, task.category_id)
        major_category = task.major_category
        if major_category is None and task.major_category_id:
            major_category = await self.db.get(WritingCategory, task.major_category_id)
        group_category = task.group_category
        if group_category is None and task.group_category_id:
            group_category = await self.db.get(WritingCategory, task.group_category_id)

        template: Optional[WritingTemplate] = None
        if template_id:
            template_result = await self.db.execute(
                select(WritingTemplate)
                .options(selectinload(WritingTemplate.category))
                .where(WritingTemplate.id == template_id)
            )
            template = template_result.scalar_one_or_none()
        if template is None:
            template = await self.get_or_create_template(
                task.category_id,
                anchor_task=task,
                force_refresh=force_template_refresh,
                refresh_if_stale=force_template_refresh,
            )

        template_schema = self._normalize_template_schema(
            template.template_schema_json,
            fallback_content=template.template_content or "",
            fallback_structure=template.structure or "",
        )
        if not template_schema.get("paragraphs"):
            raise ValueError("作文模板骨架为空，无法生成正式范文")

        peer_samples = await self._load_peer_sample_contexts(
            category_id=task.category_id,
            exclude_task_id=task.id,
            limit=3,
        )
        rendered_slots, english_essay, word_count, chinese_translation = await self._generate_slot_filled_official_sample(
            task_content=task.task_content,
            requirements=task.requirements or "",
            word_limit=task.word_limit,
            category=category,
            major_category=major_category,
            group_category=group_category,
            template=template,
            template_schema=template_schema,
            operation_prefix="writing_service.official_sample",
            peer_samples=peer_samples,
        )

        if not english_essay or not english_essay.strip():
            raise ValueError("AI 生成范文失败：英文范文为空")

        if not self._validate_rendered_slots(template_schema, rendered_slots, category=category):
            raise ValueError("AI 生成范文失败：槽位输出与模板骨架不一致")

        if not (SAMPLE_MIN_WORDS <= word_count <= SAMPLE_MAX_WORDS):
            raise ValueError(
                f"AI 生成范文失败：英文范文字数 {word_count} 不在 {SAMPLE_MIN_WORDS}-{SAMPLE_MAX_WORDS} 词之间"
            )

        await self.db.execute(delete(WritingSample).where(WritingSample.task_id == task.id))
        await self.db.flush()

        sample = WritingSample(
            task_id=task.id,
            template_id=template.id if template else None,
            sample_content=english_essay,
            sample_type="AI生成",
            score_level=score_level,
            word_count=word_count,
            translation=chinese_translation,
            rendered_slots_json=json.dumps(rendered_slots, ensure_ascii=False),
            template_version=template.template_version or 1,
            generation_mode=OFFICIAL_GENERATION_MODE,
            quality_status=QUALITY_PASSED,
        )
        self.db.add(sample)
        await self.db.commit()
        await self.db.refresh(sample)
        return sample

    async def batch_generate_samples(self, task_ids: List[int], score_level: str = "一档") -> Dict:
        """批量生成范文。"""
        success_count = 0
        fail_count = 0
        results = []

        for task_id in task_ids:
            try:
                sample = await self.generate_sample(task_id, score_level=score_level)
                success_count += 1
                results.append({"task_id": task_id, "success": True, "sample_id": sample.id})
            except Exception as exc:
                fail_count += 1
                logger.warning("批量生成范文失败 task_id=%s: %s", task_id, exc)
                results.append({"task_id": task_id, "success": False, "error": str(exc)})

        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "results": results,
        }

    async def _load_category_example_tasks(
        self,
        category_id: int,
        anchor_task: Optional[WritingTask] = None,
        limit: int = 5,
    ) -> List[WritingTask]:
        tasks: List[WritingTask] = []
        seen_ids: set[int] = set()

        if anchor_task and anchor_task.category_id == category_id and anchor_task.task_content:
            tasks.append(anchor_task)
            if anchor_task.id:
                seen_ids.add(anchor_task.id)

        result = await self.db.execute(
            select(WritingTask)
            .options(selectinload(WritingTask.paper))
            .where(WritingTask.category_id == category_id)
            .order_by(WritingTask.created_at.desc(), WritingTask.id.desc())
            .limit(limit)
        )
        for task in result.scalars().all():
            if task.id in seen_ids:
                continue
            tasks.append(task)
            seen_ids.add(task.id)
            if len(tasks) >= limit:
                break
        return tasks

    def _build_template_examples(self, tasks: List[WritingTask]) -> List[Dict[str, str]]:
        examples: List[Dict[str, str]] = []
        for task in tasks:
            content = re.sub(r"\s+", " ", (task.task_content or "").strip())
            requirements = re.sub(r"\s+", " ", (task.requirements or "").strip())
            examples.append(
                {
                    "source": self._build_source_line(task.paper),
                    "task_content": self._shorten(content, 220),
                    "requirements": self._shorten(requirements, 160) if requirements else "",
                    "word_limit": task.word_limit or "",
                }
            )
        return examples

    def _build_representative_task_context(
        self,
        category: WritingCategory,
        major_category: Optional[WritingCategory],
        group_category: Optional[WritingCategory],
    ) -> tuple[str, str]:
        path = category.path or category.name
        category_name = category.name
        prompts = {
            "邀请信": (
                "假如你校将举办英语文化节，请给你的好友 Peter 写一封邀请信，邀请他参加。",
                "内容包括：活动时间地点、主要活动、邀请理由以及期待回复。"
            ),
            "邀请回复信": (
                "假如你收到了好友邀请你参加周末活动的邮件，请写一封英文回信回复。",
                "内容包括：是否接受邀请、原因、你的安排以及礼貌收尾。"
            ),
            "活动邀请邮件": (
                "假如你是李华，请给交换生 Jim 发一封活动邀请邮件，邀请他参加端午节体验活动。",
                "内容包括：活动时间地点、体验内容、邀请原因和期待回复。"
            ),
            "建议信": (
                "假如你的朋友在学习和运动之间很难平衡，请写一封建议信帮助他。",
                "内容包括：问题背景、两到三条建议及建议带来的帮助。"
            ),
            "求助信": (
                "假如你在英语学习上遇到了困难，请给外教写一封求助信。",
                "内容包括：你遇到的问题、已做的尝试以及希望获得的帮助。"
            ),
            "问题解决建议": (
                "围绕学生常见的时间管理问题写一篇英语建议短文。",
                "内容包括：问题现象、解决建议、原因和预期效果。"
            ),
            "介绍信": (
                "假如学校公众号正在征集英文稿件，请写一封介绍信介绍一个值得推荐的中国文化主题。",
                "内容包括：介绍对象、核心信息、意义和推荐理由。"
            ),
            "人物介绍": (
                "假如英文杂志正在征集“我的榜样”栏目文章，请介绍一位对你影响很大的人。",
                "内容包括：人物身份、典型事例、对你的影响和感受。"
            ),
            "活动介绍": (
                "假如你要向来访学生介绍你校的一项特色活动，请写一篇英文介绍。",
                "内容包括：活动内容、安排、亮点和参与收获。"
            ),
            "演讲稿": (
                "假如你要在学校英语角做一次英文演讲，请围绕一个积极校园主题写一篇演讲稿。",
                "内容包括：背景、核心观点、例子和呼吁。"
            ),
            "通知": (
                "假如学生会要发布一则英语通知，请写一篇通知。",
                "内容包括：活动时间、地点、对象、要求和提醒。"
            ),
            "倡议书": (
                "假如学校开展环保主题活动，请写一篇英文倡议书。",
                "内容包括：问题背景、倡议内容、具体行动和号召。"
            ),
            "个人看法": (
                "请围绕一个常见学习或生活话题写一篇表达个人看法的英语短文。",
                "内容包括：你的观点、理由和总结。"
            ),
            "利弊分析": (
                "请围绕一个校园生活现象写一篇英语利弊分析短文。",
                "内容包括：优点、缺点和你的结论。"
            ),
            "现象评价": (
                "请针对一个校园或社会现象写一篇英语评价短文。",
                "内容包括：现象描述、你的评价和建议。"
            ),
            "方法介绍": (
                "请写一篇英语短文介绍一种高效学习方法。",
                "内容包括：方法步骤、具体做法和好处。"
            ),
            "流程说明": (
                "请写一篇英语短文说明完成一项简单任务的流程。",
                "内容包括：步骤顺序、关键细节和注意事项。"
            ),
            "规则说明": (
                "请写一篇英语短文介绍一组校园规则。",
                "内容包括：规则内容、原因和遵守后的好处。"
            ),
        }
        if category_name in prompts:
            return prompts[category_name]

        if "记叙文" in path:
            return (
                f"请围绕“{category_name}”这一主题写一篇适合中考训练的英语记叙文。",
                "内容包括：背景起因、经过细节、感受变化以及收获启发。"
            )
        if "应用文" in path:
            return (
                f"请围绕“{category_name}”这一子类写一篇代表性英语应用文。",
                "内容包括：写作目的、核心信息、补充细节以及礼貌收尾。"
            )
        return (
            f"请围绕“{group_category.name if group_category else category_name} / {major_category.name if major_category else category_name} / {category_name}”写一篇代表性英语范文。",
            "内容包括：核心观点、细节展开和总结收束。"
        )

    def _build_template_fallback(self, category: WritingCategory) -> Dict[str, object]:
        path = category.path or category.name
        category_name = category.name
        is_letter = any(keyword in path for keyword in LETTER_CATEGORY_KEYWORDS)
        is_speech = any(keyword in path for keyword in SPEECH_CATEGORY_KEYWORDS)

        if category_name == "活动邀请邮件":
            template_content = (
                "Dear [name],\n\n"
                "I am writing to invite you to [event].\n"
                "It will be held [time and place].\n\n"
                "First, we will [activity 1].\n"
                "Then, you can [activity 2].\n"
                "Besides, this activity will help you [value or meaning].\n"
                "I think you will enjoy it because [reason].\n"
                "Before coming, please [preparation 1].\n"
                "You'd better also [preparation 2 or reminder].\n"
                "I hope you can join us.\n"
                "Please let me know whether you can come.\n\n"
                "Best wishes,\n"
                "Li Hua"
            )
            structure = "\n".join(
                [
                    "第1段：称呼并说明邀请目的、活动时间地点（35-45词）",
                    "第2段：介绍活动内容、意义和邀请理由（80-90词）",
                    "第3段：说明准备事项、表达期待并请求回复（30-40词）",
                ]
            )
            opening_sentences = [
                "Dear [name],",
                "I am writing to invite you to [event].",
            ]
            closing_sentences = [
                "I hope you can join us.",
                "Please let me know whether you can come.",
            ]
        elif category_name == "建议信":
            template_content = (
                "Dear [name],\n\n"
                "I am sorry to hear that [problem or situation].\n"
                "I understand how you feel about it.\n\n"
                "First, I think you should [advice 1].\n"
                "This can help because [reason 1].\n"
                "Second, it is a good idea to [advice 2].\n"
                "In this way, [expected result 2].\n"
                "Third, you can also [advice 3].\n"
                "Besides, [extra support or encouragement].\n"
                "I hope my suggestions will be helpful.\n"
                "I believe things will get better soon.\n\n"
                "Best wishes,\n"
                "Li Hua"
            )
            structure = "\n".join(
                [
                    "第1段：称呼并回应对方处境，表达理解（30-40词）",
                    "第2段：给出两到三条建议并说明理由或效果（85-95词）",
                    "第3段：鼓励对方、表达祝愿并署名（25-35词）",
                ]
            )
            opening_sentences = [
                "Dear [name],",
                "I am sorry to hear that [problem or situation].",
            ]
            closing_sentences = [
                "I hope my suggestions will be helpful.",
                "I believe things will get better soon.",
            ]
        elif category_name == "回信":
            template_content = (
                "Dear [name],\n\n"
                "Thanks for your email.\n"
                "I am glad to answer your questions about [topic].\n\n"
                "First, let me tell you [information point 1].\n"
                "Then, [information point 2].\n"
                "Besides, [information point 3].\n"
                "I think [meaning, value or suggestion].\n"
                "If you need more help, [offer or further support].\n"
                "I hope this reply is useful to you.\n\n"
                "Best wishes,\n"
                "Li Hua"
            )
            structure = "\n".join(
                [
                    "第1段：称呼、回应来信并点明回复主题（30-40词）",
                    "第2段：围绕来信问题逐条作答或介绍信息（85-95词）",
                    "第3段：补充帮助、表达祝愿并署名（25-35词）",
                ]
            )
            opening_sentences = [
                "Dear [name],",
                "Thanks for your email.",
            ]
            closing_sentences = [
                "If you need more help, [offer or further support].",
                "I hope this reply is useful to you.",
            ]
        elif category_name == "介绍信":
            template_content = (
                "I would like to introduce [subject].\n"
                "It is [general background or feature].\n\n"
                "First of all, [detail 1].\n"
                "Then, [detail 2].\n"
                "What's more, [detail 3].\n"
                "This makes [subject] [value or special point].\n"
                "I believe [subject] can [meaning or benefit].\n\n"
                "I hope this introduction helps you know [subject] better.\n"
                "If you have the chance, you can learn more about it yourself."
            )
            structure = "\n".join(
                [
                    "第1段：点明介绍对象并概括背景（25-35词）",
                    "第2段：介绍主要特点、细节和价值（85-95词）",
                    "第3段：总结意义并自然收束（25-35词）",
                ]
            )
            opening_sentences = [
                "I would like to introduce [subject].",
                "It is [general background or feature].",
            ]
            closing_sentences = [
                "I hope this introduction helps you know [subject] better.",
                "If you have the chance, you can learn more about it yourself.",
            ]
        elif category_name == "人物介绍":
            template_content = (
                "I would like to introduce [person].\n"
                "[He/She] is [identity or relationship] and [general reason for admiration].\n\n"
                "To begin with, [quality or characteristic 1].\n"
                "For example, [specific example 1].\n"
                "In addition, [quality or characteristic 2].\n"
                "This has helped me [influence on me or others].\n"
                "Because of this, I [feeling or attitude toward the person].\n\n"
                "From [person], I have learned that [reflection].\n"
                "I will try to [future action inspired by the person]."
            )
            structure = "\n".join(
                [
                    "第1段：介绍人物身份并概括主要特点（25-35词）",
                    "第2段：通过品质和事例展开人物形象与影响（80-95词）",
                    "第3段：总结启发并表达个人态度（30-40词）",
                ]
            )
            opening_sentences = [
                "I would like to introduce [person].",
                "[He/She] is [identity or relationship] and [general reason for admiration].",
            ]
            closing_sentences = [
                "From [person], I have learned that [reflection].",
                "I will try to [future action inspired by the person].",
            ]
        elif category_name == "活动介绍":
            template_content = (
                "Here I would like to introduce [activity].\n"
                "It is held [time, place or background].\n\n"
                "First, students can [activity detail 1].\n"
                "Then, they usually [activity detail 2].\n"
                "Besides, [highlight or feature].\n"
                "This activity helps students [benefit 1].\n"
                "It also makes our school life [benefit 2].\n\n"
                "That is why many students enjoy [activity].\n"
                "I hope more people can take part in it."
            )
            structure = "\n".join(
                [
                    "第1段：点明活动名称并介绍背景（25-35词）",
                    "第2段：介绍活动安排、亮点和收获（85-95词）",
                    "第3段：总结活动价值并表达期待（25-35词）",
                ]
            )
            opening_sentences = [
                "Here I would like to introduce [activity].",
                "It is held [time, place or background].",
            ]
            closing_sentences = [
                "That is why many students enjoy [activity].",
                "I hope more people can take part in it.",
            ]
        elif category_name == "通知":
            template_content = (
                "Notice\n"
                "[date]\n\n"
                "There will be [event or change of plan].\n"
                "It will be held [time and place].\n\n"
                "First, please know that [arrangement 1 or reason].\n"
                "Then, [arrangement 2 or activity].\n"
                "Besides, [rule or reminder 1].\n"
                "Please also remember to [rule or reminder 2].\n"
                "We hope everyone will [expected action or closing].\n\n"
                "[organizer]"
            )
            structure = "\n".join(
                [
                    "第1段：通知标题、日期并点明事项（25-35词）",
                    "第2段：介绍安排、要求和提醒（85-95词）",
                    "第3段：总结提醒并署名单位（20-30词）",
                ]
            )
            opening_sentences = [
                "Notice",
                "[date]",
            ]
            closing_sentences = [
                "We hope everyone will [expected action or closing].",
                "[organizer]",
            ]
        elif category_name == "演讲稿":
            template_content = (
                "Hello everyone,\n\n"
                "Today I would like to talk about [topic].\n"
                "This topic matters because [background or importance].\n\n"
                "First of all, [main point 1].\n"
                "For example, [supporting detail 1].\n"
                "Then, [main point 2].\n"
                "In addition, [supporting detail 2].\n"
                "As a result, [expected result or meaning].\n\n"
                "I hope all of us can [call to action].\n"
                "Thank you for listening."
            )
            structure = "\n".join(
                [
                    "第1段：开场点题并说明演讲话题的重要性（35-45词）",
                    "第2段：展开核心观点并给出例子（80-90词）",
                    "第3段：总结观点并发出呼吁（25-35词）",
                ]
            )
            opening_sentences = [
                "Hello everyone,",
                "Today I would like to talk about [topic].",
            ]
            closing_sentences = [
                "I hope all of us can [call to action].",
                "Thank you for listening.",
            ]
        elif category_name == "倡议书":
            template_content = (
                "Let's work together to [topic].\n"
                "It is important because [background or problem].\n\n"
                "First, we should [action 1].\n"
                "This will help us [benefit 1].\n"
                "Second, we can [action 2].\n"
                "In this way, [benefit 2].\n"
                "Third, please [action 3].\n"
                "Small actions can make a big difference.\n\n"
                "Let's start from now and make our school better together.\n"
                "Thank you for your support."
            )
            structure = "\n".join(
                [
                    "第1段：点明倡议主题并说明背景（30-40词）",
                    "第2段：提出两到三条具体行动建议（85-95词）",
                    "第3段：总结意义并号召大家行动（25-35词）",
                ]
            )
            opening_sentences = [
                "Let's work together to [topic].",
                "It is important because [background or problem].",
            ]
            closing_sentences = [
                "Let's start from now and make our school better together.",
                "Thank you for your support.",
            ]
        elif category_name == "问题解决建议":
            template_content = (
                "Many students have the problem that [problem].\n"
                "Here are some useful ideas to solve it.\n\n"
                "First, [suggestion 1].\n"
                "This is helpful because [reason 1].\n"
                "Second, [suggestion 2].\n"
                "In this way, [result 2].\n"
                "Third, [suggestion 3].\n"
                "With these steps, [expected result].\n\n"
                "I hope these ideas can make things easier.\n"
                "Everyone can improve little by little."
            )
            structure = "\n".join(
                [
                    "第1段：提出问题并点明写作目的（25-35词）",
                    "第2段：给出具体解决建议和效果（85-95词）",
                    "第3段：总结效果并鼓励读者（25-35词）",
                ]
            )
            opening_sentences = [
                "Many students have the problem that [problem].",
                "Here are some useful ideas to solve it.",
            ]
            closing_sentences = [
                "I hope these ideas can make things easier.",
                "Everyone can improve little by little.",
            ]
        elif category_name == "意见反馈":
            template_content = (
                "I am glad to share my ideas about [topic].\n"
                "Overall, I think [general opinion].\n\n"
                "First, [feedback point 1].\n"
                "This is important because [reason 1].\n"
                "Second, [feedback point 2].\n"
                "It would be better if [improvement].\n"
                "In addition, [feedback point 3].\n"
                "I hope these suggestions can be useful.\n\n"
                "Thank you for listening to my ideas.\n"
                "I am looking forward to a better result."
            )
            structure = "\n".join(
                [
                    "第1段：说明反馈主题并概括总体看法（25-35词）",
                    "第2段：提出主要意见、原因和改进建议（85-95词）",
                    "第3段：礼貌收束并表达期待（25-35词）",
                ]
            )
            opening_sentences = [
                "I am glad to share my ideas about [topic].",
                "Overall, I think [general opinion].",
            ]
            closing_sentences = [
                "Thank you for listening to my ideas.",
                "I am looking forward to a better result.",
            ]
        elif category_name == "规则说明":
            template_content = (
                "Here are some important rules for [topic].\n"
                "Following them can make things better for everyone.\n\n"
                "First, you should [rule 1].\n"
                "This is because [reason 1].\n"
                "Second, you must [rule 2].\n"
                "This can help [benefit 2].\n"
                "Third, don't [rule 3].\n"
                "If everyone follows these rules, [result].\n\n"
                "These rules are simple but useful.\n"
                "I hope all of us can keep them in mind."
            )
            structure = "\n".join(
                [
                    "第1段：点明规则主题和作用（25-35词）",
                    "第2段：逐条说明规则与原因（85-95词）",
                    "第3段：总结规则意义并自然收束（25-35词）",
                ]
            )
            opening_sentences = [
                "Here are some important rules for [topic].",
                "Following them can make things better for everyone.",
            ]
            closing_sentences = [
                "These rules are simple but useful.",
                "I hope all of us can keep them in mind.",
            ]
        elif category_name == "行程安排":
            template_content = (
                "Hi [name],\n\n"
                "I am leaving this note to tell you [purpose].\n"
                "I am going to [place] with [person].\n\n"
                "First, we will [activity 1].\n"
                "Then, we plan to [activity 2].\n"
                "After that, [activity 3 or other arrangement].\n"
                "I will come back at [time].\n"
                "I will return by [transportation].\n"
                "Please don't worry about me.\n\n"
                "Li Hua"
            )
            structure = "\n".join(
                [
                    "第1段：说明留言目的和去向（30-40词）",
                    "第2段：介绍活动安排、回家时间和方式（80-90词）",
                    "第3段：礼貌收束并署名（15-25词）",
                ]
            )
            opening_sentences = [
                "Hi [name],",
                "I am leaving this note to tell you [purpose].",
            ]
            closing_sentences = [
                "Please don't worry about me.",
                "Li Hua",
            ]
        elif is_letter:
            template_content = (
                "Dear [name],\n\n"
                "I am writing to [purpose].\n"
                "I am glad to tell you that [activity background].\n"
                "To begin with, [key point 1].\n"
                "Besides, [key point 2].\n"
                "What's more, [key point 3 or reason].\n"
                "I think [personal reason or value].\n"
                "If you come, [specific arrangement].\n"
                "I hope [expectation].\n"
                "Please let me know [reply request].\n\n"
                "Best wishes,\n"
                "Li Hua"
            )
            structure = "\n".join(
                [
                    "第1段：称呼并说明写作目的与背景（35-45词）",
                    f"第2段：围绕“{category.name}”展开核心信息、原因与安排（75-90词）",
                    "第3段：表达期待、请求回复并署名（30-40词）",
                ]
            )
            opening_sentences = [
                "Dear [name],",
                "I am writing to [purpose].",
            ]
            closing_sentences = [
                "I hope [expectation].",
                "Please let me know [reply request].",
            ]
        elif is_speech:
            template_content = (
                "Hello everyone,\n\n"
                "Today I want to talk about [topic].\n"
                "This topic is important because [background].\n"
                "First of all, [main point 1].\n"
                "For example, [supporting example 1].\n"
                "Then, [main point 2].\n"
                "In addition, [supporting example 2].\n"
                "As a result, [expected result].\n"
                "I hope all of us can [call to action].\n\n"
                "Thank you for listening."
            )
            structure = "\n".join(
                [
                    "第1段：开场点题，说明讲话目的与背景（35-45词）",
                    f"第2段：结合“{category.name}”展开主体观点和例子（75-90词）",
                    "第3段：总结观点并发出呼吁/致谢（25-35词）",
                ]
            )
            opening_sentences = [
                "Hello everyone,",
                "Today I want to talk about [topic].",
            ]
            closing_sentences = [
                "I hope all of us can [call to action].",
                "Thank you for listening.",
            ]
        else:
            template_content = (
                "I would like to share [topic/event].\n"
                "It happened when [time or background].\n\n"
                "At first, [detail or action 1].\n"
                "Then, [detail or action 2].\n"
                "After that, [detail or action 3].\n"
                "Meanwhile, [feeling or challenge].\n"
                "In the end, [result].\n\n"
                "From this experience, I learned that [reflection].\n"
                "I will always remember [final feeling or future action]."
            )
            structure = "\n".join(
                [
                    "第1段：引入主题，交代背景（25-35词）",
                    f"第2段：围绕“{category.name}”展开经过、细节与感受（80-95词）",
                    "第3段：总结结果、启示和个人态度（30-40词）",
                ]
            )
            opening_sentences = [
                "I would like to share [topic/event].",
                "It happened when [time or background].",
            ]
            closing_sentences = [
                "From this experience, I learned that [reflection].",
                "I will always remember [final feeling or future action].",
            ]

        template_schema = self._build_schema_from_text_template(template_content, structure)

        return {
            "template_name": f"{category.name}通用模板",
            "template_content": template_content,
            "template_schema_json": template_schema,
            "structure": structure,
            "tips": "紧扣题干信息点，优先覆盖场景、细节、原因与感受；句子保持自然可迁移。",
            "opening_sentences": opening_sentences,
            "closing_sentences": closing_sentences,
            "transition_words": ["First of all,", "Then,", "Besides,", "In the end,"],
            "advanced_vocabulary": [{"word": "meaningful", "basic": "good", "usage": "描述活动或经历有意义"}],
            "grammar_points": ["注意时态统一，根据信件或记叙场景选择一般现在时或一般过去时。"],
            "scoring_criteria": {
                "content": "覆盖题干要点",
                "language": "句式自然、表达准确",
                "structure": "段落清楚、过渡自然",
            },
        }

    def _template_schema_meets_bar(self, schema: Dict[str, Any], category: WritingCategory) -> bool:
        if not schema.get("paragraphs"):
            return False
        slot_count = self._count_template_slots(schema)
        if slot_count < self._minimum_slot_count(category):
            return False

        opening_slots = (schema.get("paragraphs") or [{}])[0].get("slots") or []
        opening_patterns = " ".join(str(slot.get("fallback_pattern") or "") for slot in opening_slots)
        path = category.path or category.name
        is_letter = any(keyword in path for keyword in LETTER_CATEGORY_KEYWORDS)
        is_speech = any(keyword in path for keyword in SPEECH_CATEGORY_KEYWORDS)
        if is_letter and "Dear " not in opening_patterns:
            return False
        if not is_letter and re.search(r"(?i)\bDear\b", opening_patterns):
            return False
        if is_speech and re.search(r"(?i)\bDear\b", opening_patterns):
            return False
        return True

    async def _populate_template_representative_sample(
        self,
        template: WritingTemplate,
        category: WritingCategory,
        major_category: Optional[WritingCategory],
        group_category: Optional[WritingCategory],
        template_schema: Dict[str, Any],
    ) -> None:
        task_content, requirements = self._build_representative_task_context(category, major_category, group_category)
        rendered_slots, essay, word_count, translation = await self._generate_slot_filled_official_sample(
            task_content=task_content,
            requirements=requirements,
            word_limit=f"{DEFAULT_WORD_TARGET}词左右",
            category=category,
            major_category=major_category,
            group_category=group_category,
            template=template,
            template_schema=template_schema,
            operation_prefix="writing_service.representative_sample",
        )
        template.representative_sample_content = essay
        template.representative_translation = translation
        template.representative_rendered_slots_json = json.dumps(rendered_slots, ensure_ascii=False)
        template.representative_word_count = word_count
        template.quality_status = QUALITY_PASSED

    def _template_needs_repair(self, template: WritingTemplate, category: WritingCategory) -> bool:
        content = (template.template_content or "").strip()
        structure = (template.structure or "").strip()
        is_letter = any(keyword in (category.path or category.name) for keyword in LETTER_CATEGORY_KEYWORDS)
        schema = self._normalize_template_schema(
            template.template_schema_json,
            fallback_content=content,
            fallback_structure=structure,
        )
        slot_count = self._count_template_slots(schema)

        if not content:
            return True
        if not schema.get("paragraphs"):
            return True
        if slot_count < self._minimum_slot_count(category):
            return True
        if not is_letter and re.search(r"(?i)\bDear\b|\bBest wishes\b|\bYours\b", content):
            return True
        if "paragraph" in structure and "{" in structure:
            return True
        if not (template.opening_sentences and template.closing_sentences):
            return True
        if (template.quality_status or "").strip() == QUALITY_FAILED:
            return True
        return False

    def _repair_template_locally_if_needed(
        self,
        template: WritingTemplate,
        category: WritingCategory,
    ) -> bool:
        schema = self._normalize_template_schema(
            template.template_schema_json,
            fallback_content=template.template_content or "",
            fallback_structure=template.structure or "",
        )
        rendered_content = self._render_template_content_from_schema(schema)
        rendered_structure = self._render_structure_text_from_schema(schema)
        opening_sentences, closing_sentences = self._extract_sentence_bank_from_schema(schema)

        changed = False
        schema_json = json.dumps(schema, ensure_ascii=False)
        if (template.template_schema_json or "").strip() != schema_json:
            template.template_schema_json = schema_json
            changed = True
        if (template.template_content or "").strip() != rendered_content:
            template.template_content = rendered_content
            changed = True
        if (template.structure or "").strip() != rendered_structure:
            template.structure = rendered_structure
            changed = True
        if not template.opening_sentences:
            template.opening_sentences = json.dumps(opening_sentences, ensure_ascii=False)
            changed = True
        if not template.closing_sentences:
            template.closing_sentences = json.dumps(closing_sentences, ensure_ascii=False)
            changed = True
        if not template.template_version:
            template.template_version = 1
            changed = True
        elif changed:
            template.template_version = (template.template_version or 1) + 1
        return changed

    async def get_or_create_template(
        self,
        category_id: int,
        anchor_task: Optional[WritingTask] = None,
        force_refresh: bool = False,
        refresh_if_stale: bool = False,
    ) -> WritingTemplate:
        """按子类获取或创建模板。"""
        query = (
            select(WritingTemplate)
            .options(selectinload(WritingTemplate.category))
            .where(WritingTemplate.category_id == category_id)
            .limit(1)
        )
        result = await self.db.execute(query)
        template = result.scalar_one_or_none()

        category_result = await self.db.execute(
            select(WritingCategory)
            .options(selectinload(WritingCategory.parent).selectinload(WritingCategory.parent))
            .where(WritingCategory.id == category_id)
        )
        category = category_result.scalar_one_or_none()
        if not category:
            raise ValueError(f"作文分类不存在: {category_id}")

        if template and not force_refresh:
            needs_repair = self._template_needs_repair(template, category)
            if not needs_repair or not refresh_if_stale:
                return template

        parent = category.parent
        group = parent.parent if parent and parent.parent else parent

        example_tasks = await self._load_category_example_tasks(category_id, anchor_task=anchor_task, limit=5)
        if category.name in CANONICAL_TEMPLATE_CATEGORIES:
            template_data = self._build_template_fallback(category)
        else:
            template_data = await self.ai_service.generate_writing_template_async(
                category_name=category.name,
                category_path=category.path,
                prompt_hint=category.prompt_hint,
                target_word_count=DEFAULT_WORD_TARGET,
                group_name=group.name if group else None,
                major_category_name=parent.name if parent else None,
                task_examples=self._build_template_examples(example_tasks),
                existing_template=template.template_content if template else None,
            )
            if not template_data or not (
                template_data.get("template_schema_json") or template_data.get("template_content")
            ):
                template_data = self._build_template_fallback(category)

        template_name = self._normalize_template_text(
            template_data.get("template_name", f"{category.name}通用模板")
        )
        template_schema = self._normalize_template_schema(
            template_data.get("template_schema_json"),
            fallback_content=self._normalize_template_text(template_data.get("template_content", "")),
            fallback_structure=self._normalize_template_text(template_data.get("structure", "")),
        )
        if not self._template_schema_meets_bar(template_schema, category):
            template_data = self._build_template_fallback(category)
            template_schema = self._normalize_template_schema(
                template_data.get("template_schema_json"),
                fallback_content=self._normalize_template_text(template_data.get("template_content", "")),
                fallback_structure=self._normalize_template_text(template_data.get("structure", "")),
            )
        template_content = self._render_template_content_from_schema(template_schema)
        tips = self._normalize_template_text(template_data.get("tips", ""))
        structure = self._render_structure_text_from_schema(template_schema)
        opening_sentences = self._normalize_template_json(template_data.get("opening_sentences"))
        closing_sentences = self._normalize_template_json(template_data.get("closing_sentences"))
        transition_words = self._normalize_template_json(template_data.get("transition_words"))
        advanced_vocabulary = self._normalize_template_json(template_data.get("advanced_vocabulary"))
        grammar_points = self._normalize_template_json(template_data.get("grammar_points"))
        scoring_criteria = self._normalize_template_json(template_data.get("scoring_criteria"))
        template_schema_json = json.dumps(template_schema, ensure_ascii=False)
        fallback_opening_sentences, fallback_closing_sentences = self._extract_sentence_bank_from_schema(template_schema)
        if not opening_sentences and fallback_opening_sentences:
            opening_sentences = json.dumps(fallback_opening_sentences, ensure_ascii=False)
        if not closing_sentences and fallback_closing_sentences:
            closing_sentences = json.dumps(fallback_closing_sentences, ensure_ascii=False)

        if template is None:
            template = WritingTemplate(
                category_id=category.id,
                category=category,
                writing_type=group.name if group else (parent.name if parent else category.name),
                application_type=parent.name if parent else None,
                template_name=template_name,
                template_content=template_content,
                tips=tips,
                structure=structure,
                opening_sentences=opening_sentences,
                closing_sentences=closing_sentences,
                transition_words=transition_words,
                advanced_vocabulary=advanced_vocabulary,
                grammar_points=grammar_points,
                scoring_criteria=scoring_criteria,
                template_key=category.template_key,
                template_schema_json=template_schema_json,
                template_version=1,
                quality_status=QUALITY_PASSED,
            )
            self.db.add(template)
        else:
            template.category = category
            template.writing_type = group.name if group else (parent.name if parent else category.name)
            template.application_type = parent.name if parent else None
            template.template_name = template_name
            template.template_content = template_content
            template.tips = tips
            template.structure = structure
            template.opening_sentences = opening_sentences
            template.closing_sentences = closing_sentences
            template.transition_words = transition_words
            template.advanced_vocabulary = advanced_vocabulary
            template.grammar_points = grammar_points
            template.scoring_criteria = scoring_criteria
            template.template_key = category.template_key
            template.template_schema_json = template_schema_json
            template.template_version = (template.template_version or 1) + 1
            template.quality_status = QUALITY_PASSED

        await self.db.flush()
        await self.db.commit()
        await self.db.refresh(template)
        return template

    async def ensure_task_assets(
        self,
        task_or_id: WritingTask | int,
        *,
        force_template_refresh: bool = False,
        regenerate_sample: bool = False,
        score_level: str = "一档",
    ) -> tuple[WritingTask, WritingTemplate, WritingSample]:
        """确保作文在分类后拥有当前子类模板和对应范文。"""
        task_id = task_or_id.id if isinstance(task_or_id, WritingTask) else task_or_id
        task = await self.get_writing_detail(task_id)

        if not task:
            raise ValueError("作文不存在")

        if not task.category_id:
            category_result = await self.classify_task(task)
            if not category_result.success or not category_result.category:
                raise ValueError(category_result.error or "作文分类失败")

        template = await self.get_or_create_template(
            task.category_id,
            anchor_task=task,
            force_refresh=force_template_refresh,
            refresh_if_stale=force_template_refresh,
        )
        template_id = template.id if template else None

        existing_sample = next(
            iter(sorted(task.samples or [], key=lambda item: item.id or 0, reverse=True)),
            None,
        )
        if existing_sample and not regenerate_sample:
            if self._repair_sample_from_rendered_slots(existing_sample, template):
                await self.db.commit()
                await self.db.refresh(existing_sample)
                await self.db.refresh(template)
                refreshed_task = await self.get_writing_detail(task_id)
                if refreshed_task:
                    return refreshed_task, template, existing_sample
            if self._sample_meets_quality_bar(
                existing_sample,
                expected_template_id=template.id,
                template=template,
            ):
                return task, template, existing_sample

            await self.db.execute(delete(WritingSample).where(WritingSample.task_id == task_id))
            await self.db.flush()

        last_error: Optional[Exception] = None
        for attempt in range(1, 4):
            try:
                if attempt > 1 and force_template_refresh:
                    template = await self.get_or_create_template(
                        task.category_id,
                        anchor_task=task,
                        force_refresh=True,
                        refresh_if_stale=True,
                    )
                    template_id = template.id if template else None
                sample = await self.generate_sample(
                    task_id=task.id,
                    template_id=template_id,
                    score_level=score_level,
                    force_template_refresh=False,
                )
                refreshed_task = await self.get_writing_detail(task.id)
                return refreshed_task or task, template, sample
            except Exception as exc:
                last_error = exc
                await self.db.rollback()
                logger.warning(
                    "作文范文生成重试 %s/3 失败 task_id=%s: %s",
                    attempt,
                    task_id,
                    exc,
                )
                task = await self.get_writing_detail(task_id)
                if not task:
                    break
                if template_id is None and task.category_id:
                    template = await self.get_or_create_template(
                        task.category_id,
                        anchor_task=task,
                        force_refresh=False,
                        refresh_if_stale=False,
                    )
                    template_id = template.id if template else None

        raise ValueError(f"作文范文生成失败: {last_error}") from last_error

    async def get_writings(
        self,
        page: int = 1,
        size: int = 20,
        grade: Optional[str] = None,
        semester: Optional[str] = None,
        exam_type: Optional[str] = None,
        group_category_id: Optional[int] = None,
        major_category_id: Optional[int] = None,
        category_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[WritingTask], int, Dict]:
        """获取作文列表。"""
        query = (
            select(WritingTask)
            .options(
                selectinload(WritingTask.paper),
                selectinload(WritingTask.group_category),
                selectinload(WritingTask.major_category),
                selectinload(WritingTask.category),
            )
        )

        if grade:
            query = query.where(WritingTask.grade == grade)
        if semester:
            query = query.where(WritingTask.semester == semester)
        if exam_type:
            query = query.where(WritingTask.exam_type == exam_type)
        if group_category_id:
            query = query.where(WritingTask.group_category_id == group_category_id)
        if major_category_id:
            query = query.where(WritingTask.major_category_id == major_category_id)
        if category_id:
            query = query.where(WritingTask.category_id == category_id)
        if search:
            query = query.where(WritingTask.task_content.contains(search))

        total_result = await self.db.execute(select(func.count()).select_from(query.subquery()))
        total = total_result.scalar() or 0

        query = query.order_by(WritingTask.created_at.desc()).offset((page - 1) * size).limit(size)
        result = await self.db.execute(query)
        items = list(result.scalars().all())

        grade_counts = {}
        for grade_value in GRADE_OPTIONS:
            count_query = select(func.count()).select_from(WritingTask).where(WritingTask.grade == grade_value)
            grade_count = await self.db.execute(count_query)
            grade_counts[grade_value] = grade_count.scalar() or 0

        return items, total, grade_counts

    async def get_template_list(
        self,
        *,
        page: int = 1,
        size: int = 20,
        grade: Optional[str] = None,
        semester: Optional[str] = None,
        exam_type: Optional[str] = None,
        group_category_id: Optional[int] = None,
        major_category_id: Optional[int] = None,
        category_id: Optional[int] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """按模板维度返回作文汇编列表。"""
        category_result = await self.db.execute(select(WritingCategory))
        category_map = {item.id: item for item in category_result.scalars().all()}
        filters = []
        if grade:
            filters.append(WritingTask.grade == grade)
        if semester:
            filters.append(WritingTask.semester == semester)
        if exam_type:
            filters.append(WritingTask.exam_type == exam_type)
        if group_category_id:
            filters.append(WritingTask.group_category_id == group_category_id)
        if major_category_id:
            filters.append(WritingTask.major_category_id == major_category_id)
        if category_id:
            filters.append(WritingTask.category_id == category_id)
        if search:
            filters.append(WritingTask.task_content.contains(search))

        template_ids_query = (
            select(WritingTemplate.id)
            .join(WritingCategory, WritingTemplate.category_id == WritingCategory.id)
            .join(WritingTask, WritingTask.category_id == WritingTemplate.category_id)
            .where(*filters)
            .group_by(WritingTemplate.id)
        )
        total_result = await self.db.execute(select(func.count()).select_from(template_ids_query.subquery()))
        total = total_result.scalar() or 0

        query = (
            select(
                WritingTemplate,
                WritingCategory,
                func.count(func.distinct(WritingTask.paper_id)).label("paper_count"),
                func.count(func.distinct(WritingTask.id)).label("task_count"),
            )
            .join(WritingCategory, WritingTemplate.category_id == WritingCategory.id)
            .join(WritingTask, WritingTask.category_id == WritingTemplate.category_id)
            .where(*filters)
            .group_by(WritingTemplate.id, WritingCategory.id)
            .order_by(
                WritingCategory.path.asc(),
                func.coalesce(WritingTemplate.updated_at, WritingTemplate.created_at).desc(),
                WritingTemplate.id.desc(),
            )
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await self.db.execute(query)
        items: List[Dict[str, Any]] = []
        for template, category, paper_count, task_count in result.all():
            major_category = category_map.get(category.parent_id) if category.parent_id else None
            group_category = category_map.get(major_category.parent_id) if major_category and major_category.parent_id else major_category
            items.append(
                {
                    "template": template,
                    "category": category,
                    "major_category": major_category,
                    "group_category": group_category,
                    "paper_count": paper_count or 0,
                    "task_count": task_count or 0,
                }
            )
        return items, total

    async def get_template_papers(self, template_id: int) -> Dict[str, Any]:
        """获取某个模板覆盖的试卷列表。"""
        template_result = await self.db.execute(
            select(WritingTemplate)
            .options(selectinload(WritingTemplate.category).selectinload(WritingCategory.parent).selectinload(WritingCategory.parent))
            .where(WritingTemplate.id == template_id)
        )
        template = template_result.scalar_one_or_none()
        if not template:
            raise ValueError("模板不存在")

        result = await self.db.execute(
            select(
                ExamPaper,
                func.count(WritingTask.id).label("task_count"),
            )
            .join(WritingTask, WritingTask.paper_id == ExamPaper.id)
            .where(WritingTask.category_id == template.category_id)
            .group_by(ExamPaper.id)
            .order_by(ExamPaper.year.desc().nullslast(), ExamPaper.id.desc())
        )
        papers = []
        for paper, task_count in result.all():
            papers.append(
                {
                    "paper_id": paper.id,
                    "filename": paper.filename,
                    "year": paper.year,
                    "region": paper.region,
                    "school": paper.school,
                    "grade": paper.grade,
                    "exam_type": paper.exam_type,
                    "semester": paper.semester,
                    "task_count": task_count or 0,
                }
            )

        category = template.category
        major_category = category.parent
        group_category = major_category.parent if major_category and major_category.parent else major_category
        return {
            "template": template,
            "category": category,
            "major_category": major_category,
            "group_category": group_category,
            "papers": papers,
        }

    async def get_template_paper_detail(self, template_id: int, paper_id: int) -> Dict[str, Any]:
        """获取模板下某一张试卷的全部作文题与正式范文。"""
        template_payload = await self.get_template_papers(template_id)
        template = template_payload["template"]
        expected_category_id = template_payload["category"].id

        task_result = await self.db.execute(
            select(WritingTask)
            .options(
                selectinload(WritingTask.paper),
                selectinload(WritingTask.samples),
                selectinload(WritingTask.group_category),
                selectinload(WritingTask.major_category),
                selectinload(WritingTask.category),
            )
            .where(
                WritingTask.paper_id == paper_id,
                WritingTask.category_id == template_payload["category"].id,
            )
            .order_by(WritingTask.id.asc())
        )
        tasks = list(task_result.scalars().all())
        if not tasks:
            raise ValueError("该试卷下没有属于当前模板的作文题")

        return {
            "template": template,
            "category": template_payload["category"],
            "major_category": template_payload["major_category"],
            "group_category": template_payload["group_category"],
            "paper": tasks[0].paper,
            "tasks": [task for task in tasks if task.category_id == expected_category_id],
        }

    async def get_writing_detail(self, task_id: int) -> Optional[WritingTask]:
        """获取作文详情（含模板和范文）。"""
        query = (
            select(WritingTask)
            .options(
                selectinload(WritingTask.paper),
                selectinload(WritingTask.samples),
                selectinload(WritingTask.group_category),
                selectinload(WritingTask.major_category),
                selectinload(WritingTask.category),
            )
            .where(WritingTask.id == task_id)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_filters(self) -> Dict:
        """获取作文筛选项。"""
        grades_result = await self.db.execute(
            select(WritingTask.grade).distinct().where(WritingTask.grade.isnot(None))
        )
        semesters_result = await self.db.execute(
            select(WritingTask.semester).distinct().where(WritingTask.semester.isnot(None))
        )
        exam_types_result = await self.db.execute(
            select(WritingTask.exam_type).distinct().where(WritingTask.exam_type.isnot(None))
        )
        category_result = await self.db.execute(
            select(WritingCategory)
            .where(WritingCategory.is_active.is_(True))
            .order_by(WritingCategory.level, WritingCategory.sort_order, WritingCategory.id)
        )
        categories = list(category_result.scalars().all())

        return {
            "grades": sorted([value for value in grades_result.scalars().all() if value]),
            "semesters": sorted([value for value in semesters_result.scalars().all() if value]),
            "exam_types": sorted([value for value in exam_types_result.scalars().all() if value]),
            "groups": [item for item in categories if item.level == 1],
            "major_categories": [item for item in categories if item.level == 2],
            "categories": [item for item in categories if item.level == 3],
        }

    async def build_grade_handout(
        self,
        grade: str,
        edition: str = "teacher",
        paper_ids: Optional[List[int]] = None,
    ) -> Dict:
        """构建年级作文讲义。"""
        tasks = await self._load_tasks_for_handout(grade, paper_ids)
        if not tasks:
            return {"grade": grade, "edition": edition, "total_task_count": 0, "groups": []}

        group_map: dict[int, dict] = {}
        for task in tasks:
            if not (task.group_category and task.major_category and task.category):
                continue

            group_bucket = group_map.setdefault(
                task.group_category.id,
                {"group_category": task.group_category, "sections": {}},
            )
            section_bucket = group_bucket["sections"].setdefault(
                task.category.id,
                {
                    "group_category": task.group_category,
                    "major_category": task.major_category,
                    "category": task.category,
                    "tasks": [],
                },
            )
            section_bucket["tasks"].append(task)

        groups_output = []
        for group_bucket in sorted(
            group_map.values(),
            key=lambda item: (item["group_category"].sort_order, item["group_category"].id),
        ):
            sections_output = []
            for section in sorted(
                group_bucket["sections"].values(),
                key=lambda item: (item["major_category"].sort_order, item["category"].sort_order, item["category"].id),
            ):
                section_data = await self._build_category_section(section["tasks"], edition)
                sections_output.append(section_data)
            groups_output.append(
                {
                    "group_category": self._category_to_dict(group_bucket["group_category"]),
                    "sections": sections_output,
                }
            )

        return {
            "grade": grade,
            "edition": edition,
            "total_task_count": len(tasks),
            "groups": groups_output,
        }

    async def _load_tasks_for_handout(self, grade: str, paper_ids: Optional[List[int]]) -> List[WritingTask]:
        query = (
            select(WritingTask)
            .join(ExamPaper, WritingTask.paper_id == ExamPaper.id)
            .options(
                selectinload(WritingTask.paper),
                selectinload(WritingTask.samples),
                selectinload(WritingTask.group_category),
                selectinload(WritingTask.major_category),
                selectinload(WritingTask.category),
            )
            .where(ExamPaper.grade == grade)
            .where(WritingTask.category_id.isnot(None))
            .order_by(ExamPaper.year.desc().nullslast(), WritingTask.id.desc())
        )
        query = self._apply_exam_paper_filter(query, paper_ids)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _build_category_section(self, tasks: List[WritingTask], edition: str) -> Dict:
        category = tasks[0].category
        major_category = tasks[0].major_category
        group_category = tasks[0].group_category
        # 讲义接口只消费当前已生成的子类模板，避免在只读场景里触发整批模板重建。
        template = await self.get_or_create_template(category.id, refresh_if_stale=False)

        years = sorted({task.paper.year for task in tasks if task.paper and task.paper.year})
        applicable_ranges = []
        seen_ranges = set()
        for task in tasks[:8]:
            source = self._build_source_line(task.paper)
            preview = self._shorten(task.task_content, 32)
            line = f"{source}：{preview}" if source else preview
            if line not in seen_ranges:
                seen_ranges.add(line)
                applicable_ranges.append(line)

        samples = []
        sorted_tasks = sorted(tasks, key=lambda item: ((item.paper.year if item.paper else 0), item.id), reverse=True)
        for task in sorted_tasks:
            official_sample = self._select_display_sample(
                task.samples,
                expected_template_id=template.id,
                template=template,
            )
            if official_sample is None:
                continue

            if official_sample:
                sample = official_sample
                highlighted = self._parse_json(sample.highlights) if edition == "teacher" else []
                samples.append(
                    {
                        "id": sample.id,
                        "task_content": task.task_content,
                        "sample_content": sample.sample_content,
                        "translation": sample.translation if edition == "teacher" else None,
                        "word_count": sample.word_count,
                        "highlighted_sentences": highlighted if isinstance(highlighted, list) else [],
                        "source": {
                            "year": task.paper.year if task.paper else None,
                            "region": task.paper.region if task.paper else None,
                            "exam_type": task.paper.exam_type if task.paper else None,
                            "semester": task.paper.semester if task.paper else None,
                        },
                    }
                )
                if len(samples) >= 5:
                    break
            if len(samples) >= 5:
                break

        return {
            "group_category": self._category_to_dict(group_category),
            "major_category": self._category_to_dict(major_category),
            "category": self._category_to_dict(category),
            "summary": {
                "group_name": group_category.name,
                "major_category_name": major_category.name,
                "category_name": category.name,
                "task_count": len(tasks),
                "sample_count": sum(min(len(task.samples or []), 1) for task in tasks),
                "recent_years": years[-3:],
                "applicable_ranges": applicable_ranges,
            },
            "frameworks": [self._build_framework_from_template(category, template)],
            "expressions": self._build_expressions_from_template(template),
            "samples": samples,
        }

    def _build_framework_from_template(self, category: WritingCategory, template: WritingTemplate) -> Dict:
        opening_sentences = self._parse_json_list(template.opening_sentences)
        closing_sentences = self._parse_json_list(template.closing_sentences)
        structure_text = template.structure or ""
        sections = [
            {
                "name": "结构定位",
                "description": structure_text or f"{category.name}常用写作结构",
                "examples": opening_sentences[:2],
            },
            {
                "name": "开头句",
                "description": "适合该子类的开头方式",
                "examples": opening_sentences[:4],
            },
            {
                "name": "结尾句",
                "description": "适合该子类的收束与升华方式",
                "examples": closing_sentences[:4],
            },
        ]
        return {
            "title": f"{category.name}通用模板",
            "category_name": category.name,
            "sections": sections,
        }

    def _build_expressions_from_template(self, template: WritingTemplate) -> List[Dict]:
        expressions = []
        for label, raw_value, limit in (
            ("开头句型", template.opening_sentences, 8),
            ("结尾句型", template.closing_sentences, 8),
            ("过渡词汇", template.transition_words, 12),
            ("高级词汇", template.advanced_vocabulary, 12),
        ):
            items = self._normalize_expression_items(raw_value)[:limit]
            if items:
                expressions.append({"category": label, "items": items})
        return expressions

    def _normalize_expression_items(self, raw_value: Optional[str]) -> List[str]:
        parsed = self._parse_json(raw_value)
        if not parsed:
            return []
        items: List[str] = []
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, str):
                    items.append(item)
                elif isinstance(item, dict):
                    word = item.get("word") or item.get("basic") or ""
                    usage = item.get("usage") or ""
                    items.append(f"{word}（{usage}）" if usage else str(word))
        elif isinstance(parsed, dict):
            for key, value in parsed.items():
                items.append(f"{key}: {value}")
        return [item for item in items if item]

    def _parse_json(self, raw_value: Optional[str]):
        if not raw_value:
            return None
        try:
            return json.loads(raw_value)
        except Exception:
            return raw_value

    def _parse_json_list(self, raw_value: Optional[str]) -> List[str]:
        parsed = self._parse_json(raw_value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if item]
        return []

    def _normalize_template_text(self, value) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return ""
            if stripped.startswith(("{", "[")):
                try:
                    parsed = json.loads(stripped)
                    return self._normalize_template_text(parsed)
                except Exception:
                    pass
            dict_blocks = re.findall(r"\{[^{}]+\}", stripped)
            if dict_blocks and len(dict_blocks) >= 2:
                lines = []
                for block in dict_blocks:
                    try:
                        parsed = json.loads(block)
                    except json.JSONDecodeError:
                        continue
                    line = self._format_structure_line(parsed)
                    if line:
                        lines.append(line)
                if lines:
                    return "\n".join(lines)
            return value
        if isinstance(value, list):
            lines = []
            for item in value:
                if isinstance(item, dict):
                    line = self._format_structure_line(item)
                    if line:
                        lines.append(line)
                elif item:
                    lines.append(str(item))
            return "\n".join(lines)
        if isinstance(value, dict):
            line = self._format_structure_line(value)
            return line if line else json.dumps(value, ensure_ascii=False)
        return str(value)

    def _normalize_template_json(self, value) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return json.dumps(value, ensure_ascii=False)

    def _parse_template_paragraph_count(self, structure_text: Optional[str]) -> int:
        """从模板 structure 字段解析段落数。"""
        if not structure_text:
            return 0
        stripped = structure_text.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                return len([p for p in parsed if isinstance(p, dict)])
            except (json.JSONDecodeError):
                pass
        return len(re.findall(r"第\d+段", structure_text))

    def _count_paragraphs(self, text: str) -> int:
        """统计英文范文的段落数（以空行分隔）。"""
        if not text:
            return 0
        return len([p.strip() for p in text.split("\n\n") if p.strip()])

    def _build_source_line(self, paper: Optional[ExamPaper]) -> str:
        if not paper:
            return ""
        parts = [str(paper.year) if paper.year else "", paper.region or "", paper.exam_type or ""]
        return " ".join(part for part in parts if part)

    def _format_structure_line(self, item: dict) -> str:
        paragraph = item.get("paragraph") or item.get("section") or item.get("part")
        function = item.get("function") or item.get("goal") or item.get("focus")
        word_count = item.get("word_count") or item.get("suggestion_words") or item.get("suggested_words")
        parts = []
        if paragraph:
            parts.append(f"第{paragraph}段")
        if function:
            parts.append(str(function))
        line = "：".join(parts) if parts else ""
        if word_count:
            suffix = f"（建议 {word_count} 词）"
            return f"{line}{suffix}" if line else suffix
        return line

    def _category_to_dict(self, category: WritingCategory) -> Dict:
        return {
            "id": category.id,
            "code": category.code,
            "name": category.name,
            "level": category.level,
            "parent_id": category.parent_id,
            "path": category.path,
            "template_key": category.template_key,
        }

    def _shorten(self, text: str, length: int) -> str:
        cleaned = re.sub(r"\s+", " ", text or "").strip()
        if len(cleaned) <= length:
            return cleaned
        return f"{cleaned[:length].rstrip()}..."

    async def reclassify_all_tasks(self, limit: Optional[int] = None, batch_size: int = 25) -> Dict[str, int]:
        """全量重分类旧作文数据。"""
        query = select(WritingTask).order_by(WritingTask.id)
        if limit:
            query = query.limit(limit)
        result = await self.db.execute(query)
        tasks = list(result.scalars().all())

        classified = 0
        failed = 0
        for index, task in enumerate(tasks, start=1):
            category_result = await self.classify_task(task)
            if category_result.success:
                classified += 1
            else:
                failed += 1
            if index % batch_size == 0:
                await self.db.commit()
                logger.info("作文重分类进度：%s/%s", index, len(tasks))
        await self.db.commit()
        return {"classified": classified, "failed": failed}

    async def reset_templates_for_categories(self) -> int:
        """将已有作文范文的模板重新指向按子类生成的新模板。"""
        tasks_result = await self.db.execute(
            select(WritingTask)
            .options(
                selectinload(WritingTask.samples),
                selectinload(WritingTask.category),
            )
            .where(WritingTask.category_id.isnot(None))
        )
        tasks = list(tasks_result.scalars().all())

        updated_samples = 0
        for task in tasks:
            template = await self.get_or_create_template(task.category_id)
            for sample in task.samples:
                if sample.template_id != template.id:
                    sample.template_id = template.id
                    updated_samples += 1
        await self.db.commit()
        return updated_samples

    def _apply_exam_paper_filter(self, query, paper_ids: Optional[List[int]]):
        normalized_ids = [paper_id for paper_id in (paper_ids or []) if paper_id is not None]
        if normalized_ids:
            query = query.where(ExamPaper.id.in_(normalized_ids))
        return query
