"""
作文话题分类服务

[INPUT]: 依赖 ai_service.py
[OUTPUT]: 对外提供 classify() 方法进行作文话题分类
[POS]: backend/app/services 的作文话题分类服务
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import json
import re
import logging
import time
from typing import List, Optional
from dataclasses import dataclass

from app.config import settings
from app.services.dashscope_runtime import async_chat_completion, sync_generation_call


logger = logging.getLogger(__name__)


# ==============================================================================
#                              CONSTANTS
# ==============================================================================

WRITING_TOPICS = [
    # 核心话题（与阅读共享）
    "校园生活", "家庭亲情", "兴趣爱好", "节日习俗", "梦想成长",
    "个人成长", "科技生活", "文化交流", "环境保护", "运动健康",
    "传统文化", "志愿服务", "友谊合作", "社会现象",
    # 作文专用扩展话题
    "人物介绍", "活动安排", "经历描述", "观点表达", "问题解决",
    "建议信件", "邀请回复", "感谢道歉", "申请自荐", "通知公告"
]


# ==============================================================================
#                              DATA CLASSES
# ==============================================================================

@dataclass
class WritingTopicResult:
    """作文话题分类结果"""
    success: bool
    primary_topic: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    keywords: List[str] = None
    suggested_aspects: List[str] = None  # 建议写作角度
    error: str = None

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if self.suggested_aspects is None:
            self.suggested_aspects = []


# ==============================================================================
#                              CLASSIFIER
# ==============================================================================

class WritingTopicClassifier:
    """作文话题分类器"""

    CLASSIFY_PROMPT = """你是北京中考英语作文教学专家。
请分析以下作文题目的话题和写作角度。

## 作文题目
{content}

## 具体要求
{requirements}

## 分析步骤
1. 识别题目核心话题（人物/事件/主题）
2. 确定话题所属类别
3. 分析常见写作角度和要点

## 话题池
{topics}

注意：如果以上话题都不匹配，可以根据题目内容补充新的细粒度话题。

## 输出格式（严格JSON）

```json
{{
    "primary_topic": "唯一话题",
    "confidence": 0.95,
    "keywords": ["关键词1", "关键词2"],
    "reasoning": "选择理由",
    "suggested_aspects": ["写作角度1", "写作角度2"]
}}
```"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.DASHSCOPE_API_KEY
        if not self.api_key:
            raise ValueError("请配置DASHSCOPE_API_KEY")

        self.model = "qwen-turbo"

    def _combined_text(self, content: str, requirements: str = "") -> str:
        return "\n".join(part.strip() for part in [content or "", requirements or ""] if part and part.strip())

    def _heuristic_classify(
        self,
        content: str,
        requirements: str = "",
    ) -> WritingTopicResult:
        combined = self._combined_text(content, requirements)
        normalized = re.sub(r"\s+", "", combined)
        if not normalized:
            return WritingTopicResult(success=False, error="内容为空")

        keyword_rules = [
            ("建议信件", ("回信", "来信", "推荐", "建议", "求助")),
            ("邀请回复", ("邀请", "邀请函", "参加", "赴约")),
            ("感谢道歉", ("感谢", "道歉", "抱歉", "致歉")),
            ("申请自荐", ("申请", "自荐", "竞选", "应聘")),
            ("通知公告", ("通知", "公告", "启事")),
            ("经历描述", ("日记", "经历", "度过", "难忘", "一天的活动", "暑假", "寒假")),
            ("活动安排", ("活动安排", "活动计划", "安排", "计划")),
            ("观点表达", ("看法", "观点", "是否", "认为", "你的想法")),
            ("问题解决", ("问题", "如何", "解决", "帮助")),
            ("科技生活", ("发明", "科技", "网络", "互联网", "AI", "电脑", "手机")),
            ("环境保护", ("环保", "环境", "低碳", "垃圾分类")),
            ("运动健康", ("运动", "健康", "锻炼")),
            ("校园生活", ("校园", "学校", "同学", "老师")),
            ("文化交流", ("文化", "传统", "节日", "习俗")),
        ]

        scored: list[tuple[int, str, list[str]]] = []
        for topic, keywords in keyword_rules:
            matched = [keyword for keyword in keywords if keyword in normalized]
            if matched:
                scored.append((len(matched), topic, matched))

        if not scored:
            return WritingTopicResult(success=False, error="启发式未命中")

        scored.sort(key=lambda item: (-item[0], item[1]))
        _, topic, matched_keywords = scored[0]
        return WritingTopicResult(
            success=True,
            primary_topic=topic,
            confidence=0.72,
            reasoning=f"根据题干关键词匹配推断为{topic}",
            keywords=matched_keywords,
            suggested_aspects=[],
        )

    def _build_prompt(
        self,
        content: str,
        requirements: str,
        topics: List[str]
    ) -> str:
        """构建分类 prompt"""
        return self.CLASSIFY_PROMPT.format(
            content=content[:2000] if len(content) > 2000 else content,
            requirements=requirements or "无",
            topics=json.dumps(topics, ensure_ascii=False, indent=2)
        )

    def _parse_response(self, response_text: str) -> WritingTopicResult:
        """解析 AI 响应"""
        try:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return WritingTopicResult(
                    success=True,
                    primary_topic=data.get("primary_topic"),
                    confidence=data.get("confidence", 0.0),
                    reasoning=data.get("reasoning", ""),
                    keywords=data.get("keywords", []),
                    suggested_aspects=data.get("suggested_aspects", [])
                )
        except json.JSONDecodeError as e:
            logger.warning(f"JSON 解析失败: {e}")

        return WritingTopicResult(
            success=False,
            error="无法解析 AI 响应"
        )

    async def classify(
        self,
        content: str,
        requirements: str = "",
        topics: List[str] = None,
        max_retries: int = 2
    ) -> WritingTopicResult:
        """
        分类作文话题

        Args:
            content: 作文题目内容
            requirements: 具体写作要求
            topics: 可选话题列表（默认使用 WRITING_TOPICS）
            max_retries: 最大重试次数（默认 2 次）

        Returns:
            WritingTopicResult
        """
        combined = self._combined_text(content, requirements)
        if not combined or len(combined.strip()) < 20:
            logger.warning(f"内容为空或太短（{len(combined.strip() if combined else 0)} 字符），跳过话题分类")
            return WritingTopicResult(
                success=False,
                error="内容为空或太短"
            )

        if topics is None:
            topics = WRITING_TOPICS

        prompt = self._build_prompt(content, requirements, topics)
        try:
            start_time = time.time()
            response = await async_chat_completion(
                api_key=self.api_key,
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是北京中考英语教研专家，请严格输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                operation="writing_topic_classifier.classify",
                timeout_seconds=60.0,
            )
            elapsed = time.time() - start_time
            result_text = response["choices"][0]["message"]["content"]
            result = self._parse_response(result_text)
            if result.success:
                logger.info(
                    f"话题分类成功: {result.primary_topic} "
                    f"(confidence: {result.confidence:.2f}, 耗时: {elapsed:.2f}s)"
                )
                return result
            heuristic_result = self._heuristic_classify(content, requirements)
            if heuristic_result.success:
                logger.info(f"话题分类回退到启发式: {heuristic_result.primary_topic}")
                return heuristic_result
            logger.error(f"话题分类最终失败: {result.error}")
            return WritingTopicResult(success=False, error=result.error)
        except Exception as e:
            heuristic_result = self._heuristic_classify(content, requirements)
            if heuristic_result.success:
                logger.info(f"话题分类异常后回退到启发式: {heuristic_result.primary_topic}")
                return heuristic_result
            logger.error(f"话题分类最终失败: {e}")
            return WritingTopicResult(
                success=False,
                error=str(e)
            )

    def classify_sync(
        self,
        content: str,
        requirements: str = "",
        topics: List[str] = None,
        max_retries: int = 2
    ) -> WritingTopicResult:
        """
        同步版本的话题分类（用于脚本）

        Args:
            content: 作文题目内容
            requirements: 具体写作要求
            topics: 可选话题列表
            max_retries: 最大重试次数

        Returns:
            WritingTopicResult
        """
        combined = self._combined_text(content, requirements)
        if not combined or len(combined.strip()) < 20:
            logger.warning(f"内容为空或太短（{len(combined.strip() if combined else 0)} 字符），跳过话题分类")
            return WritingTopicResult(
                success=False,
                error="内容为空或太短"
            )

        if topics is None:
            topics = WRITING_TOPICS

        prompt = self._build_prompt(content, requirements, topics)
        try:
            start_time = time.time()
            response = sync_generation_call(
                api_key=self.api_key,
                model=self.model,
                prompt=prompt,
                result_format='message',
                operation="writing_topic_classifier.classify_sync",
            )
            elapsed = time.time() - start_time
            result_text = response.output.choices[0].message.content
            result = self._parse_response(result_text)
            if result.success:
                logger.info(
                    f"话题分类成功: {result.primary_topic} "
                    f"(confidence: {result.confidence:.2f}, 耗时: {elapsed:.2f}s)"
                )
                return result
            heuristic_result = self._heuristic_classify(content, requirements)
            if heuristic_result.success:
                logger.info(f"同步话题分类回退到启发式: {heuristic_result.primary_topic}")
                return heuristic_result
            logger.error(f"话题分类最终失败: {result.error}")
            return WritingTopicResult(success=False, error=result.error)
        except Exception as e:
            heuristic_result = self._heuristic_classify(content, requirements)
            if heuristic_result.success:
                logger.info(f"同步话题分类异常后回退到启发式: {heuristic_result.primary_topic}")
                return heuristic_result
            logger.error(f"话题分类最终失败: {e}")
            return WritingTopicResult(
                success=False,
                error=str(e)
            )
