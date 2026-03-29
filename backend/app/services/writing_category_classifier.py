"""
作文分类树分类器

[INPUT]: 依赖数据库中的 writing_categories 分类树和 AI 模型
[OUTPUT]: 对外提供基于数据库分类树的作文自动归类能力
[POS]: backend/app/services 的作文分类树分类器
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.writing import WritingCategory
from app.services.dashscope_runtime import async_chat_completion
from app.writing_category_registry import category_seed_map


logger = logging.getLogger(__name__)


@dataclass
class WritingCategoryResult:
    """作文分类结果。"""

    success: bool
    group_category: Optional[WritingCategory] = None
    major_category: Optional[WritingCategory] = None
    category: Optional[WritingCategory] = None
    confidence: float = 0.0
    reasoning: str = ""
    matched_keywords: List[str] = field(default_factory=list)
    error: Optional[str] = None


class WritingCategoryClassifier:
    """基于数据库分类树的作文分类器。"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.api_key = settings.DASHSCOPE_API_KEY
        self.model = "qwen-turbo"
        self._seed_map = category_seed_map()

    async def classify(
        self,
        content: str,
        requirements: str = "",
        extracted_writing_type: Optional[str] = None,
        extracted_application_type: Optional[str] = None,
    ) -> WritingCategoryResult:
        categories = await self._load_categories()
        leaves = [item for item in categories if item.level == 3 and item.is_active]
        if not leaves:
            return WritingCategoryResult(success=False, error="分类库为空")

        heuristic = self._heuristic_match(
            leaves,
            content=content,
            requirements=requirements,
            extracted_writing_type=extracted_writing_type,
            extracted_application_type=extracted_application_type,
        )

        ai_result = await self._ai_match(
            leaves,
            content=content,
            requirements=requirements,
            extracted_writing_type=extracted_writing_type,
            extracted_application_type=extracted_application_type,
        )

        candidate = ai_result if ai_result.success else heuristic
        if not candidate.success:
            return candidate

        category_map = {item.id: item for item in categories}
        category = candidate.category
        if category is None:
            return WritingCategoryResult(success=False, error="分类结果缺少叶子节点")

        major = category_map.get(category.parent_id) if category.parent_id else None
        group = category_map.get(major.parent_id) if major and major.parent_id else None
        return WritingCategoryResult(
            success=True,
            group_category=group,
            major_category=major,
            category=category,
            confidence=candidate.confidence,
            reasoning=candidate.reasoning,
            matched_keywords=candidate.matched_keywords,
        )

    async def _load_categories(self) -> List[WritingCategory]:
        result = await self.db.execute(
            select(WritingCategory).order_by(WritingCategory.level, WritingCategory.sort_order, WritingCategory.id)
        )
        return list(result.scalars().all())

    async def _ai_match(
        self,
        leaves: List[WritingCategory],
        content: str,
        requirements: str,
        extracted_writing_type: Optional[str],
        extracted_application_type: Optional[str],
    ) -> WritingCategoryResult:
        if not self.api_key:
            return WritingCategoryResult(success=False, error="未配置 DASHSCOPE_API_KEY")

        candidates_text = "\n".join(
            f'- code: "{leaf.code}" | path: "{leaf.path}" | hint: "{(leaf.prompt_hint or "").strip()}"'
            for leaf in leaves
        )
        extract_hint = []
        if extracted_writing_type:
            extract_hint.append(f"提取器粗分类：{extracted_writing_type}")
        if extracted_application_type:
            extract_hint.append(f"提取器应用文提示：{extracted_application_type}")

        prompt = f"""你是北京中考英语作文分类专家。请根据数据库已有分类树，为下面这道作文题选择最合适的叶子子类。

要求：
1. 只能从候选分类中选择，绝对不能自造新类。
2. 优先选择最具体、最适合模板复用教学的叶子子类。
3. 如果题目是邮件、书信、邀请、建议、申请等应用文场景，要优先识别对应信件类。
4. 如果题目是经历、成长、校园、文化、社会实践等叙事题，要优先识别对应记叙子类。
5. 输出严格 JSON，不要解释性文字。

作文题目：
{content}

写作要求：
{requirements or "无"}

辅助提示：
{"；".join(extract_hint) or "无"}

候选叶子分类：
{candidates_text}

请输出：
{{
  "category_code": "候选中的 code",
  "confidence": 0.92,
  "reasoning": "一句话说明为什么归到这个子类",
  "matched_keywords": ["命中的关键词1", "命中的关键词2"]
}}
"""
        try:
            response = await async_chat_completion(
                api_key=self.api_key,
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是严谨的作文分类器，只能输出合法 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                operation="writing_category_classifier.classify",
                timeout_seconds=60.0,
            )
            content_text = response["choices"][0]["message"]["content"]
            json_match = re.search(r"\{.*\}", content_text, re.DOTALL)
            if not json_match:
                return WritingCategoryResult(success=False, error="AI 未返回 JSON")
            data = json.loads(json_match.group())
            category_code = (data.get("category_code") or "").strip()
            category = next((leaf for leaf in leaves if leaf.code == category_code), None)
            if not category:
                return WritingCategoryResult(success=False, error=f"AI 返回未知分类: {category_code}")
            return WritingCategoryResult(
                success=True,
                category=category,
                confidence=float(data.get("confidence") or 0.0),
                reasoning=(data.get("reasoning") or "").strip(),
                matched_keywords=[str(item) for item in (data.get("matched_keywords") or []) if str(item).strip()],
            )
        except Exception as exc:
            logger.warning("作文 AI 分类失败，将回退到启发式: %s", exc)
            return WritingCategoryResult(success=False, error=str(exc))

    def _heuristic_match(
        self,
        leaves: List[WritingCategory],
        content: str,
        requirements: str,
        extracted_writing_type: Optional[str],
        extracted_application_type: Optional[str],
    ) -> WritingCategoryResult:
        combined = f"{content}\n{requirements}".strip().lower()
        normalized = re.sub(r"\s+", " ", combined)
        if not normalized:
            return WritingCategoryResult(success=False, error="内容为空")

        best_leaf: Optional[WritingCategory] = None
        best_score = -1
        best_keywords: List[str] = []

        for leaf in leaves:
            seed = self._seed_map.get(leaf.code, {})
            keywords = [kw.lower() for kw in seed.get("keywords", [])]
            matched = [kw for kw in keywords if kw and kw in normalized]
            score = len(matched) * 3

            path_lower = (leaf.path or "").lower()
            if extracted_writing_type == "应用文" and "应用文" in path_lower:
                score += 2
            if extracted_writing_type == "记叙文" and "记叙文" in path_lower:
                score += 2
            if extracted_application_type and extracted_application_type.lower() in path_lower:
                score += 3

            if score > best_score:
                best_score = score
                best_leaf = leaf
                best_keywords = matched

        if best_leaf is None:
            return WritingCategoryResult(success=False, error="启发式未命中")

        return WritingCategoryResult(
            success=True,
            category=best_leaf,
            confidence=0.66 if best_score > 0 else 0.4,
            reasoning="根据题干关键词和分类提示做启发式归类",
            matched_keywords=best_keywords[:6],
        )
