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

        routed_leaves, direct_match = self._route_candidates(
            leaves,
            content=content,
            requirements=requirements,
            extracted_writing_type=extracted_writing_type,
            extracted_application_type=extracted_application_type,
        )
        if direct_match is not None:
            candidate = direct_match
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

        heuristic = self._heuristic_match(
            routed_leaves,
            content=content,
            requirements=requirements,
            extracted_writing_type=extracted_writing_type,
            extracted_application_type=extracted_application_type,
        )

        ai_result = await self._ai_match(
            routed_leaves,
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

    def _normalize_text(self, *parts: Optional[str]) -> str:
        return re.sub(r"\s+", " ", " ".join(part or "" for part in parts)).strip().lower()

    def _contains_any(self, text: str, keywords: List[str]) -> List[str]:
        return [keyword for keyword in keywords if keyword and keyword.lower() in text]

    def _filter_by_names(self, leaves: List[WritingCategory], names: List[str]) -> List[WritingCategory]:
        name_set = set(names)
        return [leaf for leaf in leaves if leaf.name in name_set]

    def _route_candidates(
        self,
        leaves: List[WritingCategory],
        *,
        content: str,
        requirements: str,
        extracted_writing_type: Optional[str],
        extracted_application_type: Optional[str],
    ) -> tuple[List[WritingCategory], Optional[WritingCategoryResult]]:
        normalized = self._normalize_text(content, requirements, extracted_writing_type, extracted_application_type)
        if not normalized:
            return leaves, None

        matched_letter_style_keywords = self._contains_any(
            normalized,
            [
                "write an email",
                "write a letter",
                "写一封邮件",
                "写封邮件",
                "写一封电子邮件",
                "写封电子邮件",
                "写一封信",
                "写封信",
                "笔友",
                "网友",
                "exchange student",
                "交换生",
            ],
        )
        matched_reply_keywords = self._contains_any(
            normalized,
            [
                "reply",
                "reply to",
                "write back",
                "回信",
                "回邮件",
                "回复来信",
                "回复邮件",
                "回复一封邮件",
                "回复一封信",
                "发来邮件",
                "来信",
            ],
        )
        matched_submission_keywords = self._contains_any(
            normalized,
            ["message", "comment", "留言", "投稿", "征稿", "征集", "公众号", "official account", "share"],
        )
        matched_invitation_keywords = self._contains_any(normalized, ["invite", "invitation", "邀请"])
        matched_mail_keywords = self._contains_any(normalized, ["email", "e-mail", "mail", "邮件", "电子邮件"])
        matched_advice_keywords = self._contains_any(
            normalized,
            [
                "advice",
                "suggestion",
                "suggest",
                "建议",
                "提建议",
                "求助",
                "听听你的建议",
                "how should",
                "what should",
                "what can",
                "problem",
                "trouble",
                "压力",
                "矛盾",
                "friendship",
                "friends",
                "交朋友",
                "worry",
                "stress",
                "help her",
                "help him",
                "缓解压力",
                "增强信心",
            ],
        )
        matched_intro_info_keywords = self._contains_any(
            normalized,
            [
                "introduce",
                "introduction",
                "介绍",
                "culture",
                "manners",
                "礼仪",
                "room",
                "family",
                "家人",
                "房间",
                "festival",
                "school",
                "social manners",
                "chopsticks",
                "shake hands",
            ],
        )
        matched_activity_info_keywords = self._contains_any(
            normalized,
            [
                "activity",
                "activities",
                "event",
                "week",
                "party",
                "competition",
                "lecture",
                "speech",
                "分享会",
                "活动",
                "比赛",
                "讲座",
                "time",
                "place",
                "when",
                "where",
                "prepare",
                "rules",
                "集合",
                "地点",
                "时间",
                "注意事项",
            ],
        )
        matched_note_keywords = self._contains_any(
            normalized,
            ["note", "leave a message", "留言条", "便条", "message to", "return home", "回家的时间", "回家的方式"],
        )
        matched_room_keywords = self._contains_any(
            normalized,
            ["room", "bed", "desk", "books", "computer", "family", "家人", "房间", "my room", "room like"],
        )
        matched_person_intro_keywords = self._contains_any(
            normalized,
            [
                "guiding star",
                "role model",
                "hero",
                "teacher",
                "scientist",
                "inventor",
                "mother",
                "father",
                "friend",
                "person",
                "he/she",
                "who is your",
                "榜样",
                "启发你的人",
                "影响你的人",
            ],
        )
        matched_general_intro_topic_keywords = self._contains_any(
            normalized,
            [
                "book",
                "story",
                "reading",
                "museum",
                "place",
                "city",
                "hometown",
                "festival",
                "holiday",
                "home",
                "school day",
                "english learning",
                "learning experience",
                "favorite place",
                "my home",
                "my room",
            ],
        )
        matched_notice_format_keywords = self._contains_any(
            normalized,
            ["notice", "student union", "students' union", "dear foreign students", "学生会"],
        )
        matched_proposal_keywords = self._contains_any(
            normalized,
            ["倡议", "倡议书", "call on", "号召"],
        )
        has_dear_closing = "dear " in normalized or "best wishes" in normalized or "yours" in normalized
        matched_email_style = bool(
            matched_mail_keywords or matched_reply_keywords or matched_letter_style_keywords or has_dear_closing
        )
        matched_strict_letter_context = bool(
            matched_mail_keywords or matched_reply_keywords or matched_letter_style_keywords
        )

        if matched_proposal_keywords and not matched_reply_keywords and not matched_strict_letter_context:
            candidates = self._filter_by_names(leaves, ["倡议书"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.98,
                    reasoning="命中倡议/号召强规则，归入倡议书",
                    matched_keywords=matched_proposal_keywords,
                )

        if self._contains_any(normalized, ["dear teachers and fellows", "thanks for listening"]) and not matched_advice_keywords:
            candidates = self._filter_by_names(leaves, ["演讲稿"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.99,
                    reasoning="命中演讲稿固定开头/结尾强规则，归入演讲稿",
                    matched_keywords=self._contains_any(normalized, ["dear teachers and fellows", "thanks for listening"]),
                )

        if self._contains_any(
            normalized,
            ["演讲稿", "speech competition", "演讲比赛", "give a speech"],
        ) and not matched_email_style and not matched_advice_keywords:
            candidates = self._filter_by_names(leaves, ["演讲稿"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.98,
                    reasoning="命中演讲稿/演讲比赛强规则，归入演讲稿",
                    matched_keywords=self._contains_any(
                        normalized,
                        ["演讲稿", "speech competition", "演讲比赛", "give a speech"],
                    ),
                )

        if not matched_proposal_keywords and matched_notice_format_keywords and self._contains_any(
            normalized,
            ["notice", "student union", "students' union", "dear foreign students", "学生会"],
        ):
            candidates = self._filter_by_names(leaves, ["通知"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.98,
                    reasoning="命中通知标题/学生会公告强规则，归入通知",
                    matched_keywords=matched_notice_format_keywords,
                )

        if matched_note_keywords and self._contains_any(normalized, ["where", "when", "how", "go boating", "watch a movie", "return"]):
            candidates = self._filter_by_names(leaves, ["行程安排"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.96,
                    reasoning="命中留言条/便条+出行安排强规则，归入行程安排",
                    matched_keywords=matched_note_keywords,
                )

        if matched_email_style and matched_invitation_keywords:
            matched = self._contains_any(
                normalized,
                ["invite", "invitation", "邀请", "email", "e-mail", "mail", "电子邮件", "写一封邮件"],
            )
            candidates = self._filter_by_names(leaves, ["活动邀请邮件"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.98,
                    reasoning="命中邀请邮件强规则",
                    matched_keywords=matched,
                )

        if matched_email_style and matched_activity_info_keywords and self._contains_any(
            normalized,
            ["exchange student", "交换生", "peter", "sam", "mr. smith", "mr smith", "参加", "share", "english week"],
        ) and not matched_advice_keywords and not matched_reply_keywords:
            candidates = self._filter_by_names(leaves, ["活动邀请邮件"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.95,
                    reasoning="命中活动信息邮件强规则，归入活动邀请邮件",
                    matched_keywords=matched_activity_info_keywords,
                )

        if self._contains_any(
            normalized,
            ["green life", "green lifestyle", "绿色生活", "low-carbon", "低碳", "环保", "turn off", "ride", "save water"],
        ):
            candidates = self._filter_by_names(leaves, ["环保行动"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.95,
                    reasoning="命中绿色生活/低碳环保强规则，归入环保行动",
                    matched_keywords=self._contains_any(
                        normalized,
                        ["green life", "green lifestyle", "绿色生活", "low-carbon", "低碳", "环保"],
                    ),
                )

        if matched_email_style and matched_advice_keywords:
            candidates = self._filter_by_names(leaves, ["建议信"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.97,
                    reasoning="命中邮件/书信+建议类强规则，归入建议信",
                    matched_keywords=matched_advice_keywords,
                )

        if matched_mail_keywords and self._contains_any(
            normalized,
            ["笔友", "pen pal", "想了解", "询问", "提出的问题", "发邮件询问", "来信询问"],
        ):
            candidates = self._filter_by_names(leaves, ["回信"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.95,
                    reasoning="命中笔友/邮件询问信息强规则，归入回信",
                    matched_keywords=self._contains_any(
                        normalized,
                        ["笔友", "pen pal", "想了解", "询问", "提出的问题", "发邮件询问", "来信询问"],
                    ),
                )

        if matched_reply_keywords:
            candidates = self._filter_by_names(leaves, ["回信"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.95,
                    reasoning="命中回复来信/邮件强规则，归入回信",
                    matched_keywords=matched_reply_keywords,
                )

        if matched_reply_keywords and matched_intro_info_keywords:
            candidates = self._filter_by_names(leaves, ["回信"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.95,
                    reasoning="命中回复来信并介绍信息强规则，归入回信",
                    matched_keywords=matched_reply_keywords + matched_intro_info_keywords,
                )

        if matched_reply_keywords and matched_activity_info_keywords:
            candidates = self._filter_by_names(leaves, ["回信"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.94,
                    reasoning="命中回复来信并介绍活动信息强规则，归入回信",
                    matched_keywords=matched_reply_keywords + matched_activity_info_keywords,
                )

        if matched_email_style and matched_intro_info_keywords and matched_room_keywords:
            candidates = self._filter_by_names(leaves, ["回信"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.93,
                    reasoning="命中邮件+介绍家人/房间等信息强规则，归入回信",
                    matched_keywords=matched_intro_info_keywords + matched_room_keywords,
                )

        if matched_submission_keywords and not matched_strict_letter_context and matched_person_intro_keywords:
            candidates = self._filter_by_names(leaves, ["人物介绍"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.95,
                    reasoning="命中征文投稿且主题为人物/榜样介绍，归入人物介绍",
                    matched_keywords=matched_submission_keywords + matched_person_intro_keywords,
                )

        if matched_submission_keywords and not matched_strict_letter_context and (
            matched_room_keywords or matched_general_intro_topic_keywords
        ):
            candidates = self._filter_by_names(leaves, ["活动介绍"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.94,
                    reasoning="命中征文投稿且主题为介绍说明类短文，归入活动介绍",
                    matched_keywords=matched_submission_keywords + matched_room_keywords + matched_general_intro_topic_keywords,
                )

        if matched_submission_keywords and matched_advice_keywords and matched_activity_info_keywords:
            candidates = self._filter_by_names(leaves, ["建议信"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.93,
                    reasoning="命中征集建议且主题是活动方案/内容建议，归入建议信",
                    matched_keywords=matched_submission_keywords + matched_advice_keywords,
                )

        if matched_submission_keywords and not matched_reply_keywords and not (matched_invitation_keywords and matched_mail_keywords):
            filtered = [
                leaf
                for leaf in leaves
                if not any(keyword in (leaf.path or leaf.name) for keyword in ("信", "邮件", "回信", "感谢信", "道歉信"))
            ]
            if filtered:
                leaves = filtered

        if matched_submission_keywords and self._contains_any(
            normalized,
            ["hobby", "爱好", "reading", "travel", "sport", "球场", "背包旅行", "培养过程"],
        ):
            candidates = self._filter_by_names(leaves, ["兴趣培养"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.95,
                    reasoning="公众号/留言素材征集且主题是兴趣爱好，直接归入兴趣培养",
                    matched_keywords=self._contains_any(
                        normalized,
                        ["hobby", "爱好", "reading", "travel", "sport", "培养过程"],
                    ),
                )

        if matched_submission_keywords and self._contains_any(
            normalized,
            ["festival", "节日", "traditional culture", "传统文化", "mooncake", "dragon boat", "春节", "中秋"],
        ):
            candidates = self._filter_by_names(leaves, ["节日习俗", "传统文化", "文化传播"])
            if candidates:
                return candidates, None

        if self._contains_any(
            normalized,
            ["diligence", "hard work", "勤奋", "努力", "坚持不懈", "prepare for", "win", "proud", "成功的经历"],
        ):
            candidates = self._filter_by_names(leaves, ["坚持成长"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.94,
                    reasoning="命中勤奋努力取得成功强规则，归入坚持成长",
                    matched_keywords=self._contains_any(
                        normalized,
                        ["diligence", "hard work", "勤奋", "努力", "坚持不懈", "prepare for", "win", "proud"],
                    ),
                )

        if matched_invitation_keywords:
            matched = self._contains_any(
                normalized,
                ["invite", "invitation", "邀请", "email", "e-mail", "mail", "电子邮件", "电子邮件", "写一封邮件"],
            )
            if matched_mail_keywords:
                candidates = self._filter_by_names(leaves, ["活动邀请邮件"])
                if candidates:
                    return candidates, WritingCategoryResult(
                        success=True,
                        category=candidates[0],
                        confidence=0.97,
                        reasoning="命中邀请邮件强规则",
                        matched_keywords=matched,
                    )
            candidates = self._filter_by_names(leaves, ["邀请信", "邀请回复信", "活动邀请邮件"])
            if candidates:
                return candidates, None

        matched_recommend_keywords = self._contains_any(
            normalized,
            ["recommend", "recommendation", "建议去", "推荐", "推荐给", "推荐一处", "推荐一个"],
        )
        if matched_recommend_keywords:
            if self._contains_any(
                normalized,
                [
                    "park", "place", "hometown", "city", "beijing", "destination", "trip", "visit",
                    "travel", "food", "places of interest", "景点", "家乡", "城市", "公园", "旅游",
                ],
            ):
                candidates = self._filter_by_names(leaves, ["介绍信"])
                if candidates:
                    return candidates, WritingCategoryResult(
                        success=True,
                        category=candidates[0],
                        confidence=0.95,
                        reasoning="命中推荐地点/城市/景点强规则，归入介绍信",
                        matched_keywords=matched_recommend_keywords,
                    )
            if self._contains_any(
                normalized,
                ["club", "activity", "event", "sports club", "english club", "社团", "活动", "俱乐部"],
            ):
                candidates = self._filter_by_names(leaves, ["活动介绍"])
                if candidates:
                    return candidates, WritingCategoryResult(
                        success=True,
                        category=candidates[0],
                        confidence=0.93,
                        reasoning="命中推荐社团/活动强规则，归入活动介绍",
                        matched_keywords=matched_recommend_keywords,
                    )

        direct_rules: List[tuple[List[str], str, str]] = [
            (["dream school", "my dream", "梦想", "future goal", "未来目标"], "梦想目标", "命中梦想目标强规则"),
            (["竞选", "run for", "candidate"], "竞选稿", "命中竞选类强规则"),
            (["speech", "演讲", "talk", "speak to", "speak in front of"], "演讲稿", "命中演讲类强规则"),
            (["notice", "通知"], "通知", "命中通知类强规则"),
            (["倡议", "proposal", "call on"], "倡议书", "命中倡议类强规则"),
            (["感谢", "thank", "appreciate"], "感谢信", "命中感谢类强规则"),
            (["道歉", "apolog", "sorry for"], "道歉信", "命中道歉类强规则"),
            (["申请", "apply for", "application"], "申请信", "命中申请类强规则"),
            (["self-recommend", "self recommendation", "自荐"], "自荐信", "命中自荐类强规则"),
            (["求助", "ask for help", "need help"], "求助信", "命中求助类强规则"),
            (["建议信", "advice letter"], "建议信", "命中建议信强规则"),
            (["invitation reply", "reply to the invitation", "回复邀请"], "邀请回复信", "命中邀请回复类强规则"),
        ]
        for keywords, category_name, reason in direct_rules:
            matched = self._contains_any(normalized, keywords)
            if not matched:
                continue
            if category_name == "演讲稿" and (matched_strict_letter_context or matched_email_style or matched_advice_keywords):
                continue
            if category_name == "倡议书" and matched_strict_letter_context:
                continue
            if category_name == "通知" and matched_strict_letter_context and not matched_notice_format_keywords:
                continue
            candidates = self._filter_by_names(leaves, [category_name])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.96,
                    reasoning=reason,
                    matched_keywords=matched,
                )

        if self._contains_any(normalized, ["introduce", "introduction", "介绍", "role model", "festival", "school", "activity"]):
            if self._contains_any(
                normalized,
                ["person", "人物", "老师", "母亲", "father", "mother", "role model", "榜样", "hero"],
            ):
                candidates = self._filter_by_names(leaves, ["人物介绍"])
                if candidates:
                    return candidates, WritingCategoryResult(
                        success=True,
                        category=candidates[0],
                        confidence=0.93,
                        reasoning="命中人物介绍强规则",
                        matched_keywords=self._contains_any(normalized, ["person", "人物", "role model", "teacher", "mother"]),
                    )
            if self._contains_any(normalized, ["activity", "event", "活动"]):
                candidates = self._filter_by_names(leaves, ["活动介绍"])
                if candidates:
                    return candidates, WritingCategoryResult(
                        success=True,
                        category=candidates[0],
                        confidence=0.9,
                        reasoning="命中活动介绍强规则",
                        matched_keywords=self._contains_any(normalized, ["activity", "event", "活动"]),
                    )
            candidates = self._filter_by_names(leaves, ["介绍信", "人物介绍", "活动介绍"])
            if candidates:
                return candidates, None

        if self._contains_any(normalized, ["how to", "ways to", "method", "tips on", "方法", "建议大家如何"]):
            candidates = self._filter_by_names(leaves, ["方法介绍"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.9,
                    reasoning="命中方法介绍强规则",
                    matched_keywords=self._contains_any(normalized, ["how to", "ways to", "method", "方法"]),
                )

        if self._contains_any(normalized, ["steps", "process", "流程", "how to make", "制作"]):
            candidates = self._filter_by_names(leaves, ["流程说明"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.92,
                    reasoning="命中流程说明强规则",
                    matched_keywords=self._contains_any(normalized, ["steps", "process", "流程", "how to make"]),
                )

        if self._contains_any(normalized, ["rule", "rules", "must", "shouldn't", "规章", "规则"]):
            candidates = self._filter_by_names(leaves, ["规则说明"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.9,
                    reasoning="命中规则说明强规则",
                    matched_keywords=self._contains_any(normalized, ["rule", "rules", "must", "规则"]),
                )

        if self._contains_any(normalized, ["what do you think", "your opinion", "do you agree", "看法", "观点", "是否同意"]):
            candidates = self._filter_by_names(leaves, ["个人看法", "利弊分析", "现象评价"])
            if candidates:
                return candidates, None

        if self._contains_any(normalized, ["advantages and disadvantages", "pros and cons", "利弊"]):
            candidates = self._filter_by_names(leaves, ["利弊分析"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.94,
                    reasoning="命中利弊分析强规则",
                    matched_keywords=self._contains_any(normalized, ["advantages and disadvantages", "pros and cons", "利弊"]),
                )

        if self._contains_any(normalized, ["phenomenon", "现象", "problem in society", "社会现象"]):
            candidates = self._filter_by_names(leaves, ["现象评价"])
            if candidates:
                return candidates, WritingCategoryResult(
                    success=True,
                    category=candidates[0],
                    confidence=0.9,
                    reasoning="命中现象评价强规则",
                    matched_keywords=self._contains_any(normalized, ["phenomenon", "现象", "社会现象"]),
                )

        return leaves, None

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
