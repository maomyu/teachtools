"""
AI主题分类服务

使用通义千问qwen-plus模型对阅读文章进行主题分类
主题与年级强关联 - 不同年级使用不同的话题池
"""
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
import httpx

from app.config import settings


# ============================================================================
#  话题配置 - 按年级分组
# ============================================================================

TOPICS_BY_GRADE = {
    "初一": [
        "校园生活", "家庭亲情", "兴趣爱好", "节日习俗",
        "动物自然", "梦想成长", "友谊互助", "健康饮食"
    ],
    "初二": [
        "个人成长", "科技生活", "文化交流", "环境保护",
        "运动健康", "艺术创造", "旅行探索", "社会服务"
    ],
    "初三": [
        "人生哲理", "科技伦理", "跨文化理解", "全球问题",
        "职业规划", "心理健康", "社会现象", "历史文化",
        "创新思维", "人际关系", "压力应对", "责任担当"
    ]
}


# ============================================================================
#  数据类
# ============================================================================

@dataclass
class ClassifyResult:
    """主题分类结果"""
    success: bool
    primary_topic: Optional[str] = None
    secondary_topics: List[str] = None
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

    CLASSIFY_PROMPT = """你是一个北京中考英语阅读理解教学专家。请分析以下{grade}阅读文章，从给定的话题列表中选择最匹配的主题。

## 年级
{grade}

## 可选话题列表
{topics}

## 文章内容
{content}

## 分析要求
1. primary_topic 必须从可选话题中选择一个最匹配的
2. secondary_topics 最多选择2个相关话题，也必须从可选话题中选择
3. confidence 表示分类置信度，范围0-1
4. keywords 提取3-5个文章关键词
5. reasoning 简要说明选择该话题的理由（1-2句话）

## 输出格式
请严格按照以下JSON格式输出，不要添加任何其他文字：

```json
{{
    "primary_topic": "主要话题",
    "secondary_topics": ["次要话题1", "次要话题2"],
    "confidence": 0.95,
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "reasoning": "选择该话题的理由..."
}}
```"""

    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY
        if not self.api_key:
            raise ValueError("请配置DASHSCOPE_API_KEY")

    def _get_topics_for_grade(self, grade: str) -> List[str]:
        """获取指定年级的话题列表"""
        # 标准化年级格式
        normalized_grade = grade
        if "一" in grade:
            normalized_grade = "初一"
        elif "二" in grade:
            normalized_grade = "初二"
        elif "三" in grade:
            normalized_grade = "初三"

        return TOPICS_BY_GRADE.get(normalized_grade, TOPICS_BY_GRADE["初二"])

    async def classify(
        self,
        content: str,
        grade: str = "初二"
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

            # 调用qwen-plus API
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }

                payload = {
                    "model": "qwen-plus",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant specialized in English reading comprehension for Beijing middle school students."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                }

                response = await client.post(
                    self.API_URL,
                    headers=headers,
                    json=payload
                )

                if response.status_code != 200:
                    return ClassifyResult(
                        success=False,
                        error=f"API调用失败: {response.status_code} - {response.text}"
                    )

                result = response.json()
                content_str = result['choices'][0]['message']['content']

                # 解析JSON响应
                return self._parse_response(content_str, topics)

        except Exception as e:
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
            primary_topic = data.get("primary_topic", "")
            if primary_topic not in valid_topics:
                # 尝试模糊匹配
                for topic in valid_topics:
                    if topic in primary_topic or primary_topic in topic:
                        primary_topic = topic
                        break

            # 验证secondary_topics
            secondary_topics = data.get("secondary_topics", [])
            if isinstance(secondary_topics, list):
                valid_secondary = []
                for t in secondary_topics[:2]:  # 最多2个
                    if t in valid_topics:
                        valid_secondary.append(t)
                secondary_topics = valid_secondary
            else:
                secondary_topics = []

            return ClassifyResult(
                success=True,
                primary_topic=primary_topic,
                secondary_topics=secondary_topics,
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
    grade: str = "初二"
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
        print(f"次话题: {result.secondary_topics}")
        print(f"置信度: {result.confidence}")
        print(f"关键词: {result.keywords}")
        print(f"理由: {result.reasoning}")
    else:
        print(f"分类失败: {result.error}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_classifier())
