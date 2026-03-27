"""
AI主题分类服务

使用通义千问qwen-plus模型对阅读文章进行主题分类
使用统一话题池，只输出一个 primary_topic
"""
import json
import re
from typing import List, Optional
from dataclasses import dataclass

from app.config import settings
from app.services.dashscope_runtime import async_chat_completion


# ============================================================================
#  统一话题池 - 不按年级区分
# ============================================================================

UNIFIED_TOPICS = [
    # 生活类
    "校园生活", "家庭亲情", "兴趣爱好", "节日习俗", "动物自然", "梦想成长", "助人为乐", "健康饮食",
    # 成长类
    "个人成长", "科技生活", "文化交流", "环境保护", "运动健康", "艺术创造", "社会现象", "友谊合作",
    # 深度类
    "人生哲理", "科技伦理", "跨文化理解", "全球问题", "职业规划", "心理健康", "社会责任", "传统文化",
    # 拓展类
    "创新思维", "教育发展", "志愿服务", "邻里关系", "诚实守信", "勇气挑战", "感恩回馈", "时间管理",
    # 细分类
    "安全意识", "阅读习惯", "师生关系", "环境保护", "社区参与", "文化传承", "体育精神", "科学探索",
    "生活技能", "情绪管理"
]


# ============================================================================
#  数据类
# ============================================================================

@dataclass
class ClassifyResult:
    """主题分类结果"""
    success: bool
    primary_topic: Optional[str] = None
    confidence: float = 0.0
    reasoning: str = ""
    keywords: List[str] = None
    error: str = None


# ============================================================================
#  主题分类器
# ============================================================================

class TopicClassifier:
    """文章主题分类器"""

    API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    CLASSIFY_PROMPT = """你是北京中考英语教学专家。
请分析以下完形填空文章的话题。

## 文章内容
{content}

## 分析步骤
1. 先从话题词库中匹配关键词
2. 如果话题词有匹配到，深入分析文章主题
3. 选择最贴切的一个话题（只需一个，不需要次要话题）

## 统一话题池
{topics}

注意：如果以上话题都不匹配，可以根据文章内容补充新的细粒度话题。

## 输出格式（严格JSON）

```json
{{
    "primary_topic": "唯一话题",
    "confidence": 0.95,
    "keywords": ["关键词1", "关键词2"],
    "reasoning": "选择理由"
}}
```"""

    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY
        if not self.api_key:
            raise ValueError("请配置DASHSCOPE_API_KEY")

    def _get_topics_for_grade(self, grade: Optional[str]) -> List[str]:
        """获取话题列表（使用统一话题池，不区分年级）"""
        return UNIFIED_TOPICS

    def _heuristic_classify(self, content: str, valid_topics: List[str]) -> ClassifyResult:
        normalized = re.sub(r"\s+", " ", (content or "").lower())
        if not normalized:
            return ClassifyResult(success=False, error="内容为空")

        keyword_rules = [
            ("家庭亲情", ("dad", "father", "mother", "mom", "mum", "parents", "family", "home")),
            ("友谊合作", ("friend", "friends", "friendship", "classmate", "together", "help me", "help her")),
            ("师生关系", ("teacher", "teachers", "student", "students", "homework", "school bus", "classroom")),
            ("校园生活", ("school", "class", "yearbook", "cafeteria", "class president", "exam", "test")),
            ("运动健康", ("baseball", "basketball", "football", "tennis", "sports", "exercise")),
            ("动物自然", ("volcano", "earthquake", "lava", "mountain", "sea", "island", "forest", "animal")),
            ("科学探索", ("science", "scientist", "research", "researchers", "expert", "experts", "experiment", "left-handed")),
            ("文化交流", ("culture", "cultures", "tradition", "celebration", "symbol", "custom")),
            ("情绪管理", ("envy", "sad", "worry", "worried", "upset", "feelings", "emotion")),
            ("个人成长", ("grow", "changed", "change", "confidence", "loneliness", "attitude", "proud")),
            ("科技生活", ("technology", "internet", "computer", "robot", "online")),
            ("社会现象", ("society", "problem", "problems", "people think")),
        ]

        scored: list[tuple[int, str, list[str]]] = []
        for topic, keywords in keyword_rules:
            if topic not in valid_topics:
                continue
            matched = [keyword for keyword in keywords if keyword in normalized]
            if matched:
                scored.append((len(matched), topic, matched))

        if not scored:
            return ClassifyResult(success=False, error="启发式未命中")

        scored.sort(key=lambda item: (-item[0], item[1]))
        _, topic, matched_keywords = scored[0]
        return ClassifyResult(
            success=True,
            primary_topic=topic,
            confidence=0.7,
            keywords=matched_keywords,
            reasoning=f"根据关键词匹配推断为{topic}",
        )

    async def classify(
        self,
        content: str,
        grade: Optional[str] = "初二"
    ) -> ClassifyResult:
        """
        分类文章主题

        Args:
            content: 文章内容
            grade: 年级（初一/初二/初三）

        Returns:
            ClassifyResult: 分类结果
        """
        try:
            grade = grade or "初二"

            # 获取该年级的话题列表
            topics = self._get_topics_for_grade(grade)
            topics_str = "、".join(topics)

            # 截取内容（避免超出token限制）
            content_preview = content[:2500] if len(content) > 2500 else content

            # 构建prompt
            prompt = self.CLASSIFY_PROMPT.format(
                grade=grade,
                topics=topics_str,
                content=content_preview
            )

            result = await async_chat_completion(
                api_key=self.api_key,
                model="qwen-plus",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant specialized in English reading comprehension for Beijing middle school students.",
                    },
                    {"role": "user", "content": prompt},
                ],
                operation="topic_classifier.classify",
                temperature=0.1,
                timeout_seconds=60.0,
            )
            content_str = result['choices'][0]['message']['content']

            # 解析JSON响应
            parsed = self._parse_response(content_str, topics)
            if parsed.success:
                return parsed
            heuristic = self._heuristic_classify(content_preview, topics)
            if heuristic.success:
                return heuristic
            return parsed

        except Exception as e:
            heuristic = self._heuristic_classify(content, topics if 'topics' in locals() else self._get_topics_for_grade(grade))
            if heuristic.success:
                return heuristic
            return ClassifyResult(
                success=False,
                error=str(e)
            )

    def _parse_response(self, content: str, valid_topics: List[str]) -> ClassifyResult:
        """解析LLM返回的JSON内容"""
        try:
            # 提取JSON部分
            json_str = content

            if '```json' in content:
                start = content.find('```json') + 7
                end = content.find('```', start)
                json_str = content[start:end].strip()
            elif '```' in content:
                start = content.find('```') + 3
                end = content.find('```', start)
                json_str = content[start:end].strip()

            data = json.loads(json_str)

            # 验证primary_topic是否在有效话题列表中
            primary_topic = (data.get("primary_topic", "") or "").strip()
            if primary_topic not in valid_topics:
                # 尝试模糊匹配
                for topic in valid_topics:
                    if topic in primary_topic or primary_topic in topic:
                        primary_topic = topic
                        break

            if not primary_topic:
                return ClassifyResult(
                    success=False,
                    error="未识别出有效主话题"
                )

            return ClassifyResult(
                success=True,
                primary_topic=primary_topic,
                confidence=float(data.get("confidence", 0.8)),
                keywords=data.get("keywords", []),
                reasoning=data.get("reasoning", "")
            )

        except json.JSONDecodeError as e:
            return ClassifyResult(
                success=False,
                error=f"JSON解析失败: {str(e)}"
            )


# ============================================================================
#  便捷函数
# ============================================================================

async def classify_passage_topic(
    content: str,
    grade: Optional[str] = "初二"
) -> ClassifyResult:
    """
    分类文章主题的便捷函数

    Args:
        content: 文章内容
        grade: 年级

    Returns:
        ClassifyResult: 分类结果
    """
    classifier = TopicClassifier()
    return await classifier.classify(content, grade)


# ============================================================================
#  测试
# ============================================================================

async def test_classifier():
    """测试主题分类器"""
    classifier = TopicClassifier()

    # 测试文章
    test_content = """
    Think of a small thing—a piece of chalk, for example. Are you remembering its name, its shape, or its color?
    Scientists say that memory includes different parts of the brain, such as language and the ability of sense.
    When you remember something, your brain stores the information in different parts.
    """

    result = await classifier.classify(test_content, "初二")

    if result.success:
        print(f"主话题: {result.primary_topic}")
        print(f"置信度: {result.confidence}")
        print(f"关键词: {result.keywords}")
        print(f"理由: {result.reasoning}")
    else:
        print(f"分类失败: {result.error}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_classifier())
