"""
完形填空考点分析服务

[INPUT]: 依赖 httpx、app.config 的 DASHSCOPE_API_KEY
[OUTPUT]: 对外提供 ClozeAnalyzerV5 类（V5 全信号扫描 + 动态维度）
[POS]: backend/app/services 的考点分析服务
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md

考点分类系统 V5:
- 5大类(A-E) 16个考点
- 全信号扫描流程：B类→A类→D2→C类→A1兜底
- 动态维度：根据词性切换 dimensions 模板
- A5+D1融合场景：联合主考点，weight=co-primary
- 熟词僻义结构化：rare_meaning_info 独立字段
- 柯林斯词频：collins_frequency 字段

旧类型映射: 固定搭配→C2, 词义辨析→D1, 熟词僻义→D2
"""
import json
from typing import Dict, Optional, List
from dataclasses import dataclass, field

from app.config import settings
from app.services.dashscope_runtime import async_chat_completion


# ============================================================================
#  常量定义 - 新旧类型映射
# ============================================================================

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
    "XX": "待确认分类",
}


# ============================================================================
#  考点分析结果 V5 - 全信号扫描 + 动态维度
# ============================================================================

@dataclass
class PointAnalysisResultV5:
    """
    考点分析结果 V5

    核心特性：
    1. secondary_points 增加 weight 字段（auxiliary / co-primary）
    2. rejection_points 字段重命名（rejection_code / rejection_reason）
    3. word_analysis 增加 collins_frequency 字段
    4. word_analysis.dimensions 按词性动态切换
    5. rare_meaning_info 结构化熟词僻义信息
    """
    success: bool
    error: Optional[str] = None

    # === 置信度 ===
    confidence: str = "medium"  # high/medium/low
    confidence_reason: Optional[str] = None

    # === 主考点 ===
    primary_point: Optional[Dict] = None  # {code, name, explanation}

    # === 辅助考点（V5 增加 weight 字段）===
    secondary_points: List[Dict] = field(default_factory=list)
    # [{code, name, weight: "auxiliary"|"co-primary", explanation}]

    # === 排错点（V5 字段重命名）===
    rejection_points: List[Dict] = field(default_factory=list)
    # [{option_word, rejection_code, rejection_reason}]

    # === 兼容旧系统 ===
    point_type: Optional[str] = None  # 固定搭配/词义辨析/熟词僻义

    # === 通用字段 ===
    correct_word: Optional[str] = None
    translation: Optional[str] = None
    explanation: Optional[str] = None
    tips: Optional[str] = None

    # === word_analysis（V5 动态维度 + collins_frequency）===
    word_analysis: Optional[Dict] = None
    # {
    #   word: {
    #     definition: str,
    #     collins_frequency: str,  # ★新增：柯林斯词频★级
    #     dimensions: Dict  # 根据词性动态切换
    #   }
    # }
    dictionary_source: Optional[str] = None

    # === 熟词僻义（V5 结构化）===
    is_rare_meaning: bool = False
    rare_meaning_info: Optional[Dict] = None  # {common_meaning, context_meaning, textbook_source}

    # === 向后兼容字段 ===
    textbook_meaning: Optional[str] = None
    textbook_source: Optional[str] = None
    context_meaning: Optional[str] = None
    similar_words: Optional[List[Dict]] = None
    confusion_words: Optional[List[Dict]] = None  # 兼容旧系统
    phrase: Optional[str] = None
    similar_phrases: Optional[List[str]] = None


# ============================================================================
#  考点分析器 V5 - 全信号扫描 + 动态维度
# ============================================================================

class ClozeAnalyzerV5:
    """
    完形填空考点分析器 V5

    核心改进：
    1. 全信号扫描流程：B类→A类→D2→C类→A1兜底
    2. 动态维度：根据词性切换 dimensions 模板
    3. A5+D1融合场景：联合主考点，weight=co-primary
    4. 熟词僻义结构化：rare_meaning_info 独立字段
    5. 柯林斯词频：collins_frequency 字段
    """

    API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    ANALYZE_PROMPT_V5 = """你是中考英语完形填空教学专家。
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

---

## 核心执行原则

**禁止先看选项再猜答案。**
正确顺序：理解语境 → 扫描信号 → 确定考点 → 分析选项 → 输出答案

**所有考点识别必须基于"方法判断"，禁止依赖固定词表穷举。**
词表举例仅作参考，不是触发条件本身。

**若其他空格答案已知，应将其视为已知语境信息填入原文，再分析本空。**

---

## 第一步：全信号扫描（扫描所有信号，不提前停止，记录所有命中项）

### 【B类信号】逻辑连词 — 识别方法
检查空格所在句及前后句，是否存在**表达句间逻辑关系的连词或副词**：
- 表转折/对比（预期相反）→ B2：but / however / yet / although / though / instead / while / on the contrary 等
- 表因果（原因结果）→ B3：because / so / therefore / since / thus / as a result / that's why 等
- 表并列/递进（方向一致）→ B1：and / also / as well / both...and / not only...but also / besides 等
- 表让步/条件/举例/总结 → B4：even if / unless / in fact / for example / in short / such as 等

**识别标准：不靠词表，靠语义功能。** 遇到不认识的连词，判断其句间逻辑方向即可归类。

---

### 【A类信号】语篇信号 — 识别方法

**A3 代词指代 — 识别方法**
检查空格附近是否出现**人称代词、指示代词、不定代词**（he/she/it/they/this/that/these/those/one/ones/another等），且该代词的指代对象影响空格意思判断 → A3候选

**A4 情节/行为顺序 — 识别方法**
检查文章是否为叙事类，空格所在动作是否存在**时间先后或行为依赖链**（即A动作发生后才能发生B动作）→ A4候选
参考信号：first/then/later/finally/before/after/next/at last 等时序词

**A2 复现与照应 — 识别方法（含三种复现类型）**
在全文范围内（不限于本句）检查以下三种情况，任意命中即触发A2：
- **原词复现**：空格答案词与文中某处原词完全相同
- **同义/近义词复现**：文中某处词与答案词意思相近或属同一语义链
- **上位词/下位词复现**：如 textbook（下位）→ book（上位），dog（下位）→ animal（上位）
- **复指副词触发**：文中出现 again / still / also / too / either / as well 时，向前查找被复指的词或动作

**A5 情感态度 — 识别方法（含两种触发场景）**

场景①（直接定答案型）：
选项中存在**褒贬混合的情感词**，且文本语境明确指向某种情感方向 → A5主考点

场景②（辅助排除型）：
选项本身不全是情感词（如 quietly/carefully/successfully/happily），但语境中**人物情感状态明确**，需用情感背景排除不符合人物心理的选项 → A5作为辅助考点，参与排除，不直接定答案

---

### 【D2信号】熟词僻义 — 识别方法（优先于D1检查，不依赖词表）

**触发标准（两个条件同时满足）：**
1. 选项中存在**日常高频简单词**（通常为1-2音节、学生熟悉的词）
2. 将该词的**最常见义项**代入语境后，语义不通、逻辑奇怪或与上下文矛盾

→ 命中则标记D2候选，在word_analysis中展开"常见义 vs 语境义"分析

**注意：不靠词表，靠"常见义放入语境是否失效"来判断。**
例：
- stop sb → 打断某人说话（不是"停下来"）
- take back → 收回说过的话（不是"拿回来"）
- introduce...as → 把…介绍为（固定结构，非"介绍"泛义）
- find out → 查明（不是"找到"）

---

### 【C类信号】语法结构 — 识别方法

**C3 语法形式限制 — 识别方法**
检查选项之间是否**形式不同**（如doing/done/to do/原形），或句子结构是否强制要求某种语法形式：
- 动词后接特定形式的语法句型：enjoy/finish/practice/mind/spend time + doing；want/decide/agree/refuse + to do 等
- 时态语态线索：时间状语、助动词形式
- 主谓一致：主语单复数
→ C3候选

**C2 固定搭配 — 识别方法（不靠词表，靠结构特征）**
检查空格所在动词/形容词/名词后是否紧跟**介词、副词小词或固定结构框架**，且这个组合构成习惯用法：
- 动词 + 介词/副词小词（out/in/on/up/back/away/off/over等）→ 先查是否构成固定搭配，再做词义判断
- 形容词 + 介词（interested in / afraid of / proud of 等）
- 名词 + 介词（reason for / trouble with 等）
→ C2候选

**识别标准：看到"动词/形容词 + 小词"结构，优先考虑C2，不要直接跳到D1。**

**C1 词性与句子成分 — 识别方法**
检查空格所在句法位置：
- 冠词/限定词后 → 需要名词
- 系动词（be/look/feel/seem/become）后 → 需要形容词
- 情态动词后 → 需要动词原形
→ C1候选（通常作为辅助排除，不单独作主考点）

---

### 【A1兜底】上下文语义推断
以上所有信号均未命中，或命中信号不足以直接定答案，需综合空前空后语义才能判断 → A1

---

## 第二步：确定考点（全部扫描完成后统一判断）

### 主考点优先级（从高到低）
1. B类命中 → 主考点为对应B类
2. C3/C2命中 → 主考点为对应C类
3. A3 / A4 / A2 命中 → 主考点为对应A类
4. D2候选成立 → 主考点为D2
5. A5（场景①）命中 → 主考点为A5
6. 选项为近义词且无其他特征 → 主考点为D1
7. 以上均未命中 → 主考点为A1

### 辅助考点强制联动规则
- 主考点为B类 + 附近有情感词 → 必须添加A5（场景②）为辅助
- 主考点为C2/A2 + 选项为近义词 → 必须添加D1为辅助
- 任何考点 + 正确答案词符合D2识别标准 → 必须添加D2为辅助
- A5场景②（辅助排除型）→ 以实际主考点为主，A5标注为辅助

### ⚠️ A5 + D1 融合场景（情感近义词辨析）

**触发条件**：主考点为A5，且四个选项均为**同方向情感近义词**
（例：全部正面情感词 / 全部负面情感词）

**执行规则**：
- A5与D1视为**联合主考点**，权重相同，不分主辅
- secondary_points中D1标注 weight: co-primary
- word_analysis必须使用「情感类形容词专用dimensions」
- explanation必须同时覆盖：
  ① 为什么填这个情感方向（A5的工作）
  ② 为什么是这个词而不是同方向其他词（D1的工作）
- 置信度标注medium时，confidence_reason注明「A5与D1边界融合，以词义细分为最终定答依据」

**判断是否为同方向**：
- 四个选项全部正面 / 全部负面 → 同方向，触发融合
- 褒贬混合 → A5可单独定答案，D1作普通辅助

### 互斥规则
- A类内部只能一个主考点（A1/A2/A3/A4/A5选一）
- B类内部只能一个主考点（B1/B2/B3/B4选一）

### C2 固定搭配 dimensions 规则
- 主考点为C2时，word_analysis **必须使用「C2 固定搭配专用 dimensions」**
- 每个选项词的 dimensions 必须包含「固定搭配」「搭配含义」「使用场景」「与其他选项核心差异」
- 即使选项词也可以构成其他固定搭配，也要填写该词在本题语境中的搭配

---

## 第三步：word_analysis（所有考点必填，dimensions按词性动态切换）

### 情感类形容词专用 dimensions
```
"情感强度":         "weak / moderate / strong（标注强度排序，如 content < pleased < delighted）",
"触发条件":         "需要外部事件触发 / 内心平静的持续状态 / 突发惊喜感",
"典型搭配":         "be pleased with / feel content / be delighted to do...",
"与其他选项核心差异": "一句话说清楚与同组其他三词的本质区别"
```

### 普通形容词专用 dimensions
```
"描述对象":         "人 / 物 / 抽象概念",
"语义色彩":         "褒义 / 贬义 / 中性",
"典型搭配":         "...",
"与其他选项核心差异": "..."
```

### 动词专用 dimensions
```
"动作性质":         "主动发出 / 被动承受 / 持续状态",
"作用对象":         "人 / 物 / 抽象概念",
"典型搭配":         "（尤其注意动词+小词结构）",
"与其他选项核心差异": "..."
```

### 名词专用 dimensions
```
"可数性":           "可数 / 不可数 / 两者均可",
"具体或抽象":       "具体 / 抽象",
"典型搭配":         "...",
"与其他选项核心差异": "..."
```

### 副词专用 dimensions
```
"修饰对象":         "动词 / 形容词 / 整句",
"情感色彩":         "褒义 / 贬义 / 中性",
"动作状态描述":     "描述动作方式 / 描述程度 / 描述结果",
"与其他选项核心差异": "..."
```

### 逻辑连词/副词专用 dimensions（B类专用）
```
"逻辑方向":         "转折 / 因果 / 并列 / 递进",
"语气强弱":         "强调 / 中性 / 委婉",
"位置限制":         "只能句首 / 只能句中 / 两者均可",
"与其他选项核心差异": "..."
```

### C2 固定搭配专用 dimensions（主考点为 C2 时必用）
```
"固定搭配":         "该选项词构成的固定搭配短语（如 take back / look forward to）",
"搭配含义":         "该固定搭配的中文含义",
"使用场景":         "该搭配的典型使用语境",
"与其他选项核心差异": "为什么选这个搭配而不是其他选项的搭配"
```

**「与其他选项核心差异」在所有词性中必填，禁止留空。**

---

## 16种考点完整说明

### A. 语篇理解类

**A1_上下文语义推断**（兜底考点）
需综合上下文语义才能判断，无其他明确信号

**A2_复现与照应**
文中存在原词复现 / 同义近义复现 / 上下位词复现 / 复指副词（again/still/too等）

**A3_代词指代**
代词指代对象影响空格判断（he/she/it/they/this/that等）

**A4_情节/行为顺序**
叙事文中动作存在时间先后或行为依赖链

**A5_情感态度**
场景①：褒贬混合选项，情感方向直接定答案
场景②：人物情感明确，作为辅助排除工具

### B. 逻辑关系类

**B1_并列一致**：前后方向一致
**B2_转折对比**：前后语义相反或预期相反
**B3_因果关系**：前因后果 / 前果后因
**B4_其他逻辑关系**：让步 / 条件 / 举例 / 总结

### C. 句法语法类

**C1_词性与句子成分**：句法位置限制词类
**C2_固定搭配**：动词/形容词+小词的习惯词块
**C3_语法形式限制**：时态语态/非谓语/语法句型

### D. 词汇选项类

**D1_常规词义辨析**：近义词精细区分，贯穿所有考点
**D2_熟词僻义**：高频词的非常见义项，常见义在语境中失效

### E. 常识主题类

**E1_生活/场景常识**：固定场景下的常识判断
**E2_主题主旨与人物共情**：全文情感弧线/人物态度转变（末段升华句常见）
⚠️ A5与E2区别：A5判断局部情感色彩；E2依赖全文弧线，通常在末段触发

---

## 置信度规则

```
high:   有明确信号，判断唯一，无歧义
medium: 需推理，有依据，但存在其他可能；或A5+D1融合场景
low:    信号模糊，多考点竞争，建议人工复核
```

---

## 输出格式（严格JSON）

{{
    "confidence": "high / medium / low",
    "confidence_reason": "置信度依据，引用原文具体信号词或说明模糊原因",

    "primary_point": {{
        "code": "考点编码（A1~E2）",
        "name": "考点名称",
        "explanation": "为什么是这个考点，必须引用原文信号词或句"
    }},

    "secondary_points": [
        {{
            "code": "辅助考点编码",
            "name": "考点名称",
            "weight": "auxiliary（辅助）/ co-primary（A5+D1融合场景专用）",
            "explanation": "辅助考点说明及与主考点的关系"
        }}
    ],

    "rejection_points": [
        {{
            "option_word": "干扰项词",
            "rejection_code": "排错依据编码",
            "rejection_reason": "一句话说明排除原因（词义不符/搭配错误/逻辑矛盾/形式错误/情感方向错误）"
        }}
    ],

    "translation": "正确答案词的中文翻译（当前语境义，非词典泛义）",

    "explanation": "详细解析，说明完整做题思路。A5+D1融合场景必须同时覆盖情感方向判断和词义细分两部分",

    "word_analysis": {{
        "{correct_word}": {{
            "definition": "中文释义（语境义优先）",
            "collins_frequency": "柯林斯词频★级（1-5星）",
            "dimensions": {{
                // 根据词性动态切换，见上方dimensions规则
                // 必须包含「与其他选项核心差异」字段
            }}
        }},
        "干扰词A": {{
            "definition": "中文释义",
            "collins_frequency": "柯林斯词频★级",
            "dimensions": {{ ... }}
        }},
        "干扰词B": {{ ... }},
        "干扰词C": {{ ... }}
    }},

    "dictionary_source": "柯林斯词典",
    "tips": "给学生的一句话解题技巧（方法层面，不是答案层面）",

    "is_rare_meaning": false,
    "rare_meaning_info": {{
        "common_meaning": "该词最常见的中文释义",
        "context_meaning": "当前语境中的实际含义",
        "textbook_source": "课本出处（若在课本单词表中则填写，否则填null）"
    }}
}}

---

## 禁止行为

- ❌ 不得在全信号扫描完成前确定考点
- ❌ 不得用固定词表替代识别方法判断C2/D2（词表仅作参考例子）
- ❌ 不得看到"动词+小词"结构时直接跳到D1，必须先检查C2
- ❌ 不得在A5+D1融合场景中将D1降级为普通辅助或省略
- ❌ 不得在A5+D1融合场景中explanation只说情感方向不说词义细分
- ❌ 不得用同一套dimensions套用所有词性，必须动态切换（含副词专用模板）
- ❌ 不得省略任何选项的word_analysis
- ❌ 不得省略任何选项的「与其他选项核心差异」字段
- ❌ 不得输出confusion_words字段（已合并到word_analysis）
- ❌ 不得在is_rare_meaning=true时省略rare_meaning_info任何子字段
- ❌ 不得用「感觉顺」或「语感」作为explanation理由
- ❌ 不得省略任何干扰项的rejection_points，每个干扰项必须有rejection_code和rejection_reason
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
        db_session=None,
        textbook_info: Optional[Dict] = None,
    ) -> PointAnalysisResultV5:
        """
        分析单个空格的考点类型（V5版本）

        Args:
            blank_number: 空格编号
            correct_word: 正确答案词
            options: 四个选项 {"A": "...", "B": "...", "C": "...", "D": "..."}
            context: 包含该空格的句子或上下文
            db_session: 数据库会话（用于查询课本单词表）

        Returns:
            PointAnalysisResultV5: 考点分析结果
        """
        try:
            # 1. 查询课本释义
            if textbook_info is None:
                textbook_info = await self.lookup_textbook_definition(correct_word, db_session)

            if textbook_info:
                textbook_section = self.TEXTBOOK_SECTION_TEMPLATE.format(
                    word=correct_word,
                    definition=textbook_info["definition"],
                    source=textbook_info["source"]
                )
            else:
                textbook_section = ""

            # 2. 构建提示词
            prompt = self.ANALYZE_PROMPT_V5.format(
                blank_number=blank_number,
                correct_word=correct_word,
                option_a=options.get("A", ""),
                option_b=options.get("B", ""),
                option_c=options.get("C", ""),
                option_d=options.get("D", ""),
                context=context,
                textbook_section=textbook_section
            )

            # 3. 调用 API
            result = await async_chat_completion(
                api_key=self.api_key,
                model="qwen-plus",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert in English cloze test analysis for Chinese middle school students. Always respond with valid JSON. IMPORTANT: All definitions and explanations MUST be in Chinese.",
                    },
                    {"role": "user", "content": prompt},
                ],
                operation="cloze_analyzer.analyze_point",
                temperature=0.2,
                max_tokens=3000,
                timeout_seconds=120.0,
            )
            content = result['choices'][0]['message']['content']
            return self._parse_response_v5(content, correct_word)

        except Exception as e:
            return PointAnalysisResultV5(success=False, error=str(e))

    def _parse_response_v5(self, content: str, correct_word: str = "") -> PointAnalysisResultV5:
        """解析 V5 格式的 JSON 响应"""
        try:
            # 1. 提取 JSON
            json_str = self._extract_json(content)
            data = json.loads(json_str)

            # 2. 验证主考点
            primary = data.get("primary_point") or {}
            primary_code = primary.get("code", "")

            if not self._is_valid_point_code(primary_code):
                # 尝试二次推断
                primary_code = self._infer_point_code_from_context(
                    data.get("explanation", ""),
                    data.get("context", "")
                )
                if primary_code:
                    primary = {
                        "code": primary_code,
                        "name": self._get_point_name(primary_code),
                        "explanation": "AI 返回编码无效，根据解析内容二次推断"
                    }
                else:
                    primary_code = "A1"  # 兜底
                    primary = {
                        "code": "A1",
                        "name": "上下文语义推断",
                        "explanation": "无法确定具体考点，使用兜底考点"
                    }

            # 3. 处理 secondary_points（确保 weight 字段存在）
            secondary_points = []
            for sp in data.get("secondary_points", []):
                secondary_points.append({
                    "code": sp.get("code", ""),
                    "name": sp.get("name", self._get_point_name(sp.get("code", ""))),
                    "weight": sp.get("weight", "auxiliary"),  # ★默认 auxiliary
                    "explanation": sp.get("explanation", "")
                })

            # 4. 处理 rejection_points（字段重命名）
            rejection_points = []
            for rp in data.get("rejection_points", []):
                option_word = rp.get("option_word", "")
                code = rp.get("rejection_code", rp.get("code", ""))
                reason = rp.get("rejection_reason", rp.get("explanation", ""))


                # 验证日志： 当 rejection_reason 为空时记录警告
                if option_word and not reason:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"排错点 {option_word} 缺少 rejection_reason")


                rejection_points.append({
                    "option_word": option_word,
                    "rejection_code": code,
                    "rejection_reason": reason
                })

            # 5. 处理 word_analysis
            word_analysis = data.get("word_analysis")

            # 6. 构建结果
            result = PointAnalysisResultV5(
                success=True,
                confidence=data.get("confidence", "medium"),
                confidence_reason=data.get("confidence_reason"),
                primary_point={
                    "code": primary_code,
                    "name": primary.get("name") or self._get_point_name(primary_code),
                    "explanation": primary.get("explanation", "")
                },
                secondary_points=secondary_points,
                rejection_points=rejection_points,
                point_type=NEW_CODE_TO_LEGACY.get(primary_code, "词义辨析"),
                correct_word=data.get("correct_word", correct_word),
                translation=data.get("translation"),
                explanation=data.get("explanation"),
                tips=data.get("tips"),
                word_analysis=word_analysis,
                dictionary_source=data.get("dictionary_source", "柯林斯词典"),
                is_rare_meaning=data.get("is_rare_meaning", False),
                rare_meaning_info=data.get("rare_meaning_info"),
            )

            # 7. 处理熟词僻义
            self._process_rare_meaning(result, data)

            # 8. 兼容旧字段：confusion_words
            result.confusion_words = self._build_confusion_words_from_word_analysis(word_analysis, correct_word)

            return result

        except json.JSONDecodeError as e:
            return PointAnalysisResultV5(success=False, error=f"JSON解析失败: {str(e)}")

    def _extract_json(self, content: str) -> str:
        """从内容中提取 JSON"""
        json_str = content

        if '```json' in content:
            start = content.find('```json') + 7
            end = content.find('```', start)
            json_str = content[start:end].strip()
        elif '```' in content:
            start = content.find('```') + 3
            end = content.find('```', start)
            json_str = content[start:end].strip()

        return json_str

    def _is_valid_point_code(self, code: str) -> bool:
        """验证考点编码是否有效"""
        valid_codes = ["A1", "A2", "A3", "A4", "A5", "B1", "B2", "B3", "B4",
                       "C1", "C2", "C3", "D1", "D2", "E1", "E2"]
        return code in valid_codes

    def _infer_point_code_from_context(self, explanation: str, context: str) -> Optional[str]:
        """基于上下文特征的二次推断考点编码"""
        combined = f"{explanation} {context}".lower()

        # B 类逻辑关系检查（优先级最高）
        b_keywords = {
            "B2": ["but", "however", "yet", "although", "instead", "while", "contrast", "opposite", "转折", "对比"],
            "B3": ["because", "so", "therefore", "since", "as a result", "cause", "result", "因果", "导致"],
            "B1": ["and", "also", "as well", "both", "not only", "并列", "一致"],
            "B4": ["even if", "unless", "in fact", "for example", "such as", "递进", "让步", "举例"]
        }

        for code, keywords in b_keywords.items():
            if any(kw in combined for kw in keywords):
                return code

        # C 类句法语法检查
        c_keywords = {
            "C2": ["phrase", "collocation", "固定搭配", "短语", "depend on", "be interested", "look forward"],
            "C1": ["part of speech", "noun", "verb", "adjective", "词性", "句子成分"],
            "C3": ["tense", "passive", "active", "时态", "语态", "doing", "done", "to do"]
        }

        for code, keywords in c_keywords.items():
            if any(kw in combined for kw in keywords):
                return code

        # A 类语篇理解检查
        a_keywords = {
            "A3": ["he ", "she ", "it ", "they ", "this ", "that ", "代词", "指代"],
            "A5": ["happy", "sad", "angry", "excited", "surprised", "情感", "态度", "心情"],
            "A2": ["repeat", "same", "similar", "复现", "照应", "呼应"],
            "A4": ["first", "then", "later", "finally", "before", "after", "顺序", "情节"]
        }

        for code, keywords in a_keywords.items():
            if any(kw in combined for kw in keywords):
                return code

        # D 类词汇选项检查
        if any(kw in combined for kw in ["meaning", "definition", "synonym", "词义", "辨析", "区分"]):
            if any(kw in combined for kw in ["rare", "uncommon", "僻义", "课本", "熟词"]):
                return "D2"
            return "D1"

        # E 类常识主题检查
        if any(kw in combined for kw in ["common sense", "knowledge", "常识", "背景", "主题", "共情"]):
            return "E1"

        return None

    def _get_point_name(self, code: str) -> str:
        """获取考点编码对应的中文名称"""
        point_names = {
            "A1": "上下文语义推断",
            "A2": "复现与照应",
            "A3": "代词指代",
            "A4": "情节/行为顺序",
            "A5": "情感态度",
            "B1": "并列一致",
            "B2": "转折对比",
            "B3": "因果关系",
            "B4": "其他逻辑关系",
            "C1": "词性与句子成分",
            "C2": "固定搭配",
            "C3": "语法形式限制",
            "D1": "常规词义辨析",
            "D2": "熟词僻义",
            "E1": "生活/场景常识",
            "E2": "主题主旨与人物共情",
        }
        return point_names.get(code, "未知考点")

    def _process_rare_meaning(self, result: PointAnalysisResultV5, data: Dict):
        """处理熟词僻义逻辑"""
        if result.is_rare_meaning and result.rare_meaning_info:
            # 填充向后兼容字段
            result.textbook_meaning = result.rare_meaning_info.get("common_meaning")
            result.context_meaning = result.rare_meaning_info.get("context_meaning")
            result.textbook_source = result.rare_meaning_info.get("textbook_source")

            # 自动添加 D2 到辅助考点（如果不存在）
            d2_exists = any(sp.get("code") == "D2" for sp in result.secondary_points)
            if not d2_exists:
                result.secondary_points.append({
                    "code": "D2",
                    "name": "熟词僻义",
                    "weight": "auxiliary",
                    "explanation": f"课本释义'{result.textbook_meaning}'在此语境下表示'{result.context_meaning}'"
                })

    def _build_confusion_words_from_word_analysis(self, word_analysis: Optional[Dict], correct_word: str) -> List[Dict]:
        """从 word_analysis 构建 confusion_words（兼容旧系统）"""
        if not word_analysis:
            return []

        confusion_words = []
        for word, data in word_analysis.items():
            if word != correct_word and data.get("rejection_reason"):
                confusion_words.append({
                    "word": word,
                    "meaning": data.get("definition", ""),
                    "reason": data.get("rejection_reason", "")
                })

        return confusion_words

    def extract_context(self, content: str, blank_number: int, context_sentences: int = 2) -> str:
        """从文章中提取包含指定空格的完整上下文"""
        import re

        patterns = [
            rf'___{blank_number}___',
            rf'_{blank_number}_',
            rf'\({blank_number}\)',
            rf'\[{blank_number}\]',
            rf'（{blank_number}）',
            rf'[{blank_number}]',
        ]

        sentences = re.split(r'(?<=[。.!?！？])\s*', content)

        for pattern in patterns:
            for i, sentence in enumerate(sentences):
                if re.search(pattern, sentence):
                    start_idx = max(0, i - context_sentences)
                    end_idx = min(len(sentences), i + context_sentences + 1)
                    context = ' '.join(sentences[start_idx:end_idx])

                    if len(context) < 150 and (start_idx > 0 or end_idx < len(sentences)):
                        start_idx = max(0, i - context_sentences - 1)
                        end_idx = min(len(sentences), i + context_sentences + 2)
                        context = ' '.join(sentences[start_idx:end_idx])

                    return context.strip()

        return content[:300] if len(content) > 300 else content


# ============================================================================
#  测试函数
# ============================================================================

async def test_analyzer_v5():
    """测试考点分析器 V5"""
    analyzer = ClozeAnalyzerV5()

    result = await analyzer.analyze_point(
        blank_number=1,
        correct_word="delighted",
        options={
            "A": "content",
            "B": "pleased",
            "C": "delighted",
            "D": "satisfied"
        },
        context="""When Sarah heard the news that she had won the scholarship, she was absolutely ___.
        She had worked so hard for this moment, and all her efforts had finally paid off.
        Her parents were proud of her achievement, and her teachers congratulated her warmly."""
    )

    if result.success:
        print("=" * 70)
        print("V5 分析结果（全信号扫描 + 动态维度）:")
        print("=" * 70)
        print(f"置信度: {result.confidence}")
        print(f"置信度依据: {result.confidence_reason}")
        print()
        print(f"主考点: {result.primary_point['code']} - {result.primary_point['name']}")
        print(f"主考点解析: {result.primary_point['explanation']}")

        if result.secondary_points:
            print(f"\n辅助/联合考点:")
            for sp in result.secondary_points:
                weight_label = "联合主考点" if sp.get('weight') == 'co-primary' else "辅助"
                print(f"  - [{weight_label}] {sp['code']}: {sp.get('name', '')}")
                print(f"    说明: {sp.get('explanation', '')}")

        if result.rejection_points:
            print(f"\n排错点:")
            for rp in result.rejection_points:
                print(f"  - 排除 {rp['option_word']}: {rp['rejection_code']}")
                print(f"    理由: {rp['rejection_reason']}")

        print(f"\n翻译: {result.translation}")
        print(f"\n解析: {result.explanation}")

        if result.word_analysis:
            print(f"\n词义分析（动态维度）:")
            for word, data in result.word_analysis.items():
                is_correct = word == result.correct_word
                prefix = "✓" if is_correct else "✗"
                print(f"\n  {prefix} {word}:")
                print(f"    释义: {data.get('definition', '-')}")
                print(f"    词频: {data.get('collins_frequency', '-')}")
                if data.get('dimensions'):
                    print(f"    维度分析:")
                    for dim_key, dim_val in data['dimensions'].items():
                        print(f"      - {dim_key}: {dim_val}")
                if data.get('rejection_reason'):
                    print(f"    排除理由: {data['rejection_reason']}")

        print(f"\n技巧: {result.tips}")

        if result.is_rare_meaning:
            print(f"\n熟词僻义信息:")
            print(f"  常见义: {result.rare_meaning_info.get('common_meaning')}")
            print(f"  语境义: {result.rare_meaning_info.get('context_meaning')}")
            print(f"  课本出处: {result.rare_meaning_info.get('textbook_source')}")

        print("=" * 70)
    else:
        print(f"分析失败: {result.error}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_analyzer_v5())
