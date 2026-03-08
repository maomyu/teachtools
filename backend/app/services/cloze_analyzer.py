"""
完形填空考点分析服务

[INPUT]: 依赖 httpx、app.config 的 DASHSCOPE_API_KEY
[OUTPUT]: 对外提供 ClozeAnalyzer 类，分析四类考点
[POS]: backend/app/services 的考点分析服务
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import json
import httpx
from typing import Dict, Optional, List
from dataclasses import dataclass

from app.config import settings


@dataclass
class PointAnalysisResult:
    """考点分析结果"""
    success: bool
    point_type: Optional[str] = None  # 词汇/固定搭配/词义辨析/熟词僻义
    correct_word: Optional[str] = None
    translation: Optional[str] = None
    explanation: Optional[str] = None
    confusion_words: Optional[List[Dict]] = None
    tips: Optional[str] = None
    error: Optional[str] = None


class ClozeAnalyzer:
    """完形填空考点分析器 - 四类考点识别"""

    API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    ANALYZE_PROMPT = """你是中考英语完形填空教学专家。
请分析以下空格的考点类型和详细解析。

## 空格信息
- 编号: 第{blank_number}空
- 正确答案: {correct_word}
- 四个选项:
  A. {option_a}
  B. {option_b}
  C. {option_c}
  D. {option_d}

## 原文语境（含空格）
{context}

## 考点类型判断标准

1. **固定搭配**
   - 识别特征: 正确答案是短语动词或介词搭配
   - 例如: look up, depend on, take off, be interested in

2. **词义辨析**
   - 识别特征: 四个选项含义相近，需根据语境和搭配区分
   - 例如: say/tell/speak/talk, achieve/succeed/manage/accomplish

3. **熟词僻义**
   - 识别特征: 正确答案是常见词的非常规含义
   - 例如: book(书→预订), bank(银行→河岸), fine(好的→罚款)

4. **词汇**
   - 识别特征: 基础词汇考查，主要依靠语境理解和词汇积累
   - 四个选项词性相同但语义明显不同

## 输出格式（严格JSON，不要添加任何其他文字）

{{
    "point_type": "固定搭配|词义辨析|熟词僻义|词汇",
    "correct_word": "{correct_word}",
    "translation": "该词在此语境下的中文翻译",
    "explanation": "解析说明（2-3句话，说明为什么选这个词）",
    "confusion_words": [
        {{
            "word": "易混淆选项词",
            "meaning": "该词的含义",
            "reason": "为什么不能选这个词"
        }}
    ],
    "tips": "记忆技巧或相关拓展（可选）"
}}
"""

    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY未配置")

    async def analyze_point(
        self,
        blank_number: int,
        correct_word: str,
        options: Dict[str, str],
        context: str
    ) -> PointAnalysisResult:
        """
        分析单个空格的考点类型

        Args:
            blank_number: 空格编号
            correct_word: 正确答案词
            options: 四个选项 {"A": "...", "B": "...", "C": "...", "D": "..."}
            context: 包含该空格的句子或上下文

        Returns:
            PointAnalysisResult: 考点分析结果
        """
        try:
            prompt = self.ANALYZE_PROMPT.format(
                blank_number=blank_number,
                correct_word=correct_word,
                option_a=options.get("A", ""),
                option_b=options.get("B", ""),
                option_c=options.get("C", ""),
                option_d=options.get("D", ""),
                context=context
            )

            messages = [
                {"role": "system", "content": "You are an expert in English cloze test analysis for Chinese middle school students."},
                {"role": "user", "content": prompt}
            ]

            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }

                payload = {
                    "model": "qwen-plus",
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 1000
                }

                response = await client.post(
                    self.API_URL,
                    headers=headers,
                    json=payload
                )

                if response.status_code != 200:
                    return PointAnalysisResult(
                        success=False,
                        error=f"API调用失败: {response.status_code}"
                    )

                result = response.json()
                content = result['choices'][0]['message']['content']

                return self._parse_response(content)

        except Exception as e:
            return PointAnalysisResult(
                success=False,
                error=str(e)
            )

    def _parse_response(self, content: str) -> PointAnalysisResult:
        """解析AI返回的JSON"""
        try:
            json_str = content

            # 提取JSON部分
            if '```json' in content:
                start = content.find('```json') + 7
                end = content.find('```', start)
                json_str = content[start:end].strip()
            elif '```' in content:
                start = content.find('```') + 3
                end = content.find('```', start)
                json_str = content[start:end].strip()

            data = json.loads(json_str)

            # 验证考点类型
            valid_types = ["词汇", "固定搭配", "词义辨析", "熟词僻义"]
            point_type = data.get("point_type", "词汇")
            if point_type not in valid_types:
                point_type = "词汇"  # 默认

            return PointAnalysisResult(
                success=True,
                point_type=point_type,
                correct_word=data.get("correct_word"),
                translation=data.get("translation"),
                explanation=data.get("explanation"),
                confusion_words=data.get("confusion_words", []),
                tips=data.get("tips")
            )

        except json.JSONDecodeError as e:
            return PointAnalysisResult(
                success=False,
                error=f"JSON解析失败: {str(e)}"
            )

    def extract_context(self, content: str, blank_number: int, window: int = 100) -> str:
        """
        从文章中提取包含指定空格的上下文

        Args:
            content: 带空格的文章
            blank_number: 空格编号
            window: 上下文窗口大小

        Returns:
            包含该空格的句子或段落
        """
        # 尝试匹配不同格式的空格标记
        import re
        patterns = [
            rf'[{blank_number}]',  # ①②③格式
            rf'\({blank_number}\)',  # (1)(2)(3)格式
            rf'\[{blank_number}\]',  # [1][2][3]格式
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                pos = match.start()
                # 提取前后文
                start = max(0, pos - window)
                end = min(len(content), pos + window)
                context = content[start:end]

                # 尝试提取完整句子
                sentences = re.split(r'[.!?]', context)
                if len(sentences) >= 2:
                    # 返回包含空格的句子
                    for i, sent in enumerate(sentences):
                        if re.search(pattern, sent):
                            return sent.strip()

                return context.strip()

        # 如果找不到空格标记，返回文章开头
        return content[:window * 2] if len(content) > window * 2 else content


# 使用示例
async def test_analyzer():
    """测试考点分析器"""
    analyzer = ClozeAnalyzer()

    result = await analyzer.analyze_point(
        blank_number=1,
        correct_word="enjoyed",
        options={
            "A": "hated",
            "B": "disliked",
            "C": "enjoyed",
            "D": "avoided"
        },
        context="I have always ___ reading books since I was a child."
    )

    if result.success:
        print(f"考点类型: {result.point_type}")
        print(f"翻译: {result.translation}")
        print(f"解析: {result.explanation}")
    else:
        print(f"分析失败: {result.error}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_analyzer())
