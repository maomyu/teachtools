"""
完形填空考点分析服务

[INPUT]: 依赖 httpx、app.config 的 DASHSCOPE_API_KEY
[OUTPUT]: 对外提供 ClozeAnalyzer 类（v1 三类考点）和 ClozeAnalyzerV2 类（v2 16种考点）
[POS]: backend/app/services 的考点分析服务
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md

考点分类系统 v2:
- 5大类(A-E) 16个考点
- 支持多标签: 主考点 + 辅助考点 + 排错点
- 优先级: P1(核心) > P2(重要) > P3(一般)

旧类型映射: 固定搭配→C2, 词义辨析→D1, 熟词僻义→D2
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


# ============================================================================
#  考点分析器 V2 - 16种考点 + 多标签
# ============================================================================

@dataclass
class PointAnalysisResultV2:
    """考点分析结果 V2 - 支持多标签"""
    success: bool
    error: Optional[str] = None

    # === 新考点系统 ===
    primary_point: Optional[Dict] = None  # {"code": "A1", "name": "...", "explanation": "..."}
    secondary_points: List[Dict] = field(default_factory=list)  # [{"code": "A5", "explanation": "..."}]
    rejection_points: List[Dict] = field(default_factory=list)  # [{"option_word": "...", "code": "A5", "explanation": "..."}]

    # === 兼容旧系统 ===
    point_type: Optional[str] = None  # 固定搭配/词义辨析/熟词僻义（映射后的值）

    # === 通用字段 ===
    correct_word: Optional[str] = None
    translation: Optional[str] = None
    explanation: Optional[str] = None
    confusion_words: Optional[List[Dict]] = None
    tips: Optional[str] = None

    # 固定搭配专用
    phrase: Optional[str] = None
    similar_phrases: Optional[List[str]] = None

    # 词义辨析专用
    word_analysis: Optional[Dict] = None
    dictionary_source: Optional[str] = None

    # 熟词僻义专用
    textbook_meaning: Optional[str] = None
    textbook_source: Optional[str] = None
    context_meaning: Optional[str] = None
    similar_words: Optional[List[Dict]] = None


# 旧类型到新编码的映射
LEGACY_TO_NEW_CODE = {
    "固定搭配": "C2",
    "词义辨析": "D1",
    "熟词僻义": "D2",
}

# 新编码到旧类型的映射
NEW_CODE_TO_LEGACY = {
    "C2": "固定搭配",
    "D1": "词义辨析",
    "D2": "熟词僻义",
}


class ClozeAnalyzerV2:
    """完形填空考点分析器 V2 - 16种考点识别 + 多标签支持"""

    API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    ANALYZE_PROMPT_V2 = """你是中考英语完形填空教学专家。
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

## 16种考点分类体系

### A. 语篇理解类 (P1-核心能力)

**A1_上下文语义推断**: 需要理解上下文语义才能确定答案
- 触发: 空本身单靠选项看不出来，必须靠上下文补充信息
- 信号: 空前有铺垫，空后有解释

**A2_复现与照应**: 文中其他位置出现了相同/近义词
- 触发: 文中有明显重复、同义替换、近义呼应
- 信号: 原词复现，同义词复现，主题链词汇

**A3_代词指代**: 需要理解代词指代的对象
- 触发: 空附近出现代词，代词的指向会影响意思判断
- 信号: he/she/it/they, this/that/these/those

**A4_情节/行为顺序**: 涉及故事发展或行为先后顺序
- 触发: 文章是叙事文，人物动作存在前后链条
- 信号: first/then/later/finally, before/after

**A5_情感态度**: 涉及人物情感、态度、心理变化
- 触发: 选项多为形容词、副词、情绪类动词
- 信号: happy/excited/surprised/sad/angry

### B. 逻辑关系类 (P1-核心能力)

**B1_并列一致**: 前后内容语义一致、方向一致
- 信号: and, also, as well, both...and, not only...but also

**B2_转折对比**: 前后语义相反或预期相反
- 信号: but, however, yet, although, instead, while

**B3_因果关系**: 前因后果或前果后因
- 信号: because, so, therefore, since, as a result

**B4_其他逻辑关系**: 递进、让步、条件、举例、总结等
- 信号: even if, unless, in fact, for example, in short

### C. 句法语法类 (P2-结构分析)

**C1_词性与句子成分**: 需要分析句子成分确定词性
- 信号: 冠词后→名词，系动词后→形容词，情态动词后→动词原形

**C2_固定搭配**: 动词短语、介词短语、习惯表达
- 信号: depend on, be interested in, make a decision

**C3_语法形式限制**: 时态、语态、非谓语动词形式
- 信号: 时间状语，主语单复数，be done/doing/to do

### D. 词汇选项类 (P3-词汇知识)

**D1_常规词义辨析**: 近义词辨析，需要根据语境选最合适的
- 信号: say/tell/speak/talk, look/see/watch/notice

**D2_熟词僻义**: 常见词的非常见含义
- 信号: run a company, head north, tie for first place

### E. 常识主题类 (P3-背景知识)

**E1_生活常识/场景常识**: 日常生活、文化背景知识
- 信号: 医院、学校、车站、比赛等固定场景

**E2_主题主旨与人物共情**: 理解文章主旨、人物心理
- 信号: 成长、亲情、挫折、鼓励、帮助等主题

## 判断流程（语义→逻辑→结构→词项）

1. **语义层面**: 先判断是否需要上下文语义推断（A类）
2. **逻辑层面**: 检查是否有逻辑关系词（B类）
3. **结构层面**: 分析句子结构、语法（C类）
4. **词项层面**: 最后判断词汇选项（D类）
5. **背景层面**: 是否需要常识或主题理解（E类）

## 输出格式（严格JSON）

{{
    "primary_point": {{
        "code": "考点编码 (如 A1, B2, C2, D1)",
        "name": "考点名称",
        "explanation": "为什么是这个考点"
    }},
    "secondary_points": [
        {{
            "code": "辅助考点编码",
            "explanation": "辅助考点说明"
        }}
    ],
    "rejection_points": [
        {{
            "option_word": "干扰项词",
            "code": "排错依据编码",
            "explanation": "为什么可以排除这个选项"
        }}
    ],
    "translation": "句子翻译",
    "explanation": "详细解析",
    "confusion_words": [
        {{
            "word": "易混淆词",
            "meaning": "含义",
            "reason": "排除理由"
        }}
    ],
    "tips": "解题技巧"
}}
"""

    TEXTBOOK_SECTION_TEMPLATE = """## 课本释义参照（用于熟词僻义判断 D2）
单词 "{word}" 在课本中存在：
- 释义：{definition}
- 出处：{source}

如果当前语境含义与上述课本释义**不同**，则可能判定为熟词僻义(D2)。"""

    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY未配置")

    async def lookup_textbook_definition(self, word: str, db_session=None) -> Optional[Dict]:
        """查询课本单词表，返回释义和出处"""
        if not db_session:
            return None

        try:
            from app.models.textbook_vocab import TextbookVocab
            from sqlalchemy import select

            result = await db_session.execute(
                select(TextbookVocab).where(TextbookVocab.word == word.lower()).limit(1)
            )
            entry = result.scalar_one_or_none()

            if entry:
                return {
                    "definition": entry.definition,
                    "source": entry.source_display
                }
        except Exception:
            pass

        return None

    async def analyze_point(
        self,
        blank_number: int,
        correct_word: str,
        options: Dict[str, str],
        context: str,
        db_session=None
    ) -> PointAnalysisResultV2:
        """分析单个空格的考点类型（V2版本）"""
        try:
            textbook_info = await self.lookup_textbook_definition(correct_word, db_session)

            if textbook_info:
                textbook_section = self.TEXTBOOK_SECTION_TEMPLATE.format(
                    word=correct_word,
                    definition=textbook_info["definition"],
                    source=textbook_info["source"]
                )
            else:
                textbook_section = ""

            prompt = self.ANALYZE_PROMPT_V2.format(
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

            async with httpx.AsyncClient(timeout=90.0) as client:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }

                payload = {
                    "model": "qwen-plus",
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 2500
                }

                response = await client.post(
                    self.API_URL,
                    headers=headers,
                    json=payload
                )

                if response.status_code != 200:
                    return PointAnalysisResultV2(
                        success=False,
                        error=f"API调用失败: {response.status_code}"
                    )

                result = response.json()
                content = result['choices'][0]['message']['content']

                return self._parse_response_v2(content, correct_word)

        except Exception as e:
            return PointAnalysisResultV2(
                success=False,
                error=str(e)
            )

    def _parse_response_v2(self, content: str, correct_word: str = "") -> PointAnalysisResultV2:
        """解析AI返回的JSON（V2版本）"""
        try:
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

            # 验证主考点
            primary = data.get("primary_point", {})
            primary_code = primary.get("code", "")
            valid_codes = ["A1", "A2", "A3", "A4", "A5", "B1", "B2", "B3", "B4", "C1", "C2", "C3", "D1", "D2", "E1", "E2"]

            if not primary_code or primary_code not in valid_codes:
                # 如果编码无效，默认为 D1（常规词义辨析）
                primary_code = "D1"
                primary = {"code": "D1", "name": "常规词义辨析", "explanation": "默认分类"}

            # 映射到旧类型（兼容）
            legacy_type = NEW_CODE_TO_LEGACY.get(primary_code, "词义辨析")

            result = PointAnalysisResultV2(
                success=True,
                primary_point={
                    "code": primary_code,
                    "name": primary.get("name", ""),
                    "explanation": primary.get("explanation", "")
                },
                secondary_points=data.get("secondary_points", []),
                rejection_points=data.get("rejection_points", []),
                point_type=legacy_type,
                correct_word=data.get("correct_word", correct_word),
                translation=data.get("translation"),
                explanation=data.get("explanation"),
                confusion_words=data.get("confusion_words", []),
                tips=data.get("tips")
            )

            # 根据主考点类型填充专用字段
            if primary_code == "C2":  # 固定搭配
                # 如果有固定搭配相关信息，填充
                pass
            elif primary_code == "D1":  # 词义辨析
                result.word_analysis = data.get("word_analysis")
                result.dictionary_source = data.get("dictionary_source", "柯林斯词典")
            elif primary_code == "D2":  # 熟词僻义
                result.textbook_meaning = data.get("textbook_meaning")
                result.textbook_source = data.get("textbook_source")
                result.context_meaning = data.get("context_meaning")
                result.similar_words = data.get("similar_words", [])

            return result

        except json.JSONDecodeError as e:
            return PointAnalysisResultV2(
                success=False,
                error=f"JSON解析失败: {str(e)}"
            )

    def extract_context(self, content: str, blank_number: int, window: int = 100) -> str:
        """从文章中提取包含指定空格的上下文"""
        import re

        patterns = [
            rf'___{blank_number}___',
            rf'[{blank_number}]',
            rf'\({blank_number}\)',
            rf'\[{blank_number}\]',
        ]

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                pos = match.start()
                start = max(0, pos - window)
                end = min(len(content), pos + window)
                context = content[start:end]

                sentences = re.split(r'[.!?]', context)
                if len(sentences) >= 2:
                    for i, sent in enumerate(sentences):
                        if re.search(pattern, sent):
                            return sent.strip()

                return context.strip()

        return content[:window * 2] if len(content) > window * 2 else content


# 使用示例
async def test_analyzer():
    """测试考点分析器 V1"""
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


async def test_analyzer_v2():
    """测试考点分析器 V2"""
    analyzer = ClozeAnalyzerV2()

    result = await analyzer.analyze_point(
        blank_number=1,
        correct_word="tell",
        options={
            "A": "say",
            "B": "tell",
            "C": "speak",
            "D": "talk"
        },
        context="Please ___ me the truth about what happened yesterday. I really need to know what was going on."
    )

    if result.success:
        print("=" * 60)
        print("V2 分析结果:")
        print("=" * 60)
        print(f"主考点: {result.primary_point['code']} - {result.primary_point['name']}")
        print(f"主考点解析: {result.primary_point['explanation']}")

        if result.secondary_points:
            print(f"\n辅助考点:")
            for sp in result.secondary_points:
                print(f"  - {sp['code']}: {sp.get('explanation', '')}")

        if result.rejection_points:
            print(f"\n排错点:")
            for rp in result.rejection_points:
                print(f"  - 排除 {rp['option_word']}: {rp['code']} - {rp.get('explanation', '')}")

        print(f"\n翻译: {result.translation}")
        print(f"解析: {result.explanation}")

        if result.confusion_words:
            print(f"\n易混淆词:")
            for cw in result.confusion_words:
                print(f"  - {cw['word']}: {cw.get('meaning', '')} → {cw.get('reason', '')}")

        print(f"\n技巧: {result.tips}")
        print("=" * 60)
    else:
        print(f"分析失败: {result.error}")


if __name__ == "__main__":
    import asyncio
    print("测试 V1 分析器:")
    asyncio.run(test_analyzer())
    print("\n\n测试 V2 分析器:")
    asyncio.run(test_analyzer_v2())
