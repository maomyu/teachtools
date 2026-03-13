"""
AI主题分类服务

使用通义千问qwen-plus模型对阅读文章进行主题分类
使用统一话题池，只输出一个 primary_topic
"""
import json
from typing import List, Optional
from dataclasses import dataclass
import httpx

from app.config import settings


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

    def _get_topics_for_grade(self, grade: str) -> List[str]:
        """获取话题列表（使用统一话题池，不区分年级）"""
        return UNIFIED_TOPICS

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
        print(f"置信度: {result.confidence}")
        print(f"关键词: {result.keywords}")
        print(f"理由: {result.reasoning}")
    else:
        print(f"分类失败: {result.error}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_classifier())
