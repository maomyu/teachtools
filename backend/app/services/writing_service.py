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
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func, select, update
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

    def _sample_meets_quality_bar(
        self,
        sample: Optional[WritingSample],
        *,
        expected_template_id: Optional[int] = None,
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

        actual_word_count = sample.word_count or self._count_english_words(sample.sample_content)
        if not (SAMPLE_MIN_WORDS <= actual_word_count <= SAMPLE_MAX_WORDS):
            return False

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
        """按作文子类模板生成范文。"""
        result = await self.db.execute(
            select(WritingTask)
            .options(
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

        template: Optional[WritingTemplate] = None
        if template_id:
            template_result = await self.db.execute(select(WritingTemplate).where(WritingTemplate.id == template_id))
            template = template_result.scalar_one_or_none()
        if template is None:
            template = await self.get_or_create_template(
                task.category_id,
                anchor_task=task,
                force_refresh=force_template_refresh,
            )

        prompt = self._build_sample_prompt(
            task=task,
            category=task.category,
            major_category=task.major_category,
            group_category=task.group_category,
            template_content=template.template_content if template else "",
            tips=template.tips if template and template.tips else "",
            structure=template.structure if template and template.structure else "",
        )

        result_text = ""
        english_essay = ""
        chinese_translation: Optional[str] = None
        word_count = 0

        for attempt in range(3):
            result_text = await self.ai_service.chat_async(
                prompt,
                system_prompt="你是北京中考英语写作教学专家。",
                operation="writing_service.generate_sample",
            )
            if not result_text:
                raise ValueError("AI 生成范文失败：返回内容为空")

            english_essay, chinese_translation = self._parse_essay_with_translation(result_text)
            word_count = self._count_english_words(english_essay)
            logger.info("作文范文生成尝试 %s/3，字数=%s", attempt + 1, word_count)

            if SAMPLE_MIN_WORDS <= word_count <= SAMPLE_MAX_WORDS:
                break
            prompt = (
                f"{prompt}\n\n"
                f"⚠️ 上一次英文范文约 {word_count} 词，不符合要求。请重新生成，并将英文部分控制在 {SAMPLE_MIN_WORDS}-{SAMPLE_MAX_WORDS} 词之间，"
                "不要省略要点，也不要写成长篇教学范文。"
            )
            # 段落结构校验
            template_para_count = self._parse_template_paragraph_count(template.structure if template else "")
            if template_para_count > 0:
                essay_para_count = self._count_paragraphs(english_essay)
                if essay_para_count != template_para_count:
                    logger.warning(
                        "范文段落数(%s)与模板(%s)不一致, task_id=%s",
                        essay_para_count, template_para_count, task.id,
                    )
                    if attempt < 2:
                        prompt += (
                            f"\n\n⚠️ 上一次范文有 {essay_para_count} 个段落，"
                            f"但模板要求 {template_para_count} 个段落。请严格对齐。"
                        )

        revision_round = 0
        while english_essay and not (SAMPLE_MIN_WORDS <= word_count <= SAMPLE_MAX_WORDS) and revision_round < 3:
            english_essay, word_count = await self._revise_essay_length(
                essay=english_essay,
                task=task,
                category=task.category,
                major_category=task.major_category,
                group_category=task.group_category,
                min_words=SAMPLE_MIN_WORDS,
                max_words=SAMPLE_MAX_WORDS,
            )
            revision_round += 1

        if english_essay and not (SAMPLE_MIN_WORDS <= word_count <= SAMPLE_MAX_WORDS):
            fallback_prompt = (
                f"{self._build_sample_prompt(task, task.category, task.major_category, task.group_category, template.template_content if template else '', template.tips if template and template.tips else '', template.structure if template and template.structure else '')}\n\n"
                f"⚠️ 最终要求再强调一次：只输出英文范文和中文翻译，英文部分必须在 {SAMPLE_MIN_WORDS}-{SAMPLE_MAX_WORDS} 词之间,"
                "理想区间为 145-155 词。请适度增加细节、原因、感受和结尾升华。"
            )
            result_text = await self.ai_service.chat_async(
                fallback_prompt,
                system_prompt="你是严格执行字数要求的北京中考英语写作教学专家。",
                operation="writing_service.generate_sample_fallback",
            )
            if result_text:
                english_essay, chinese_translation = self._parse_essay_with_translation(result_text)
                word_count = self._count_english_words(english_essay)

        if not chinese_translation and english_essay:
            translation_prompt = f"请将下面英文范文翻译成自然流畅的中文，保持段落对应：\n\n{english_essay}"
            chinese_translation = await self.ai_service.chat_async(
                translation_prompt,
                system_prompt="你是专业英汉翻译。",
                operation="writing_service.translate_sample",
            )

        if english_essay:
            word_count = self._count_english_words(english_essay)

        if not english_essay or not english_essay.strip():
            raise ValueError("AI 生成范文失败：英文范文为空")

        if not chinese_translation or not chinese_translation.strip():
            raise ValueError("AI 生成范文失败：中文翻译为空")

        if not (SAMPLE_MIN_WORDS <= word_count <= SAMPLE_MAX_WORDS):
            raise ValueError(
                f"AI 生成范文失败：英文范文字数 {word_count} 不在 {SAMPLE_MIN_WORDS}-{SAMPLE_MAX_WORDS} 词之间"
            )

        sample = WritingSample(
            task_id=task.id,
            template_id=template.id if template else None,
            sample_content=english_essay or result_text,
            sample_type="AI生成",
            score_level=score_level,
            word_count=word_count,
            translation=chinese_translation,
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

    def _build_template_fallback(self, category: WritingCategory) -> Dict[str, object]:
        path = category.path or category.name
        is_letter = any(keyword in path for keyword in LETTER_CATEGORY_KEYWORDS)
        is_speech = any(keyword in path for keyword in SPEECH_CATEGORY_KEYWORDS)

        if is_letter:
            template_content = (
                "Dear [name],\n\n"
                "I am writing to [purpose].\n"
                "First of all, [key point 1]. Besides, [key point 2]. "
                "What's more, [key point 3 or reason].\n"
                "I hope [expectation]. Please let me know [reply request].\n\n"
                "Best wishes,\n"
                "Li Hua"
            )
            structure = "\n".join(
                [
                    "第1段：称呼并说明写作目的（30-40词）",
                    f"第2段：围绕“{category.name}”展开核心信息和细节（70-80词）",
                    "第3段：表达期待、收束全文并署名（30-40词）",
                ]
            )
        elif is_speech:
            template_content = (
                "Hello everyone,\n\n"
                "Today I want to talk about [topic].\n"
                "First of all, [main point 1]. Then, [main point 2]. "
                "Finally, [call to action or conclusion].\n\n"
                "Thank you for listening."
            )
            structure = "\n".join(
                [
                    "第1段：开场点题，说明讲话目的（30-40词）",
                    f"第2段：结合“{category.name}”展开主体内容（70-80词）",
                    "第3段：总结观点并呼吁/致谢（30-40词）",
                ]
            )
        else:
            template_content = (
                "I would like to share [topic/event].\n"
                "First of all, [background or main point]. Then, [detail or action]. "
                "After that, [result or another detail].\n"
                "In the end, I learned that [feeling or reflection]."
            )
            structure = "\n".join(
                [
                    "第1段：引入主题，交代背景或观点（35-45词）",
                    f"第2段：围绕“{category.name}”展开关键内容（65-80词）",
                    "第3段：总结感受、启示或个人态度（30-40词）",
                ]
            )

        return {
            "template_name": f"{category.name}通用模板",
            "template_content": template_content,
            "structure": structure,
            "tips": "紧扣题干信息点，优先覆盖场景、细节、原因与感受；句子保持自然可迁移。",
            "opening_sentences": [
                f"I would like to share something about {category.name}.",
                "I'm glad to write about this topic today.",
            ],
            "closing_sentences": [
                "I hope my ideas can be helpful.",
                "This is how I would deal with the topic.",
            ],
            "transition_words": ["First of all,", "Then,", "Besides,", "In the end,"],
            "advanced_vocabulary": [{"word": "meaningful", "basic": "good", "usage": "描述活动或经历有意义"}],
            "grammar_points": ["注意时态统一，根据信件或记叙场景选择一般现在时或一般过去时。"],
            "scoring_criteria": {
                "content": "覆盖题干要点",
                "language": "句式自然、表达准确",
                "structure": "段落清楚、过渡自然",
            },
        }

    def _should_refresh_template(self, template: WritingTemplate, category: WritingCategory) -> bool:
        content = (template.template_content or "").strip()
        structure = (template.structure or "").strip()
        is_letter = any(keyword in (category.path or category.name) for keyword in LETTER_CATEGORY_KEYWORDS)

        if not content:
            return True
        if not is_letter and re.search(r"(?i)\bDear\b|\bBest wishes\b|\bYours\b", content):
            return True
        if "paragraph" in structure and "{" in structure:
            return True
        if not (template.opening_sentences and template.closing_sentences):
            return True
        return False

    async def get_or_create_template(
        self,
        category_id: int,
        anchor_task: Optional[WritingTask] = None,
        force_refresh: bool = False,
        refresh_if_stale: bool = True,
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
            if not refresh_if_stale:
                return template
            if not self._should_refresh_template(template, category):
                return template

        parent = category.parent
        group = parent.parent if parent and parent.parent else parent

        example_tasks = await self._load_category_example_tasks(category_id, anchor_task=anchor_task, limit=5)
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
        if not template_data or not template_data.get("template_content"):
            template_data = self._build_template_fallback(category)

        template_name = self._normalize_template_text(
            template_data.get("template_name", f"{category.name}通用模板")
        )
        template_content = self._normalize_template_text(template_data.get("template_content", ""))
        tips = self._normalize_template_text(template_data.get("tips", ""))
        structure = self._normalize_template_text(template_data.get("structure", ""))
        opening_sentences = self._normalize_template_json(template_data.get("opening_sentences"))
        closing_sentences = self._normalize_template_json(template_data.get("closing_sentences"))
        transition_words = self._normalize_template_json(template_data.get("transition_words"))
        advanced_vocabulary = self._normalize_template_json(template_data.get("advanced_vocabulary"))
        grammar_points = self._normalize_template_json(template_data.get("grammar_points"))
        scoring_criteria = self._normalize_template_json(template_data.get("scoring_criteria"))

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
        result = await self.db.execute(
            select(WritingTask)
            .options(
                selectinload(WritingTask.samples),
                selectinload(WritingTask.category),
                selectinload(WritingTask.major_category),
                selectinload(WritingTask.group_category),
                selectinload(WritingTask.paper),
            )
            .where(WritingTask.id == task_id)
        )
        task = result.scalar_one_or_none()

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
        )

        existing_sample = next(
            (
                sample
                for sample in sorted(task.samples or [], key=lambda item: item.id or 0, reverse=True)
                if sample.sample_type == "AI生成"
            ),
            None,
        )
        if existing_sample and not regenerate_sample:
            if self._sample_meets_quality_bar(existing_sample, expected_template_id=template.id):
                return task, template, existing_sample

            await self.db.delete(existing_sample)
            await self.db.flush()

        last_error: Optional[Exception] = None
        for attempt in range(1, 4):
            try:
                sample = await self.generate_sample(
                    task_id=task.id,
                    template_id=template.id,
                    score_level=score_level,
                    force_template_refresh=False,
                )
                return task, template, sample
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "作文范文生成重试 %s/3 失败 task_id=%s: %s",
                    attempt,
                    task.id,
                    exc,
                )

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
            for sample in task.samples:
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
                "sample_count": sum(len(task.samples) for task in tasks),
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
