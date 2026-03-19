"""
通义千问AI服务

提供话题分类、考点分析等AI能力
"""
import json
import re
from typing import Dict, List, Optional
import dashscope
from dashscope import Generation

from app.config import settings


# 话题列表配置
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


class QwenService:
    """通义千问服务"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.DASHSCOPE_API_KEY
        if not self.api_key:
            raise ValueError("请配置DASHSCOPE_API_KEY")

        dashscope.api_key = self.api_key
        self.model = "qwen-turbo"  # 可选: qwen-plus, qwen-max

    def classify_topic(
        self,
        content: str,
        grade: str,
        topics: Optional[List[str]] = None
    ) -> Dict:
        """
        话题分类

        Args:
            content: 文章内容
            grade: 年级
            topics: 可选话题列表（默认使用TOPICS_BY_GRADE）

        Returns:
            {
                "primary_topic": "主话题",
                "secondary_topics": ["次要话题"],
                "confidence": 0.95,
                "keywords": ["关键词"],
                "reasoning": "分类理由"
            }
        """
        if topics is None:
            topics = TOPICS_BY_GRADE.get(grade, TOPICS_BY_GRADE["初三"])

        # 截取内容（避免超出token限制）
        content_preview = content[:2000] if len(content) > 2000 else content

        prompt = f"""
你是一位北京中考英语教研专家。请分析以下{grade}阅读理解文章，给出最合适的话题分类。

文章内容：
{content_preview}

可选话题类别：
{json.dumps(topics, ensure_ascii=False, indent=2)}

请按以下JSON格式输出（仅输出JSON，不要其他内容）：
{{
    "primary_topic": "主要话题（从上面选择一个）",
    "secondary_topics": ["次要话题1", "次要话题2"],
    "confidence": 0.95,
    "keywords": ["关键词1", "关键词2"],
    "difficulty": "中等",
    "reasoning": "分类理由简述"
}}
"""

        try:
            response = Generation.call(
                model=self.model,
                prompt=prompt,
                result_format='message'
            )

            if response.status_code == 200:
                result_text = response.output.choices[0].message.content
                # 提取JSON
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    return {
                        "primary_topic": None,
                        "secondary_topics": [],
                        "confidence": 0.0,
                        "error": "无法解析AI响应"
                    }

            return {
                "primary_topic": None,
                "secondary_topics": [],
                "confidence": 0.0,
                "error": f"AI调用失败: {response.message}"
            }

        except Exception as e:
            return {
                "primary_topic": None,
                "secondary_topics": [],
                "confidence": 0.0,
                "error": str(e)
            }

    def extract_cloze_points(
        self,
        content: str,
        blanks: List[Dict]
    ) -> List[Dict]:
        """
        完形填空考点分析

        Args:
            content: 完形文章内容
            blanks: 空格信息列表 [{"number": 1, "options": {"A": "...", "B": "...", ...}, "answer": "B"}]

        Returns:
            考点分析结果列表
        """
        prompt = f"""
分析以下完形填空题目，识别每个空的考点类型。

文章：
{content}

空格及选项：
{json.dumps(blanks, ensure_ascii=False, indent=2)}

考点类型：
1. 词汇 - 基础词汇考查
2. 固定搭配 - 动词短语、介词搭配
3. 词义辨析 - 同义/近义词选择
4. 熟词僻义 - 常见词的非常规含义

请按JSON格式输出：
[
    {{
        "blank_number": 1,
        "correct_answer": "B",
        "point_type": "固定搭配",
        "point_detail": "look up 查阅",
        "explanation": "根据上下文，此处表示在字典中查阅..."
    }},
    ...
]
"""

        try:
            response = Generation.call(
                model=self.model,
                prompt=prompt,
                result_format='message'
            )

            if response.status_code == 200:
                result_text = response.output.choices[0].message.content
                json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return []

            return []

        except Exception as e:
            print(f"完形考点分析失败: {e}")
            return []

    def generate_writing_template(
        self,
        writing_type: str,
        application_type: Optional[str] = None
    ) -> Dict:
        """
        生成作文模板

        Args:
            writing_type: 文体类型（应用文/记叙文）
            application_type: 应用文子类型（书信/通知/邀请等）

        Returns:
            模板内容
        """
        prompt = f"""
请为北京中考英语作文生成一个高质量模板。

文体类型：{writing_type}
{f'应用文类型：{application_type}' if application_type else ''}

要求：
1. 符合中考英语满分作文评分标准
2. 包含常用句型和结构
3. 标注可替换部分

请按JSON格式输出：
{{
    "template_name": "模板名称",
    "template_content": "模板内容...",
    "tips": ["写作技巧1", "写作技巧2"],
    "structure": "结构说明"
}}
"""

        try:
            response = Generation.call(
                model=self.model,
                prompt=prompt,
                result_format='message'
            )

            if response.status_code == 200:
                result_text = response.output.choices[0].message.content
                json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return {}

            return {}

        except Exception as e:
            print(f"作文模板生成失败: {e}")
            return {}

    def chat(self, prompt: str) -> str:
        """
        通用对话接口 - 直接发送prompt获取回复

        Args:
            prompt: 完整的提示词

        Returns:
            AI回复的文本内容
        """
        try:
            response = Generation.call(
                model=self.model,
                prompt=prompt,
                result_format='message'
            )

            if response.status_code == 200:
                return response.output.choices[0].message.content
            return ""

        except Exception as e:
            print(f"AI chat调用失败: {e}")
            return ""
