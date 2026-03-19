# 完形填空考点分析系统 V5 重构方案

> 版本: V5
> 日期: 2025-03-19
> 状态: 待执行

---

## 目录

1. [V5 提示词核心变化详解](#一v5-提示词核心变化详解)
2. [后端重构详细方案](#二后端重构详细方案)
3. [前端类型系统重构](#三前端类型系统重构)
4. [前端展示重构](#四前端展示重构)
   - 4.1 [完形填空详情页 (ClozeDetailContent)](#41-完形填空详情页-clozedetailcontenttsx)
   - 4.2 [考点汇总页面 (ClozePointsPage)](#42-考点汇总页面-clozepointspagetsx)
   - 4.3 [完形填空列表页 (ClozePage)](#43-完形填空列表页-clozepagetsx)
5. [讲义内容重构](#五讲义内容重构)
6. [执行计划](#六执行计划)
7. [附录：完整 V5 提示词](#附录完整-v5-提示词)

---

## 一、V5 提示词核心变化详解

### 1.1 执行流程重构

**V2 流程**：决策树 → 考点选择 → 输出

**V5 流程**：
```
第一步：全信号扫描（扫描所有信号，不提前停止）
  ├─ B类信号：逻辑连词扫描
  ├─ A类信号：语篇信号扫描（A3/A4/A2/A5）
  ├─ D2信号：熟词僻义扫描（优先于D1）
  ├─ C类信号：语法结构扫描（C3/C2/C1）
  └─ A1兜底：上下文语义推断

第二步：确定考点（全部扫描完成后统一判断）
  ├─ 主考点优先级判断
  ├─ 辅助考点强制联动
  └─ A5+D1融合场景处理

第三步：word_analysis（按词性动态切换dimensions）
  ├─ 情感类形容词专用dimensions
  ├─ 普通形容词专用dimensions
  ├─ 动词专用dimensions
  ├─ 名词专用dimensions
  ├─ 副词专用dimensions
  └─ 逻辑连词/副词专用dimensions（B类）
```

### 1.2 新增/修改的考点识别方法

#### B类信号 - 逻辑连词
```
B2 转折/对比：but / however / yet / although / though / instead / while / on the contrary
B3 因果：because / so / therefore / since / thus / as a result / that's why
B1 并列/递进：and / also / as well / both...and / not only...but also / besides
B4 让步/条件/举例/总结：even if / unless / in fact / for example / in short / such as
```

#### A类信号 - 语篇信号
```
A3 代词指代：检查空格附近是否出现人称/指示/不定代词
A4 情节/行为顺序：检查是否存在时间先后或行为依赖链
A2 复现与照应：
  - 原词复现
  - 同义/近义词复现
  - 上位词/下位词复现
  - 复指副词触发（again/still/also/too/either/as well）
A5 情感态度：
  - 场景①（直接定答案型）：褒贬混合选项
  - 场景②（辅助排除型）：情感背景排除
```

#### D2信号 - 熟词僻义（优先于D1检查）
```
触发标准（两个条件同时满足）：
1. 选项中存在日常高频简单词（通常为1-2音节）
2. 将该词的最常见义项代入语境后，语义不通

例：
- stop sb → 打断某人说话（不是"停下来"）
- take back → 收回说过的话（不是"拿回来"）
- introduce...as → 把…介绍为
- find out → 查明（不是"找到"）
```

#### C类信号 - 语法结构
```
C3 语法形式限制：检查选项之间是否形式不同（doing/done/to do/原形）
C2 固定搭配：检查动词/形容词/名词后是否紧跟介词/副词小词
C1 词性与句子成分：检查空格所在句法位置

识别标准：看到"动词/形容词 + 小词"结构，优先考虑C2，不要直接跳到D1
```

### 1.3 主考点优先级

```python
PRIORITY_ORDER = [
    1. B类命中 → 主考点为对应B类
    2. C3/C2命中 → 主考点为对应C类
    3. A3 / A4 / A2 命中 → 主考点为对应A类
    4. D2候选成立 → 主考点为D2
    5. A5（场景①）命中 → 主考点为A5
    6. 选项为近义词且无其他特征 → 主考点为D1
    7. 以上均未命中 → 主考点为A1
]
```

### 1.4 辅助考点强制联动规则

```
- 主考点为B类 + 附近有情感词 → 必须添加A5（场景②）为辅助
- 主考点为C2/A2 + 选项为近义词 → 必须添加D1为辅助
- 任何考点 + 正确答案词符合D2识别标准 → 必须添加D2为辅助
- A5场景②（辅助排除型）→ 以实际主考点为主，A5标注为辅助
```

### 1.5 A5 + D1 融合场景（新增）

**触发条件**：主考点为A5，且四个选项均为**同方向情感近义词**

**执行规则**：
- A5与D1视为**联合主考点**，权重相同
- secondary_points中D1标注 `weight: co-primary`
- word_analysis必须使用「情感类形容词专用dimensions」
- explanation必须同时覆盖：
  - 为什么填这个情感方向（A5的工作）
  - 为什么是这个词而不是同方向其他词（D1的工作）
- 置信度标注medium时，confidence_reason注明「A5与D1边界融合」

**判断是否为同方向**：
- 四个选项全部正面 / 全部负面 → 同方向，触发融合
- 褒贬混合 → A5可单独定答案，D1作普通辅助

### 1.6 word_analysis 动态 dimensions（核心变化）

#### 情感类形容词专用 dimensions
```json
{
  "情感强度": "weak / moderate / strong（标注强度排序，如 content < pleased < delighted）",
  "触发条件": "需要外部事件触发 / 内心平静的持续状态 / 突发惊喜感",
  "典型搭配": "be pleased with / feel content / be delighted to do...",
  "与其他选项核心差异": "一句话说清楚与同组其他三词的本质区别"
}
```

#### 普通形容词专用 dimensions
```json
{
  "描述对象": "人 / 物 / 抽象概念",
  "语义色彩": "褒义 / 贬义 / 中性",
  "典型搭配": "...",
  "与其他选项核心差异": "..."
}
```

#### 动词专用 dimensions
```json
{
  "动作性质": "主动发出 / 被动承受 / 持续状态",
  "作用对象": "人 / 物 / 抽象概念",
  "典型搭配": "（尤其注意动词+小词结构）",
  "与其他选项核心差异": "..."
}
```

#### 名词专用 dimensions
```json
{
  "可数性": "可数 / 不可数 / 两者均可",
  "具体或抽象": "具体 / 抽象",
  "典型搭配": "...",
  "与其他选项核心差异": "..."
}
```

#### 副词专用 dimensions
```json
{
  "修饰对象": "动词 / 形容词 / 整句",
  "情感色彩": "褒义 / 贬义 / 中性",
  "动作状态描述": "描述动作方式 / 描述程度 / 描述结果",
  "与其他选项核心差异": "..."
}
```

#### 逻辑连词/副词专用 dimensions（B类专用）
```json
{
  "逻辑方向": "转折 / 因果 / 并列 / 递进",
  "语气强弱": "强调 / 中性 / 委婉",
  "位置限制": "只能句首 / 只能句中 / 两者均可",
  "与其他选项核心差异": "..."
}
```

### 1.7 输出格式变化

#### 新增字段
```json
{
  "confidence": "high / medium / low",
  "confidence_reason": "置信度依据，引用原文具体信号词",

  "primary_point": {
    "code": "A1~E2",
    "name": "考点名称",
    "explanation": "必须引用原文信号词或句"
  },

  "secondary_points": [
    {
      "code": "辅助考点编码",
      "name": "考点名称",
      "weight": "auxiliary / co-primary",
      "explanation": "辅助考点说明及与主考点的关系"
    }
  ],

  "rejection_points": [
    {
      "option_word": "干扰项词",
      "rejection_code": "排错依据编码",
      "rejection_reason": "排除原因（词义不符/搭配错误/逻辑矛盾/形式错误/情感方向错误）"
    }
  ],

  "word_analysis": {
    "{correct_word}": {
      "definition": "中文释义（语境义优先）",
      "collins_frequency": "柯林斯词频★级（1-5星）",
      "dimensions": {}
    },
    "干扰词A": {
      "definition": "中文释义",
      "collins_frequency": "柯林斯词频★级",
      "dimensions": {},
      "rejection_reason": "排除理由（词义层面展开）"
    }
  },

  "is_rare_meaning": false,
  "rare_meaning_info": {
    "common_meaning": "该词最常见的中文释义",
    "context_meaning": "当前语境中的实际含义",
    "textbook_source": "课本出处（若在课本单词表中则填写，否则null）"
  }
}
```

#### 删除字段
```
- confusion_words（已合并到 word_analysis）
```

### 1.8 禁止行为清单

```
❌ 不得在全信号扫描完成前确定考点
❌ 不得用固定词表替代识别方法判断C2/D2
❌ 不得看到"动词+小词"结构时直接跳到D1，必须先检查C2
❌ 不得在A5+D1融合场景中将D1降级为普通辅助或省略
❌ 不得在A5+D1融合场景中explanation只说情感方向不说词义细分
❌ 不得用同一套dimensions套用所有词性，必须动态切换
❌ 不得省略任何选项的word_analysis
❌ 不得省略任何选项的「与其他选项核心差异」字段
❌ 不得输出confusion_words字段（已合并）
❌ 不得在is_rare_meaning=true时省略rare_meaning_info任何子字段
❌ 不得用「感觉顺」或「语感」作为explanation理由
```

---

## 二、后端重构详细方案

### 2.1 文件结构

```
backend/app/services/cloze_analyzer.py
├── PointAnalysisResult（V1 - 保留兼容）
├── ClozeAnalyzer（V1 - 保留兼容）
├── PointAnalysisResultV2（V2 - 保留兼容）
├── ClozeAnalyzerV2（V2 - 保留兼容）
├── PointAnalysisResultV5（V5 - 新增）★
└── ClozeAnalyzerV5（V5 - 新增）★
```

### 2.2 新增 `PointAnalysisResultV5` 数据类

```python
@dataclass
class PointAnalysisResultV5:
    """考点分析结果 V5 - 全信号扫描 + 动态维度"""
    success: bool
    error: Optional[str] = None

    # === 置信度 ===
    confidence: str = "medium"  # high/medium/low
    confidence_reason: Optional[str] = None

    # === 主考点 ===
    primary_point: Optional[Dict] = None  # {code, name, explanation}

    # === 辅助考点（增加 weight 字段）===
    secondary_points: List[Dict] = field(default_factory=list)
    # [{code, name, weight: "auxiliary"|"co-primary", explanation}]

    # === 排错点（结构化）===
    rejection_points: List[Dict] = field(default_factory=list)
    # [{option_word, rejection_code, rejection_reason}]

    # === 兼容旧系统 ===
    point_type: Optional[str] = None  # 固定搭配/词义辨析/熟词僻义

    # === 通用字段 ===
    correct_word: Optional[str] = None
    translation: Optional[str] = None
    explanation: Optional[str] = None
    tips: Optional[str] = None

    # === word_analysis（动态维度）===
    word_analysis: Optional[Dict] = None
    # {
    #   word: {
    #     definition: str,
    #     collins_frequency: str,  # ★新增
    #     dimensions: Dict,  # 根据词性动态
    #     rejection_reason: str  # 仅干扰词
    #   }
    # }
    dictionary_source: Optional[str] = None

    # === 熟词僻义（结构化）===
    is_rare_meaning: bool = False
    rare_meaning_info: Optional[Dict] = None  # {common_meaning, context_meaning, textbook_source}

    # === 向后兼容字段 ===
    textbook_meaning: Optional[str] = None
    textbook_source: Optional[str] = None
    context_meaning: Optional[str] = None
    similar_words: Optional[List[Dict]] = None
```

### 2.3 新增 `ClozeAnalyzerV5` 类

```python
class ClozeAnalyzerV5:
    """完形填空考点分析器 V5 - 全信号扫描 + 动态维度"""

    API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    # ★ 完整的 V5 提示词（见下方 2.4 节）
    ANALYZE_PROMPT_V5 = """..."""

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
        # 复用现有逻辑
        ...

    async def analyze_point(
        self,
        blank_number: int,
        correct_word: str,
        options: Dict[str, str],
        context: str,
        db_session=None
    ) -> PointAnalysisResultV5:
        """分析单个空格的考点类型（V5版本）"""
        try:
            # 1. 查询课本释义
            textbook_info = await self.lookup_textbook_definition(correct_word, db_session)
            textbook_section = self._build_textbook_section(correct_word, textbook_info)

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
            messages = [
                {"role": "system", "content": "You are an expert in English cloze test analysis for Chinese middle school students. Always respond with valid JSON. IMPORTANT: All definitions and explanations MUST be in Chinese."},
                {"role": "user", "content": prompt}
            ]

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    self.API_URL,
                    headers={
                        'Authorization': f'Bearer {self.api_key}',
                        'Content-Type': 'application/json'
                    },
                    json={
                        "model": "qwen-plus",
                        "messages": messages,
                        "temperature": 0.2,  # 降低随机性
                        "max_tokens": 3000  # 增加输出长度
                    }
                )

                if response.status_code != 200:
                    return PointAnalysisResultV5(
                        success=False,
                        error=f"API调用失败: {response.status_code}"
                    )

                result = response.json()
                content = result['choices'][0]['message']['content']
                return self._parse_response_v5(content, correct_word)

        except Exception as e:
            return PointAnalysisResultV5(success=False, error=str(e))

    def _parse_response_v5(self, content: str, correct_word: str = "") -> PointAnalysisResultV5:
        """解析 V5 格式的 JSON 响应"""
        try:
            # 1. 提取 JSON
            data = self._extract_json(content)

            # 2. 验证主考点
            primary = data.get("primary_point") or {}
            primary_code = primary.get("code", "")

            if not self._is_valid_point_code(primary_code):
                # 尝试二次推断
                primary_code = self._infer_point_code(data)
                primary = self._build_fallback_primary(primary_code)

            # 3. 构建结果
            result = PointAnalysisResultV5(
                success=True,
                confidence=data.get("confidence", "medium"),
                confidence_reason=data.get("confidence_reason"),
                primary_point={
                    "code": primary_code,
                    "name": primary.get("name") or self._get_point_name(primary_code),
                    "explanation": primary.get("explanation", "")
                },
                secondary_points=data.get("secondary_points", []),
                rejection_points=data.get("rejection_points", []),
                point_type=NEW_CODE_TO_LEGACY.get(primary_code, "词义辨析"),
                correct_word=data.get("correct_word", correct_word),
                translation=data.get("translation"),
                explanation=data.get("explanation"),
                tips=data.get("tips"),
                word_analysis=data.get("word_analysis"),
                dictionary_source=data.get("dictionary_source", "柯林斯词典"),
                is_rare_meaning=data.get("is_rare_meaning", False),
                rare_meaning_info=data.get("rare_meaning_info"),
            )

            # 4. 处理熟词僻义
            self._process_rare_meaning(result, data)

            return result

        except json.JSONDecodeError as e:
            return PointAnalysisResultV5(success=False, error=f"JSON解析失败: {str(e)}")

    def _is_valid_point_code(self, code: str) -> bool:
        """验证考点编码是否有效"""
        valid_codes = ["A1", "A2", "A3", "A4", "A5", "B1", "B2", "B3", "B4",
                       "C1", "C2", "C3", "D1", "D2", "E1", "E2"]
        return code in valid_codes

    def _process_rare_meaning(self, result: PointAnalysisResultV5, data: Dict):
        """处理熟词僻义逻辑"""
        if result.is_rare_meaning and result.rare_meaning_info:
            # 填充向后兼容字段
            result.textbook_meaning = result.rare_meaning_info.get("common_meaning")
            result.context_meaning = result.rare_meaning_info.get("context_meaning")
            result.textbook_source = result.rare_meaning_info.get("textbook_source")

            # 自动添加 D2 到辅助考点
            d2_exists = any(sp.get("code") == "D2" for sp in result.secondary_points)
            if not d2_exists:
                result.secondary_points.append({
                    "code": "D2",
                    "name": "熟词僻义",
                    "weight": "auxiliary",
                    "explanation": f"课本释义'{result.textbook_meaning}'在此语境下表示'{result.context_meaning}'"
                })
```

---

## 三、前端类型系统重构

### 3.1 更新 `SecondaryPoint` 类型

```typescript
// frontend/src/types/index.ts

/** 辅助考点 V5（增加 weight 字段）*/
export interface SecondaryPoint {
  code: string
  name?: string
  weight: 'auxiliary' | 'co-primary'  // ★新增
  explanation?: string
}
```

### 3.2 更新 `RejectionPoint` 类型

```typescript
/** 排错点 V5（字段重命名）*/
export interface RejectionPoint {
  option_word: string
  rejection_code: string      // ★改名（原 point_code）
  rejection_reason: string    // ★改名（原 explanation）
}
```

### 3.3 新增词性维度类型

```typescript
// ============================================================================
//  词性维度类型（V5 动态维度）
// ============================================================================

/** 情感类形容词维度 */
export interface EmotionAdjectiveDimensions {
  情感强度: string
  触发条件: string
  典型搭配: string
  与其他选项核心差异: string
}

/** 普通形容词维度 */
export interface CommonAdjectiveDimensions {
  描述对象: string
  语义色彩: string
  典型搭配: string
  与其他选项核心差异: string
}

/** 动词维度 */
export interface VerbDimensions {
  动作性质: string
  作用对象: string
  典型搭配: string
  与其他选项核心差异: string
}

/** 名词维度 */
export interface NounDimensions {
  可数性: string
  具体或抽象: string
  典型搭配: string
  与其他选项核心差异: string
}

/** 副词维度 */
export interface AdverbDimensions {
  修饰对象: string
  情感色彩: string
  动作状态描述: string
  与其他选项核心差异: string
}

/** 逻辑连词/副词维度（B类专用）*/
export interface ConjunctionDimensions {
  逻辑方向: string
  语气强弱: string
  位置限制: string
  与其他选项核心差异: string
}

/** 动态维度联合类型 */
export type WordDimensions =
  | EmotionAdjectiveDimensions
  | CommonAdjectiveDimensions
  | VerbDimensions
  | NounDimensions
  | AdverbDimensions
  | ConjunctionDimensions
  | Record<string, string>  // 兜底
```

### 3.4 更新 `ClozePointNew` 类型

```typescript
/** 完形考点 V5 - 全信号扫描版本 */
export interface ClozePointNew {
  id: number
  blank_number?: number
  correct_answer?: string
  correct_word?: string
  options?: QuestionOptions
  sentence?: string

  // === V5 考点系统 ===
  confidence?: 'high' | 'medium' | 'low'  // ★新增
  confidence_reason?: string               // ★新增
  primary_point?: PointType
  secondary_points: SecondaryPoint[]
  rejection_points: RejectionPoint[]

  // === 兼容旧系统 ===
  legacy_point_type?: string
  point_type?: string

  // === 解析内容 ===
  translation?: string
  explanation?: string
  tips?: string

  // === word_analysis（V5 动态维度）===
  word_analysis?: Record<string, {
    definition: string
    collins_frequency?: string  // ★新增：柯林斯词频
    dimensions: WordDimensions
    rejection_reason?: string
  }>
  dictionary_source?: string

  // === 熟词僻义（V5 结构化）===
  is_rare_meaning?: boolean
  rare_meaning_info?: {
    common_meaning: string
    context_meaning: string
    textbook_source: string | null
  }
  // 向后兼容
  textbook_meaning?: string
  textbook_source?: string
  context_meaning?: string
  similar_words?: Array<{ word: string; textbook: string; rare: string }>

  // === 状态 ===
  point_verified: boolean
}
```

### 3.5 新增排错码常量

```typescript
/** 排错依据编码 */
export const REJECTION_CODES = {
  WORD_MEANING: '词义不符',
  COLLOCATION: '搭配错误',
  LOGIC: '逻辑矛盾',
  FORM: '形式错误',
  EMOTION: '情感方向错误',
} as const

export type RejectionCode = typeof REJECTION_CODES[keyof typeof REJECTION_CODES]
```

---

## 四、前端展示重构

### 4.1 完形填空详情页 (ClozeDetailContent.tsx)

#### 4.1.1 新增置信度显示

```tsx
// 在 Popover 标题区域显示置信度
<Space>
  <Tag color={confidence === 'high' ? 'green' : confidence === 'medium' ? 'gold' : 'red'}>
    置信度: {confidence}
  </Tag>
  {confidence_reason && (
    <Text type="secondary" style={{ fontSize: 11 }}>
      {confidence_reason}
    </Text>
  )}
</Space>
```

#### 4.1.2 更新排错点展示

```tsx
// 排错点列表（按选项分组）
{rejectionPoints.length > 0 && (
  <div style={{ marginTop: 8, padding: '8px 10px', background: '#fff1f0', borderRadius: 6 }}>
    <Text type="secondary" style={{ fontSize: 13, marginBottom: 4, display: 'block' }}>
      排错分析：
    </Text>
    {rejectionPoints.map((rp, idx) => (
      <div key={idx} style={{ padding: '4px 0' }}>
        <Tag color="red" style={{ fontSize: 11 }}>{rp.option_word}</Tag>
        <Tag style={{ fontSize: 10 }}>{rp.rejection_code}</Tag>
        <Text type="secondary" style={{ fontSize: 12 }}>{rp.rejection_reason}</Text>
      </div>
    ))}
  </div>
)}
```

#### 4.1.3 更新 word_analysis 表格（动态维度）

```tsx
function renderWordAnalysisTable(wordAnalysis: Record<string, any>, correctWord: string) {
  // 获取维度列（动态）
  const firstWord = Object.values(wordAnalysis)[0]
  const dimensionKeys = firstWord?.dimensions ? Object.keys(firstWord.dimensions) : []

  // 判断词性类型（用于特殊渲染）
  const isEmotionAdjective = dimensionKeys.includes('情感强度')
  const isConjunction = dimensionKeys.includes('逻辑方向')

  return (
    <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ background: '#f5f5f5' }}>
          <th style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>单词</th>
          <th style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>词频</th>
          <th style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>释义</th>
          {dimensionKeys.map(key => (
            <th key={key} style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>
              {key}
            </th>
          ))}
          <th style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>排除理由</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(wordAnalysis).map(([word, data]) => (
          <tr key={word} style={{ background: word === correctWord ? '#e6f7ff' : 'white' }}>
            <td style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>
              <Text strong={word === correctWord}>{word}</Text>
            </td>
            <td style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>
              {data.collins_frequency || '-'}
            </td>
            <td style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>
              {data.definition}
            </td>
            {dimensionKeys.map(key => (
              <td key={key} style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>
                {data.dimensions?.[key] || '-'}
              </td>
            ))}
            <td style={{ padding: '5px 8px', border: '1px solid #e8e8e8' }}>
              {word !== correctWord && data.rejection_reason ? (
                <Text type="danger" style={{ fontSize: 11 }}>{data.rejection_reason}</Text>
              ) : '-'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
```

#### 4.1.4 更新辅助考点展示（支持 co-primary）

```tsx
// PointTagGroup.tsx 更新
function PointTagGroup({ primaryPoint, secondaryPoints, ... }) {
  const coPrimaryPoints = secondaryPoints.filter(sp => sp.weight === 'co-primary')
  const auxiliaryPoints = secondaryPoints.filter(sp => sp.weight === 'auxiliary')

  return (
    <Space wrap>
      {/* 主考点 */}
      {primaryPoint && (
        <Tag color={CATEGORY_COLORS[primaryPoint.category]}>
          {primaryPoint.code} {primaryPoint.name}
        </Tag>
      )}

      {/* 联合主考点（A5+D1融合场景）*/}
      {coPrimaryPoints.map(sp => (
        <Tag key={sp.code} color="gold" style={{ borderStyle: 'dashed' }}>
          {sp.code} {sp.name} (联合)
        </Tag>
      ))}

      {/* 辅助考点 */}
      {auxiliaryPoints.slice(0, maxSecondaryVisible).map(sp => (
        <Tag key={sp.code} color="default" style={{ fontSize: 11 }}>
          +{sp.code}
        </Tag>
      ))}
    </Space>
  )
}
```

---

### 4.2 考点汇总页面 (ClozePointsPage.tsx)

**文件位置**: `frontend/src/pages/ClozePointsPage.tsx`

#### 4.2.1 表格列重构

**现有问题**：
- 使用旧 V1 三分类（固定搭配/词义辨析/熟词僻义）颜色
- word_analysis 表格使用固定的三维度列（使用对象/使用场景/正负态度）
- 缺少置信度、排错点等 V5 字段展示

**重构方案**：

```tsx
// ============================================================================
//  表格列定义更新
// ============================================================================

const columns: ColumnsType<PointSummary> = [
  {
    title: '考点词',
    dataIndex: 'word',
    key: 'word',
    width: 120,
    render: (word: string) => <Text strong style={{ fontSize: 14 }}>{word}</Text>,
  },
  {
    title: '释义',
    dataIndex: 'definition',
    key: 'definition',
    width: 200,
    ellipsis: true,
    render: (def: string) => def || '-',
  },
  {
    title: '主考点',
    dataIndex: 'point_type',
    key: 'point_type',
    width: 140,
    render: (type: string, record) => {
      const primaryPoint = (record as any).primary_point
      const color = primaryPoint?.category
        ? CATEGORY_COLORS[primaryPoint.category]
        : POINT_TYPE_COLORS_V1[type] || 'default'
      const label = primaryPoint?.code
        ? `${primaryPoint.code} ${POINT_CODE_TO_SHORT_NAME[primaryPoint.code]}`
        : type
      return <Tag color={color}>{label}</Tag>
    },
  },
  // ★新增：置信度列
  {
    title: '置信度',
    key: 'confidence',
    width: 80,
    render: (_, record) => {
      const confidence = (record as any).confidence
      if (!confidence) return '-'
      const colorMap = { high: 'green', medium: 'gold', low: 'red' }
      return (
        <Tag color={colorMap[confidence] || 'default'} style={{ fontSize: 11 }}>
          {confidence}
        </Tag>
      )
    },
  },
  {
    title: '出现次数',
    dataIndex: 'frequency',
    key: 'frequency',
    width: 80,
    align: 'center',
    render: (freq: number) => <Tag color="blue">{freq}</Tag>,
  },
  {
    title: '例句',
    key: 'occurrences',
    render: (_, record) => {
      if (!record.occurrences?.length) return '-'
      return (
        <div style={{ maxHeight: 80, overflow: 'auto' }}>
          {record.occurrences.slice(0, 2).map((occ, idx) => (
            <div key={idx} style={{ marginBottom: 4, padding: '4px 8px', background: '#fafafa', borderRadius: 4, fontSize: 12 }}>
              <Text type="secondary" ellipsis style={{ maxWidth: 300 }}>
                {occ.sentence}
              </Text>
            </div>
          ))}
          {record.occurrences.length > 2 && (
            <Text type="secondary" style={{ fontSize: 11 }}>
              +{record.occurrences.length - 2} 更多...
            </Text>
          )}
        </div>
      )
    },
  },
]
```

#### 4.2.2 展开行 word_analysis 表格（动态维度）

```tsx
// ============================================================================
//  展开行：动态维度表格
// ============================================================================

function renderDynamicDimensionsTable(
  wordAnalysis: Record<string, any>,
  correctWord: string
) {
  if (!wordAnalysis || Object.keys(wordAnalysis).length === 0) return null

  // 动态获取维度列
  const firstWord = Object.values(wordAnalysis)[0] as any
  const dimensionKeys = firstWord?.dimensions ? Object.keys(firstWord.dimensions) : []

  // 判断词性类型
  const isEmotionAdjective = dimensionKeys.includes('情感强度')
  const isConjunction = dimensionKeys.includes('逻辑方向')
  const isVerb = dimensionKeys.includes('动作性质')
  const isNoun = dimensionKeys.includes('可数性')
  const isAdverb = dimensionKeys.includes('修饰对象')

  return (
    <div style={{ marginBottom: 8 }}>
      <Text strong style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>
        词义分析（{isEmotionAdjective ? '情感形容词' : isConjunction ? '逻辑连词' : isVerb ? '动词' : isNoun ? '名词' : isAdverb ? '副词' : '普通'}）：
      </Text>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', fontSize: 11, borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f5f5f5' }}>
              <th style={{ padding: '4px 8px', border: '1px solid #e8e8e8', whiteSpace: 'nowrap' }}>单词</th>
              <th style={{ padding: '4px 8px', border: '1px solid #e8e8e8' }}>词频</th>
              <th style={{ padding: '4px 8px', border: '1px solid #e8e8e8' }}>释义</th>
              {dimensionKeys.map(key => (
                <th key={key} style={{ padding: '4px 8px', border: '1px solid #e8e8e8' }}>
                  {key}
                </th>
              ))}
              <th style={{ padding: '4px 8px', border: '1px solid #e8e8e8' }}>排除理由</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(wordAnalysis).map(([word, data]: [string, any]) => (
              <tr key={word} style={{ background: word === correctWord ? '#e6f7ff' : 'white' }}>
                <td style={{ padding: '4px 8px', border: '1px solid #e8e8e8', whiteSpace: 'nowrap' }}>
                  <Text strong={word === correctWord}>{word}</Text>
                </td>
                <td style={{ padding: '4px 8px', border: '1px solid #e8e8e8' }}>
                  {data.collins_frequency || '-'}
                </td>
                <td style={{ padding: '4px 8px', border: '1px solid #e8e8e8', maxWidth: 200 }}>
                  <Text type="secondary" style={{ fontSize: 10 }}>{data.definition}</Text>
                </td>
                {dimensionKeys.map(key => (
                  <td key={key} style={{ padding: '4px 8px', border: '1px solid #e8e8e8' }}>
                    {data.dimensions?.[key] || '-'}
                  </td>
                ))}
                <td style={{ padding: '4px 8px', border: '1px solid #e8e8e8' }}>
                  {word !== correctWord && data.rejection_reason ? (
                    <Text type="danger" style={{ fontSize: 10 }}>{data.rejection_reason}</Text>
                  ) : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

#### 4.2.3 展开行排错点展示

```tsx
// ============================================================================
//  展开行：排错点列表
// ============================================================================

function renderRejectionPoints(rejectionPoints: RejectionPoint[]) {
  if (!rejectionPoints || rejectionPoints.length === 0) return null

  return (
    <div style={{ marginTop: 8, padding: '8px 12px', background: '#fff1f0', borderRadius: 4 }}>
      <Text strong style={{ fontSize: 12, marginBottom: 4, display: 'block' }}>
        排错分析：
      </Text>
      {rejectionPoints.map((rp, idx) => (
        <div key={idx} style={{ padding: '4px 0', borderBottom: idx < rejectionPoints.length - 1 ? '1px dashed #ffa39e' : 'none' }}>
          <Tag color="red" style={{ fontSize: 11 }}>{rp.option_word}</Tag>
          <Tag style={{ fontSize: 10 }}>{rp.rejection_code}</Tag>
          <Text type="secondary" style={{ fontSize: 11 }}>{rp.rejection_reason}</Text>
        </div>
      ))}
    </div>
  )
}
```

#### 4.2.4 筛选器更新

**现有筛选器**：
- 级联筛选器（大类 → 具体考点）
- 优先级筛选
- 年级筛选
- 关键词搜索

**保持不变**，但更新快捷筛选标签：

```tsx
/** 快捷筛选标签配置 - V5 版本 */
const QUICK_FILTER_TAGS = [
  { key: 'P1', label: 'P1 核心考点', category: undefined, pointType: undefined, priority: 1 },
  { key: 'A', label: 'A 语篇理解', category: 'A', pointType: undefined, priority: undefined },
  { key: 'B', label: 'B 逻辑关系', category: 'B', pointType: undefined, priority: undefined },
  { key: 'C', label: 'C 句法语法', category: 'C', pointType: undefined, priority: undefined },
  { key: 'D', label: 'D 词汇选项', category: 'D', pointType: undefined, priority: undefined },
  { key: 'E', label: 'E 常识主题', category: 'E', pointType: undefined, priority: undefined },
] as const
```

---

### 4.3 完形填空列表页 (ClozePage.tsx)

**文件位置**: `frontend/src/pages/ClozePage.tsx`

#### 4.3.1 考点分布标签更新

**现有问题**：
- 使用旧 V1 分类展示考点分布
- 表格列使用 `point_distribution` 字段

**重构方案**：

```tsx
// ============================================================================
//  考点分布展示 - V5 按大类
// ============================================================================

// 在表格列中更新考点分布展示
{
  title: '考点分布',
  key: 'point_distribution',
  width: 280,
  render: (_, record) => {
    // V5: 优先使用按大类分组的数据
    if (record.point_distribution_by_category && Object.keys(record.point_distribution_by_category).length > 0) {
      return (
        <Space size={4} wrap>
          {Object.entries(record.point_distribution_by_category).map(([category, count]) => (
            <Tag key={category} color={CATEGORY_COLORS[category] || 'default'}>
              {CATEGORY_NAMES[category] || category} ({count as number})
            </Tag>
          ))}
        </Space>
      )
    }
    // V2 兼容：使用具体考点分布
    if (record.point_distribution && Object.keys(record.point_distribution).length > 0) {
      return (
        <Space size={4} wrap>
          {Object.entries(record.point_distribution).map(([code, count]) => {
            const category = code[0] // 获取大类字母
            return (
              <Tag key={code} color={CATEGORY_COLORS[category] || 'default'}>
                {code} ({count as number})
              </Tag>
            )
          })}
        </Space>
      )
    }
    // V1 兼容：使用旧分类
    if (record.point_distribution_v1 && Object.keys(record.point_distribution_v1).length > 0) {
      return (
        <Space size={4} wrap>
          {Object.entries(record.point_distribution_v1).map(([type, count]) => (
            <Tag key={type} color={POINT_TYPE_COLORS_V1[type] || 'default'}>
              {type} ({count})
            </Tag>
          ))}
        </Space>
      )
    }
    return '-'
  },
}
```

#### 4.3.2 筛选器更新（级联选择器）

```tsx
// ============================================================================
//  级联筛选器 - V5 考点类型
// ============================================================================

const POINT_CASCADER_OPTIONS = [
  {
    value: 'A',
    label: 'A 语篇理解类',
    children: [
      { value: 'A1', label: 'A1 上下文语义推断' },
      { value: 'A2', label: 'A2 复现与照应' },
      { value: 'A3', label: 'A3 代词指代' },
      { value: 'A4', label: 'A4 情节/行为顺序' },
      { value: 'A5', label: 'A5 情感态度' },
    ],
  },
  {
    value: 'B',
    label: 'B 逻辑关系类',
    children: [
      { value: 'B1', label: 'B1 并列一致' },
      { value: 'B2', label: 'B2 转折对比' },
      { value: 'B3', label: 'B3 因果关系' },
      { value: 'B4', label: 'B4 其他逻辑关系' },
    ],
  },
  {
    value: 'C',
    label: 'C 句法语法类',
    children: [
      { value: 'C1', label: 'C1 词性与句子成分' },
      { value: 'C2', label: 'C2 固定搭配' },
      { value: 'C3', label: 'C3 语法形式限制' },
    ],
  },
  {
    value: 'D',
    label: 'D 词汇选项类',
    children: [
      { value: 'D1', label: 'D1 常规词义辨析' },
      { value: 'D2', label: 'D2 熟词僻义' },
    ],
  },
  {
    value: 'E',
    label: 'E 常识主题类',
    children: [
      { value: 'E1', label: 'E1 生活/场景常识' },
      { value: 'E2', label: 'E2 主题主旨与人物共情' },
    ],
  },
]
```

---

## 五、讲义内容重构

### 5.1 更新 `ClozeHandoutView.tsx`

#### 5.1.1 删除旧分类展示

```tsx
// 删除以下代码
// ❌ 固定搭配分组
// ❌ 词义辨析分组
// ❌ 熟词僻义分组
```

#### 5.1.2 新增按大类分组展示

```tsx
function ClozeHandoutView() {
  // 按大类分组
  const pointsByCategory = useMemo(() => {
    const grouped: Record<string, PointWordData[]> = {
      A: [], B: [], C: [], D: [], E: []
    }

    // 遍历所有考点，按主考点编码分类
    allPoints.forEach(point => {
      const category = point.primary_point?.code?.[0] || 'A'
      if (grouped[category]) {
        grouped[category].push(point)
      }
    })

    return grouped
  }, [allPoints])

  return (
    <div>
      {['A', 'B', 'C', 'D', 'E'].map(category => (
        <Card key={category} title={`${category} ${CATEGORY_NAMES[category]}`}>
          <PointListByCategory
            category={category}
            points={pointsByCategory[category]}
          />
        </Card>
      ))}
    </div>
  )
}
```

#### 5.1.3 新增考点详情展示

```tsx
function PointListByCategory({ category, points }: { category: string, points: PointWordData[] }) {
  // 按具体考点编码细分
  const pointsByCode = useMemo(() => {
    const grouped: Record<string, PointWordData[]> = {}
    points.forEach(point => {
      const code = point.primary_point?.code || 'A1'
      if (!grouped[code]) grouped[code] = []
      grouped[code].push(point)
    })
    return grouped
  }, [points])

  return (
    <Collapse>
      {Object.entries(pointsByCode).map(([code, items]) => (
        <Collapse.Panel
          key={code}
          header={`${code} ${POINT_TYPE_BY_CODE[code]?.name} (${items.length})`}
        >
          <List
            dataSource={items}
            renderItem={item => (
              <List.Item>
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Text strong>{item.word}</Text>
                  <Text type="secondary">{item.definition}</Text>
                  {/* 动态维度展示 */}
                  {item.word_analysis?.[item.word]?.dimensions && (
                    <DimensionsDisplay dimensions={item.word_analysis[item.word].dimensions} />
                  )}
                </Space>
              </List.Item>
            )}
          />
        </Collapse.Panel>
      ))}
    </Collapse>
  )
}
```

---

## 六、执行计划

### 6.1 阶段划分

| 阶段 | 任务 | 依赖 | 状态 |
|------|------|------|------|
| Phase 1 | 后端 `ClozeAnalyzerV5` 实现 | 无 | 待执行 |
| Phase 2 | 前端类型系统更新 | Phase 1 | 待执行 |
| Phase 3 | 前端展示组件重构 | Phase 2 | 待执行 |
| Phase 4 | 讲义内容重构 | Phase 3 | 待执行 |
| Phase 5 | 数据清理（可选） | Phase 4 | 待执行 |

### 6.2 Phase 1 详细任务清单

- [ ] 1.1 新增 `PointAnalysisResultV5` 数据类
- [ ] 1.2 新增 `ANALYZE_PROMPT_V5` 提示词常量
- [ ] 1.3 新增 `ClozeAnalyzerV5` 类
- [ ] 1.4 实现 `_parse_response_v5` 解析器
- [ ] 1.5 实现 `_process_rare_meaning` 熟词僻义处理
- [ ] 1.6 更新 API 路由（新增 V5 接口或升级现有接口）
- [ ] 1.7 单元测试

### 6.3 Phase 2 详细任务清单

- [ ] 2.1 更新 `SecondaryPoint` 类型
- [ ] 2.2 更新 `RejectionPoint` 类型
- [ ] 2.3 新增词性维度类型（6种）
- [ ] 2.4 更新 `ClozePointNew` 类型
- [ ] 2.5 新增 `REJECTION_CODES` 常量

### 6.4 Phase 3 详细任务清单

- [ ] 3.1 更新 `ClozeDetailContent.tsx`
  - [ ] 3.1.1 新增置信度显示
  - [ ] 3.1.2 更新排错点展示
  - [ ] 3.1.3 更新 word_analysis 表格（动态维度）
- [ ] 3.2 更新 `PointTagGroup.tsx`
  - [ ] 3.2.1 支持 co-primary 联合主考点展示
- [ ] 3.3 更新 `ClozePage.tsx`（筛选器兼容）

### 6.5 Phase 4 详细任务清单

- [ ] 4.1 删除旧分类展示代码
- [ ] 4.2 新增按大类分组展示
- [ ] 4.3 新增考点详情展示（动态维度）

### 6.6 Phase 5 详细任务清单（可选）

- [ ] 5.1 清空旧考点分析数据
- [ ] 5.2 重新分析所有空格
- [ ] 5.3 验证数据一致性

---

## 附录：16种考点编码速查表

| 编码 | 名称 | 大类 | 优先级 |
|------|------|------|--------|
| A1 | 上下文语义推断 | 语篇理解类 | P1-核心 |
| A2 | 复现与照应 | 语篇理解类 | P1-核心 |
| A3 | 代词指代 | 语篇理解类 | P1-核心 |
| A4 | 情节/行为顺序 | 语篇理解类 | P1-核心 |
| A5 | 情感态度 | 语篇理解类 | P1-核心 |
| B1 | 并列一致 | 逻辑关系类 | P1-核心 |
| B2 | 转折对比 | 逻辑关系类 | P1-核心 |
| B3 | 因果关系 | 逻辑关系类 | P1-核心 |
| B4 | 其他逻辑关系 | 逻辑关系类 | P1-核心 |
| C1 | 词性与句子成分 | 句法语法类 | P2-重要 |
| C2 | 固定搭配 | 句法语法类 | P2-重要 |
| C3 | 语法形式限制 | 句法语法类 | P2-重要 |
| D1 | 常规词义辨析 | 词汇选项类 | P3-一般 |
| D2 | 熟词僻义 | 词汇选项类 | P3-一般 |
| E1 | 生活/场景常识 | 常识主题类 | P3-一般 |
| E2 | 主题主旨与人物共情 | 常识主题类 | P3-一般 |

---

## 附录：完整 V5 提示词

> 以下提示词应完整复制到 `backend/app/services/cloze_analyzer.py` 的 `ANALYZE_PROMPT_V5` 常量中

```python
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
{context} 必须包含完整的完型填空文章

{textbook_section} 当前的选项所在的句子

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
            "dimensions": {{ ... }},
            "rejection_reason": "排除理由（词义层面展开，与rejection_points互补）"
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
- ❌ 不得输出confusion_words字段（已合并）
- ❌ 不得在is_rare_meaning=true时省略rare_meaning_info任何子字段
- ❌ 不得用「感觉顺」或「语感」作为explanation理由

"""
```

---

## 变更记录

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2025-03-19 | V5 | 初始版本，完整重构方案 |
| 2025-03-19 | V5.1 | 补充考点汇总页面、列表页重构方案、完整提示词附录 |
