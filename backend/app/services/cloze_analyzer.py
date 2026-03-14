"""
完形填空考点分析服务

[INPUT]: 依赖 httpx、app.config 的 DASHSCOPE_API_KEY
[OUTPUT]: 对外提供 ClozeAnalyzer 类，分析三类考点（固定搭配、词义辨析、熟词僻义）
[POS]: backend/app/services 的考点分析服务
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import json
import httpx
from typing import Dict, Optional, List
from dataclasses import dataclass, field

from app.config import settings


@dataclass
class PointAnalysisResult:
    """考点分析结果"""
    success: bool
    point_type: Optional[str] = None  # 固定搭配/词义辨析/熟词僻义
    error: Optional[str] = None

    # 通用字段
    correct_word: Optional[str] = None
    translation: Optional[str] = None
    explanation: Optional[str] = None
    confusion_words: Optional[List[Dict]] = None
    tips: Optional[str] = None

    # 固定搭配专用
    phrase: Optional[str] = None  # 完整短语 (take a break)
    similar_phrases: Optional[List[str]] = None  # 相似短语列表

    # 词义辨析专用
    word_analysis: Optional[Dict] = None  # 三维度分析 {word: {definition, dimensions, rejection_reason}}
    dictionary_source: Optional[str] = None  # 词典来源 (柯林斯词典)

    # 熟词僻义专用
    textbook_meaning: Optional[str] = None  # 课本释义
    textbook_source: Optional[str] = None  # 课本出处 (人教版八上 Unit 5)
    context_meaning: Optional[str] = None  # 语境释义
    similar_words: Optional[List[Dict]] = None  # 相似熟词僻义列表


class ClozeAnalyzer:
    """完形填空考点分析器 - 三类考点识别（增强版）"""

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

{textbook_section}

## 三类考点判断标准

### 1. 固定搭配

**识别特征：** 正确答案与某个词形成固定搭配

**包含类型：**
- 短语动词：look up, depend on, take off, give up, work out
- 动词+名词：make a decision, take a break, have a look, take a chance
- 形容词+介词：be good at, be interested in, be proud of, be keen on
- 名词+介词：access to, key to, answer to, attention to
- 介词短语：at night, in the morning, on Sunday, by bus, in English
- 惯用表达：as soon as, as well as, neither...nor, as a matter of fact

### 2. 词义辨析

**识别特征：** 四个选项在某种维度上有相似性，需根据语境区分

**三维度分析法（核心）：**
1. **使用对象**：该词用于描述什么/谁
2. **使用场景**：在什么情况下使用
3. **正负态度**：词义隐含的褒贬色彩

**词典来源：** 使用柯林斯词典（Collins COBUILD）的英英解释作为词义辨析的标准参照

**辨析维度：**
- 同义/近义词：say/tell/speak/talk, big/large/huge, start/begin
- 词形辨析：affect/effect, except/accept, advice/advise
- 词性辨析：hard (形容词/副词), fast (形容词/副词/动词)
- 语义强度：like/love/adore, happy/content/pleased/delighted
- 语境搭配：look forward to doing, enjoy doing, finish doing

### 3. 熟词僻义

**判断标准（基于课本单词表）：**
- **熟词**：课本单词表里有这个词（人教版/外研版初一至初三）
- **僻义**：文章中的意思与课本单词表的释义不同

**僻义类型：**
- 词性转换：book (预订), water (浇水), hand (传递), warm (加热)
- 专业术语：mouse (鼠标), web (网站), surf (上网), program (编程)
- 比喻引申：cold (冷淡), hot (热门/辣), green (环保的/没经验的)
- 多义词引申：tie (平局), head (朝…方向行驶), pad (发射台)

## 判断流程

请按以下顺序判断：
1. 首先检查是否为**固定搭配**（最明显的特征）
2. 其次检查是否为**熟词僻义**（课本有该词，但当前意思与课本不同）
3. 最后判断为**词义辨析**（最常见的情况）

## 输出格式（严格JSON，按考点类型区分格式）

### 如果是固定搭配：
{{
    "point_type": "固定搭配",
    "correct_word": "{correct_word}",
    "phrase": "完整短语",
    "translation": "短语翻译",
    "explanation": "解析说明",
    "confusion_words": [
        {{
            "word": "易混淆选项词",
            "meaning": "该词的含义",
            "reason": "为什么不能选这个词"
        }}
    ],
    "similar_phrases": ["相似短语1", "相似短语2"],
    "tips": "记忆技巧或相关拓展"
}}

### 如果是词义辨析（必须包含三维度分析）：
{{
    "point_type": "词义辨析",
    "correct_word": "{correct_word}",
    "translation": "该词的中文翻译",
    "dictionary_source": "柯林斯词典",
    "word_analysis": {{
        "正确词": {{
            "definition": "英英解释（柯林斯词典风格）",
            "dimensions": {{
                "使用对象": "描述该词的使用对象",
                "使用场景": "描述该词的使用场景",
                "正负态度": "中性词/褒义词/贬义词"
            }}
        }},
        "干扰词1": {{
            "definition": "英英解释",
            "dimensions": {{
                "使用对象": "...",
                "使用场景": "...",
                "正负态度": "..."
            }},
            "rejection_reason": "排除理由"
        }},
        "干扰词2": {{
            "definition": "...",
            "dimensions": {{...}},
            "rejection_reason": "..."
        }},
        "干扰词3": {{
            "definition": "...",
            "dimensions": {{...}},
            "rejection_reason": "..."
        }}
    }},
    "confusion_words": [
        {{
            "word": "干扰词",
            "meaning": "该词含义",
            "reason": "排除理由"
        }}
    ],
    "tips": "记忆技巧"
}}

### 如果是熟词僻义（必须包含课本参照）：
{{
    "point_type": "熟词僻义",
    "correct_word": "{correct_word}",
    "textbook_meaning": "课本中的常见释义",
    "textbook_source": "课本出处（如：人教版八年级上册 Unit 5）",
    "context_meaning": "当前语境下的释义",
    "explanation": "解析说明（课本释义与语境释义的差异）",
    "similar_words": [
        {{
            "word": "其他熟词僻义示例词",
            "textbook": "课本释义",
            "rare": "僻义"
        }}
    ],
    "tips": "记忆技巧或常见语境提示"
}}
"""

    TEXTBOOK_SECTION_TEMPLATE = """## 课本释义参照（仅用于熟词僻义判断）
单词 "{word}" 在课本中存在：
- 释义：{definition}
- 出处：{source}

如果当前语境含义与上述课本释义**不同**，则判定为熟词僻义。"""

    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY未配置")

    async def lookup_textbook_definition(self, word: str, db_session=None) -> Optional[Dict]:
        """
        查询课本单词表，返回释义和出处

        Args:
            word: 要查询的单词
            db_session: 数据库会话（可选）

        Returns:
            如果找到，返回 {definition, source}；否则返回 None
        """
        if not db_session:
            return None

        try:
            from app.models.textbook_vocab import TextbookVocab
            from sqlalchemy import select

            # 查询课本单词表
            result = await db_session.execute(
                select(TextbookVocab).where(TextbookVocab.word == word.lower()).limit(1)
            )
            entry = result.scalar_one_or_none()

            if entry:
                return {
                    "definition": entry.definition,
                    "source": entry.source_display
                }
        except Exception as e:
            # 查询失败不影响主流程
            pass

        return None

    async def analyze_point(
        self,
        blank_number: int,
        correct_word: str,
        options: Dict[str, str],
        context: str,
        db_session=None
    ) -> PointAnalysisResult:
        """
        分析单个空格的考点类型

        Args:
            blank_number: 空格编号
            correct_word: 正确答案词
            options: 四个选项 {"A": "...", "B": "...", "C": "...", "D": "..."}
            context: 包含该空格的句子或上下文
            db_session: 数据库会话（用于查询课本单词表）

        Returns:
            PointAnalysisResult: 考点分析结果
        """
        try:
            # 查询课本释义（用于熟词僻义判断）
            textbook_info = await self.lookup_textbook_definition(correct_word, db_session)

            # 构建课本参照部分
            if textbook_info:
                textbook_section = self.TEXTBOOK_SECTION_TEMPLATE.format(
                    word=correct_word,
                    definition=textbook_info["definition"],
                    source=textbook_info["source"]
                )
            else:
                textbook_section = ""

            prompt = self.ANALYZE_PROMPT.format(
                blank_number=blank_number,
                correct_word=correct_word,
                option_a=options.get("A", ""),
                option_b=options.get("B", ""),
                option_c=options.get("C", ""),
                option_d=options.get("D", ""),
                context=context,
                textbook_section=textbook_section
            )

            messages = [
                {"role": "system", "content": "You are an expert in English cloze test analysis for Chinese middle school students. Always respond with valid JSON."},
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
                    "max_tokens": 2000  # 增加以支持更详细的分析
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

                return self._parse_response(content, correct_word)

        except Exception as e:
            return PointAnalysisResult(
                success=False,
                error=str(e)
            )

    def _parse_response(self, content: str, correct_word: str = "") -> PointAnalysisResult:
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
            valid_types = ["固定搭配", "词义辨析", "熟词僻义"]
            point_type = data.get("point_type")
            if not point_type or point_type not in valid_types:
                return PointAnalysisResult(
                    success=False,
                    error=f"无效的考点类型: {point_type}，必须是: {valid_types}"
                )

            # 通用字段
            result = PointAnalysisResult(
                success=True,
                point_type=point_type,
                correct_word=data.get("correct_word", correct_word),
                translation=data.get("translation"),
                explanation=data.get("explanation"),
                confusion_words=data.get("confusion_words", []),
                tips=data.get("tips")
            )

            # 根据考点类型填充专用字段
            if point_type == "固定搭配":
                result.phrase = data.get("phrase")
                result.similar_phrases = data.get("similar_phrases", [])

            elif point_type == "词义辨析":
                result.word_analysis = data.get("word_analysis")
                result.dictionary_source = data.get("dictionary_source", "柯林斯词典")

            elif point_type == "熟词僻义":
                result.textbook_meaning = data.get("textbook_meaning")
                result.textbook_source = data.get("textbook_source")
                result.context_meaning = data.get("context_meaning")
                result.similar_words = data.get("similar_words", [])

            return result

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
        import re

        # 尝试匹配不同格式的空格标记
        patterns = [
            rf'___{blank_number}___',  # ___11___格式 (最常见)
            rf'[{blank_number}]',       # ①②③格式
            rf'\({blank_number}\)',     # (1)(2)(3)格式
            rf'\[{blank_number}\]',     # [1][2][3]格式
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
        correct_word="tell",
        options={
            "A": "say",
            "B": "tell",
            "C": "speak",
            "D": "talk"
        },
        context="Please ___ me the truth about what happened yesterday."
    )

    if result.success:
        print(f"考点类型: {result.point_type}")
        print(f"翻译: {result.translation}")
        print(f"解析: {result.explanation}")
        if result.word_analysis:
            print(f"三维度分析: {json.dumps(result.word_analysis, ensure_ascii=False, indent=2)}")
    else:
        print(f"分析失败: {result.error}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_analyzer())
