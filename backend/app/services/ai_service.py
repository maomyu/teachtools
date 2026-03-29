"""
通义千问AI服务

提供话题分类、考点分析等AI能力
"""
import json
import re
from typing import Dict, List, Optional

from app.config import settings
from app.services.dashscope_runtime import async_chat_completion, sync_generation_call


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

        self.model = "qwen-turbo"  # 可选: qwen-plus, qwen-max

    def _call_generation_text(self, prompt: str, operation: str) -> str:
        response = sync_generation_call(
            api_key=self.api_key,
            model=self.model,
            prompt=prompt,
            result_format='message',
            operation=operation,
        )
        return response.output.choices[0].message.content

    async def chat_async(
        self,
        prompt: str,
        *,
        system_prompt: str = "You are a helpful assistant.",
        temperature: float | None = None,
        max_tokens: int | None = None,
        operation: str = "qwen_service.chat_async",
    ) -> str:
        result = await async_chat_completion(
            api_key=self.api_key,
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            operation=operation,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout_seconds=120.0,
        )
        return result["choices"][0]["message"]["content"]

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
            result_text = self._call_generation_text(
                prompt,
                "qwen_service.classify_topic",
            )
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
            result_text = self._call_generation_text(
                prompt,
                "qwen_service.extract_cloze_points",
            )
            json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return []

        except Exception as e:
            print(f"完形考点分析失败: {e}")
            return []

    def _build_writing_template_prompt(
        self,
        category_name: str,
        category_path: str,
        prompt_hint: Optional[str] = None,
        target_word_count: int = 150,
        group_name: Optional[str] = None,
        major_category_name: Optional[str] = None,
        task_examples: Optional[list[dict[str, str]]] = None,
        existing_template: Optional[str] = None,
    ) -> str:
        prompt_hint_text = prompt_hint or "无"
        example_blocks = []
        for index, item in enumerate(task_examples or [], start=1):
            example_blocks.append(
                "\n".join(
                    [
                        f"### 同类题目 {index}",
                        f"- 来源：{item.get('source') or '未知'}",
                        f"- 题目：{item.get('task_content') or '无'}",
                        f"- 要求：{item.get('requirements') or '无'}",
                        f"- 字数：{item.get('word_limit') or '未注明'}",
                    ]
                )
            )
        examples_text = "\n\n".join(example_blocks) if example_blocks else "暂无同类题目样本，仅基于分类树和当前题目生成。"
        existing_template_text = existing_template.strip() if existing_template else "无"

        letter_like = any(keyword in category_path for keyword in ("信", "邮件", "回信"))
        speech_like = any(keyword in category_path for keyword in ("演讲稿", "发言稿", "倡议书", "通知"))
        if letter_like:
            format_rule = "这是书信/邮件子类，模板正文必须保留称呼、正文、结尾、署名等完整格式。"
        elif speech_like:
            format_rule = "这是通知/演讲/倡议类子类，模板要用演讲稿或通知格式，不要写成私人书信。"
        else:
            format_rule = "这不是书信/邮件子类，模板正文绝对不要出现 Dear、Best wishes、Yours 等书信格式。"
        return f"""你是北京中考英语写作教学专家。请根据数据库给定的作文子类，生成一套适合学生背诵迁移的通用模板。

## 分类信息
- 文体组：{group_name or "未分类"}
- 主类：{major_category_name or "未分类"}
- 子类：{category_name}
- 分类路径：{category_path}
- 教学提示：{prompt_hint_text}
- 目标范文字数：约 {target_word_count} 词

## 真实题目样本
{examples_text}

## 已有模板（如果存在，请在其基础上纠偏优化）
{existing_template_text}

## 设计要求
1. 模板必须服务于“同一子类多题通用”，不能写成只适合某一道题的死模板。
2. 模板要贴合北京中考英语写作，语言自然、可迁移、可背诵。
3. 必须体现该子类最常见的结构、功能句和收尾方式。
4. {format_rule}
5. 如果是记叙或表达类，要突出段落组织、叙事顺序或观点展开方式。
6. 高频表达要偏中考高频、学生可直接替换套用，避免虚浮大词。
7. 输出结构要能直接用于教师讲义。
8. template_content 必须是“通用模板”，要大量使用占位符，如 [event] / [reason] / [activity] / [feeling]，不要直接抄成某一道题的完整范文。
9. structure 请写成清晰的分段说明文本，每段一行，包含段落功能和建议词数，不要输出 Python dict 字面量。

## 输出格式（JSON）

```json
{{
    "template_name": "该子类通用模板名称",
    "template_content": "可直接套用的英文模板正文，使用占位符",
    "structure": "分段说明，每段功能和建议词数",
    "tips": "3-5条适合该子类的写作提醒",
    "opening_sentences": ["2-4个适合该子类的开头句"],
    "closing_sentences": ["2-4个适合该子类的结尾句"],
    "transition_words": ["First of all,", "Besides,", "What's more,", "In conclusion,"],
    "advanced_vocabulary": [{{"word": "表达词", "basic": "基础词", "usage": "使用场景"}}],
    "grammar_points": ["2-4条适合该子类的语法提醒"],
    "scoring_criteria": {{"content": "内容建议", "language": "语言建议", "structure": "结构建议"}}
}}
```

请直接输出 JSON，不要有其他解释。"""

    def _parse_template_result(self, result_text: str) -> Dict:
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if not json_match:
            return {}
        result = json.loads(json_match.group())
        for key in ['opening_sentences', 'closing_sentences', 'transition_words',
                    'advanced_vocabulary', 'grammar_points', 'scoring_criteria']:
            if key in result and isinstance(result[key], (list, dict)):
                result[key] = json.dumps(result[key], ensure_ascii=False)
        return result

    def generate_writing_template(
        self,
        category_name: str,
        category_path: str,
        prompt_hint: Optional[str] = None,
        target_word_count: int = 150,
        group_name: Optional[str] = None,
        major_category_name: Optional[str] = None,
        task_examples: Optional[list[dict[str, str]]] = None,
        existing_template: Optional[str] = None,
    ) -> Dict:
        """
        生成作文模板（方法论驱动版 v3）

        Args:
            category_name: 叶子子类名
            category_path: 分类完整路径
            prompt_hint: 分类提示
            target_word_count: 目标词数

        Returns:
            模板内容（包含句型库、词汇表等）
        """
        prompt = self._build_writing_template_prompt(
            category_name,
            category_path,
            prompt_hint,
            target_word_count,
            group_name=group_name,
            major_category_name=major_category_name,
            task_examples=task_examples,
            existing_template=existing_template,
        )

        try:
            result_text = self._call_generation_text(
                prompt,
                "qwen_service.generate_writing_template",
            )
            return self._parse_template_result(result_text)

        except Exception as e:
            print(f"作文模板生成失败: {e}")
            return {}

    async def generate_writing_template_async(
        self,
        category_name: str,
        category_path: str,
        prompt_hint: Optional[str] = None,
        target_word_count: int = 150,
        group_name: Optional[str] = None,
        major_category_name: Optional[str] = None,
        task_examples: Optional[list[dict[str, str]]] = None,
        existing_template: Optional[str] = None,
    ) -> Dict:
        prompt = self._build_writing_template_prompt(
            category_name,
            category_path,
            prompt_hint,
            target_word_count,
            group_name=group_name,
            major_category_name=major_category_name,
            task_examples=task_examples,
            existing_template=existing_template,
        )
        try:
            result_text = await self.chat_async(
                prompt,
                system_prompt="你是北京中考英语写作教学专家。",
                operation="qwen_service.generate_writing_template_async",
            )
            return self._parse_template_result(result_text)
        except Exception as e:
            print(f"作文模板生成失败: {e}")
            return {}

    def _build_answer_explanation_prompt(
        self,
        question_text: str,
        options: Dict[str, str],
        correct_answer: str,
        passage_content: str = "",
        existing_explanation: str = "",
    ) -> str:
        # 格式化选项
        options_text = "\n".join([
            f"{key}. {value}"
            for key, value in options.items()
            if value  # 过滤空选项
        ])
        has_text_options = bool(options_text.strip())
        if not has_text_options:
            options_text = "该题选项为图片或未提取到文字内容，无法直接展示选项文本。"

        # 截取文章内容（避免过长）
        passage_preview = ""
        if passage_content:
            passage_preview = f"\n文章内容（节选）：\n{passage_content[:1500]}...\n" if len(passage_content) > 1500 else f"\n文章内容：\n{passage_content}\n"

        answer_label = correct_answer if correct_answer else "开放题/未提供固定标准答案"
        explanation_preview = existing_explanation.strip() or "无"

        if not correct_answer.strip():
            return f"""你是一位经验丰富的初中英语老师。请根据以下英语阅读开放题，输出一版适合教师版使用的最终参考答案。

{passage_preview}
题目：{question_text}

原题已有答案/解析：
{explanation_preview}

要求：
1. 最终答案必须先给出英文参考答案，不能只写中文。
2. 如果原题已有英文示例答案，优先保留其核心意思并优化语言表达，不要改写成纯中文。
3. 中文只作为英文答案的翻译或补充说明，不能替代英文答案本身。
4. 输出格式固定为：
参考答案（英文）：...
参考翻译（中文）：...
5. 如有必要，可在末尾补一句“作答说明：...”，但整体保持简洁。
6. 直接输出最终内容，不要额外标题。"""
        return f"""你是一位经验丰富的初中英语老师。请根据以下阅读理解题目，输出一版更清晰、更完整、更适合教学使用的最终答案说明。

{passage_preview}
题目：{question_text}

选项：
{options_text}

正确答案：{answer_label}

原题已有答案/解析：
{explanation_preview}

要求：
1. AI必须参与优化和补全，不要直接照抄原题已有内容。
2. 如果原题已有答案或解析，保留其核心结论，不要与原题冲突，并补充更清晰的依据、逻辑或表达。
3. 如果原题只有答案没有解析，请补出简洁解析。
4. 如果这是一道开放题，请输出“参考答案：...”并补一句简短理由。
5. 如果这是一道图片选项题，请基于题干、文章结构、上下文和正确答案标签输出“参考解析”，不要假装看到了图片细节。
6. 输出 60-140 字中文，直接输出最终内容，不要标题。"""

    def generate_answer_explanation(
        self,
        question_text: str,
        options: Dict[str, str],
        correct_answer: str,
        passage_content: str = "",
        existing_explanation: str = "",
    ) -> str:
        prompt = self._build_answer_explanation_prompt(
            question_text=question_text,
            options=options,
            correct_answer=correct_answer,
            passage_content=passage_content,
            existing_explanation=existing_explanation,
        )
        try:
            return self._call_generation_text(
                prompt,
                "qwen_service.generate_answer_explanation",
            ).strip()
        except Exception as e:
            print(f"答案解析生成失败: {e}")
            return ""

    async def generate_answer_explanation_async(
        self,
        question_text: str,
        options: Dict[str, str],
        correct_answer: str,
        passage_content: str = "",
        existing_explanation: str = "",
    ) -> str:
        prompt = self._build_answer_explanation_prompt(
            question_text=question_text,
            options=options,
            correct_answer=correct_answer,
            passage_content=passage_content,
            existing_explanation=existing_explanation,
        )
        try:
            return (
                await self.chat_async(
                    prompt,
                    system_prompt="你是一位经验丰富的初中英语老师。",
                    operation="qwen_service.generate_answer_explanation_async",
                )
            ).strip()
        except Exception as e:
            print(f"答案解析生成失败: {e}")
            return ""

    def chat(self, prompt: str) -> str:
        """
        通用对话接口 - 直接发送prompt获取回复

        Args:
            prompt: 完整的提示词

        Returns:
            AI回复的文本内容
        """
        try:
            return self._call_generation_text(
                prompt,
                "qwen_service.chat",
            )
        except Exception as e:
            print(f"AI chat调用失败: {e}")
            return ""
