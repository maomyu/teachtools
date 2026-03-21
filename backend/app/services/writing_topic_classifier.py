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

import dashscope
from dashscope import Generation

from app.config import settings


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

        dashscope.api_key = self.api_key
        self.model = "qwen-turbo"

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
        # 边界检查：内容为空或太短
        if not content or len(content.strip()) < 50:
            logger.warning(f"内容为空或太短（{len(content.strip() if content else 0)} 字符），跳过话题分类")
            return WritingTopicResult(
                success=False,
                error="内容为空或太短"
            )

        if topics is None:
            topics = WRITING_TOPICS

        prompt = self._build_prompt(content, requirements, topics)

        # 带重试的 AI 调用
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                start_time = time.time()

                response = Generation.call(
                    model=self.model,
                    prompt=prompt,
                    result_format='message'
                )

                elapsed = time.time() - start_time

                if response.status_code == 200:
                    result_text = response.output.choices[0].message.content
                    result = self._parse_response(result_text)

                    if result.success:
                        logger.info(
                            f"话题分类成功: {result.primary_topic} "
                            f"(confidence: {result.confidence:.2f}, 耗时: {elapsed:.2f}s)"
                        )
                        return result
                    else:
                        last_error = result.error
                else:
                    last_error = f"AI 调用失败: {response.message}"

            except Exception as e:
                last_error = str(e)
                logger.warning(f"话题分类失败 (attempt {attempt + 1}): {e}")

            # 重试前等待
            if attempt < max_retries:
                time.sleep(0.5)

        # 所有重试都失败，返回降级结果
        logger.error(f"话题分类最终失败: {last_error}")
        return WritingTopicResult(
            success=False,
            error=last_error
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
        # 边界检查：内容为空或太短
        if not content or len(content.strip()) < 50:
            logger.warning(f"内容为空或太短（{len(content.strip() if content else 0)} 字符），跳过话题分类")
            return WritingTopicResult(
                success=False,
                error="内容为空或太短"
            )

        if topics is None:
            topics = WRITING_TOPICS

        prompt = self._build_prompt(content, requirements, topics)

        # 带重试的 AI 调用
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                start_time = time.time()

                response = Generation.call(
                    model=self.model,
                    prompt=prompt,
                    result_format='message'
                )

                elapsed = time.time() - start_time

                if response.status_code == 200:
                    result_text = response.output.choices[0].message.content
                    result = self._parse_response(result_text)

                    if result.success:
                        logger.info(
                            f"话题分类成功: {result.primary_topic} "
                            f"(confidence: {result.confidence:.2f}, 耗时: {elapsed:.2f}s)"
                        )
                        return result
                    else:
                        last_error = result.error
                else:
                    last_error = f"AI 调用失败: {response.message}"

            except Exception as e:
                last_error = str(e)
                logger.warning(f"话题分类失败 (attempt {attempt + 1}): {e}")

            # 重试前等待
            if attempt < max_retries:
                time.sleep(0.5)

        # 所有重试都失败，返回降级结果
        logger.error(f"话题分类最终失败: {last_error}")
        return WritingTopicResult(
            success=False,
            error=last_error
        )
