# 完形填空考点分类系统文档

> 本文档记录完形填空考点分类系统的演进历程，包括 v1（3种考点）和 v2（5大类16个考点）的完整说明。
>
> **当前版本**: v1（3种考点），v2 规划中
> **最后更新**: 2026-03-15

---

## 当前系统（v1）

### 支持的考点类型（3种）

| 类型 | 识别特征 | 专用字段 |
|------|---------|---------|
| 固定搭配 | 正确答案与某个词形成固定搭配 | `phrase`, `similar_phrases` |
| 词义辨析 | 四个选项在某种维度上有相似性，需根据语境区分 | `word_analysis`, `dictionary_source` |
| 熟词僻义 | 课本单词表里有该词，但文章中的意思与课本释义不同 | `textbook_meaning`, `textbook_source`, `context_meaning`, `similar_words` |

### 三类考点判断标准

#### 1. 固定搭配

**识别特征：** 正确答案与某个词形成固定搭配

**包含类型：**
- 短语动词：look up, depend on, take off, give up, work out
- 动词+名词：make a decision, take a break, have a look, take a chance
- 形容词+介词：be good at, be interested in, be proud of, be keen on
- 名词+介词：access to, key to, answer to, attention to
- 介词短语：at night, in the morning, on Sunday, by bus, in English
- 惯用表达：as soon as, as well as, neither...nor, as a matter of fact

**输出格式：**
```json
{
    "point_type": "固定搭配",
    "phrase": "完整短语",
    "translation": "短语翻译",
    "explanation": "解析说明",
    "confusion_words": [{"word": "易混淆词", "meaning": "含义", "reason": "排除理由"}],
    "similar_phrases": ["相似短语1", "相似短语2"],
    "tips": "记忆技巧"
}
```

#### 2. 词义辨析

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

**输出格式：**
```json
{
    "point_type": "词义辨析",
    "translation": "该词的中文翻译",
    "dictionary_source": "柯林斯词典",
    "word_analysis": {
        "正确词": {
            "definition": "英英解释",
            "dimensions": {"使用对象": "...", "使用场景": "...", "正负态度": "..."}
        },
        "干扰词1": {
            "definition": "英英解释",
            "dimensions": {...},
            "rejection_reason": "排除理由"
        }
    },
    "confusion_words": [{"word": "干扰词", "meaning": "含义", "reason": "排除理由"}],
    "tips": "记忆技巧"
}
```

#### 3. 熟词僻义

**判断标准（基于课本单词表）：**
- **熟词**：课本单词表里有这个词（人教版/外研版初一至初三）
- **僻义**：文章中的意思与课本单词表的释义不同

**僻义类型：**
- 词性转换：book (预订), water (浇水), hand (传递), warm (加热)
- 专业术语：mouse (鼠标), web (网站), surf (上网), program (编程)
- 比喻引申：cold (冷淡), hot (热门/辣), green (环保的/没经验的)
- 多义词引申：tie (平局), head (朝…方向行驶), pad (发射台)

**输出格式：**
```json
{
    "point_type": "熟词僻义",
    "textbook_meaning": "课本中的常见释义",
    "textbook_source": "课本出处（如：人教版八年级上册 Unit 5）",
    "context_meaning": "当前语境下的释义",
    "explanation": "解析说明（课本释义与语境释义的差异）",
    "similar_words": [{"word": "示例词", "textbook": "课本释义", "rare": "僻义"}],
    "tips": "记忆技巧"
}
```

### 判断流程

```
1. 首先检查是否为【固定搭配】（最明显的特征）
2. 其次检查是否为【熟词僻义】（课本有该词，但当前意思与课本不同）
3. 最后判断为【词义辨析】（最常见的情况）
```

### 数据模型

**数据库表：** `cloze_points`

| 字段 | 类型 | 说明 |
|------|------|------|
| `point_type` | String(50) | 考点类型（单选：固定搭配/词义辨析/熟词僻义） |
| `point_detail` | Text | 考点详解 |
| `translation` | Text | 翻译 |
| `explanation` | Text | 解析 |
| `confusion_words` | Text (JSON) | 易混淆词信息 |
| `tips` | Text | 记忆技巧 |
| `phrase` | String(255) | 固定搭配专用：完整短语 |
| `similar_phrases` | Text (JSON) | 固定搭配专用：相似短语列表 |
| `word_analysis` | Text (JSON) | 词义辨析专用：三维度分析 |
| `dictionary_source` | String(100) | 词义辨析专用：词典来源 |
| `textbook_meaning` | Text | 熟词僻义专用：课本释义 |
| `textbook_source` | String(100) | 熟词僻义专用：课本出处 |
| `context_meaning` | Text | 熟词僻义专用：语境释义 |
| `similar_words` | Text (JSON) | 熟词僻义专用：相似词列表 |

**CHECK 约束：**
```sql
CONSTRAINT ck_point_type CHECK (point_type IN ('固定搭配', '词义辨析', '熟词僻义'))
```

### Prompt 模板

见 `backend/app/services/cloze_analyzer.py` 第 51-201 行的 `ANALYZE_PROMPT`

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/cloze` | GET | 获取完形文章列表，支持按 `point_type` 筛选 |
| `/api/cloze/{id}` | GET | 获取完形详情（含考点分析） |
| `/api/cloze/points/summary` | GET | 获取考点汇总，按类型聚合 |
| `/api/cloze/filters` | GET | 获取筛选项（含所有 point_types） |
| `/api/cloze/blanks/{id}/point` | PUT | 更新考点分析 |

### 前端展示

**颜色映射：**
```typescript
const POINT_TYPE_COLORS: Record<string, string> = {
  '固定搭配': 'green',
  '词义辨析': 'orange',
  '熟词僻义': 'purple',
}
```

**组件文件：**
- `frontend/src/components/cloze/ClozeDetailContent.tsx` - 详情页考点展示
- `frontend/src/pages/ClozePointsPage.tsx` - 考点汇总页

---

## 新系统（v2）

### 设计目标

1. **分类细化**：从 3 种扩展为 5 大类 16 个考点
2. **多标签支持**：每个空格可有主考点 + 辅助考点 + 排错点
3. **优先级体系**：引入 P1/P2/P3 优先级，体现做题思路

### 考点体系（5大类16个考点）

#### A. 语篇理解类 (P1-核心)

> 解决"这篇文章到底在说什么、这个空和上下文怎么连"

| 编码 | 名称 | 定义 | 触发条件 | 典型信号 |
|------|------|------|---------|---------|
| A1 | 上下文语义推断 | 根据空前空后及前后句推断空格应表达的大致语义 | 空本身单靠选项看不出来，必须靠上下文补充信息 | 空前有铺垫，空后有解释；前一句提出问题，后一句给结果 |
| A2 | 复现与照应 | 前文或后文出现与答案意思相同、相近、相反或同一主题链上的词 | 文中有明显重复、同义替换、近义呼应 | 原词复现，同义词复现，主题链词汇，动作链重复 |
| A3 | 代词指代 | 通过代词回指确定人物、事物或信息对象 | 空附近出现代词，代词的指向会影响意思判断 | he/she/it/they, this/that/these/those, one/ones, his/her/their |
| A4 | 情节/行为顺序 | 根据故事发展顺序、动作先后顺序判断哪个词最合理 | 文章是叙事文，人物动作存在前后链条 | first/then/later/finally, before/after, 动作必须按顺序发生 |
| A5 | 情感态度 | 根据人物心情、作者评价、语境色彩判断褒贬方向 | 选项多为形容词、副词、情绪类动词，人物情感明显变化 | happy/excited/pleased/surprised/sad/shock/upset/angry |

#### B. 逻辑关系类 (P1-核心)

> 解决"前后句是什么关系，空里应填什么方向的意思"

| 编码 | 名称 | 定义 | 典型信号 |
|------|------|------|---------|
| B1 | 并列一致 | 前后内容语义一致、方向一致、性质相近 | and, also, as well, both...and, not only...but also |
| B2 | 转折对比 | 前后语义相反或预期相反 | but, however, yet, although, instead, while |
| B3 | 因果关系 | 前因后果或前果后因 | because, so, therefore, since, as a result |
| B4 | 其他逻辑关系 | 递进、让步、条件、举例、总结等 | even if, unless, in fact, for example, in short |

#### C. 句法语法类 (P2-重要)

> 解决"这个位置从结构上允许填什么"

| 编码 | 名称 | 定义 | 典型信号 |
|------|------|------|---------|
| C1 | 词性与句子成分 | 根据句法位置判断所需词类 | 冠词后→名词，系动词后→形容词，情态动词后→动词原形，副词修饰动词/形容词 |
| C2 | 固定搭配 | 某些词必须和特定介词、名词、动词或句型一起使用 | depend on, be interested in, make a decision, pay attention to |
| C3 | 语法形式限制 | 由时态、语态、主谓一致、非谓语等形式规则限制 | 时间状语，主语单复数，be done/doing/to do，比较级标志词 |

#### D. 词汇选项类 (P3-一般)

> 解决"几个选项里到底哪个词最贴切"

| 编码 | 名称 | 定义 | 典型信号 |
|------|------|------|---------|
| D1 | 常规词义辨析 | 几个选项词性相同、意思相近，需要根据语境精细区分 | say/tell/speak/talk, look/see/watch/notice, job/work/career/task |
| D2 | 熟词僻义 | 常见词在特定语境中使用非常见义项 | run a company, head north, tie for first place, book a room, miss a class |

#### E. 常识主题类 (P3-一般)

> 解决"文章真实场景下，哪种表达最符合常理和人物心理"

| 编码 | 名称 | 定义 | 典型信号 |
|------|------|------|---------|
| E1 | 生活常识/场景常识 | 根据现实世界常识判断哪个选项合理 | 医院、学校、车站、比赛等固定场景，人物通常行为模式 |
| E2 | 主题主旨与人物共情 | 从全文主题和人物心理出发理解作者真正想表达的意思 | 成长、亲情、挫折、鼓励、帮助等主题，结尾升华句 |

### 多标签结构

每个空格可拥有：

```json
{
    "blank_id": 7,
    "primary_point": {
        "code": "B2",
        "name": "转折对比",
        "explanation": "前后语义相反，but 提示转折"
    },
    "secondary_points": [
        {"code": "A5", "explanation": "情感态度由正面转向负面"},
        {"code": "A1", "explanation": "上下文语义推断支持转折"}
    ],
    "rejection_points": [
        {"option_word": "happy", "code": "A5", "explanation": "与转折后的负面态度矛盾"},
        {"option_word": "excited", "code": "B1", "explanation": "与转折逻辑矛盾"}
    ],
    "confidence": 0.91
}
```

### 判断流程（语义→逻辑→结构→词项）

```
1. 【语义层面】先判断是否需要上下文语义推断（A类）
2. 【逻辑层面】检查是否有逻辑关系词（B类）
3. 【结构层面】分析句子结构、语法（C类）
4. 【词项层面】最后判断词汇选项（D类）
5. 【背景层面】是否需要常识或主题理解（E类）
```

### 新数据库模型

```python
class ClozePoint(Base):
    # 新增字段
    primary_point_code = Column(String(20))  # 主考点编码，如 "A1", "B2"
    legacy_point_type = Column(String(50))   # 兼容旧类型

class ClozeSecondaryPoint(Base):
    """辅助考点关联表"""
    cloze_point_id = Column(Integer, ForeignKey("cloze_points.id"))
    point_code = Column(String(20))
    explanation = Column(Text)
    sort_order = Column(Integer)

class ClozeRejectionPoint(Base):
    """排错点关联表"""
    cloze_point_id = Column(Integer, ForeignKey("cloze_points.id"))
    option_word = Column(String(255))  # 被排除的选项词
    point_code = Column(String(20))    # 排错依据
    explanation = Column(Text)

class PointTypeDefinition(Base):
    """考点类型定义表"""
    code = Column(String(20), unique=True)       # A1, B2, etc.
    category = Column(String(10))                 # A, B, C, D, E
    category_name = Column(String(50))           # 语篇理解类
    name = Column(String(50))                    # 上下文语义推断
    priority = Column(Integer)                   # 1, 2, 3
    description = Column(Text)
```

### 旧类型映射

| 旧类型 (v1) | 新编码 (v2) | 新名称 |
|-------------|-------------|--------|
| 固定搭配 | C2 | 句法语法类-固定搭配 |
| 词义辨析 | D1 | 词汇选项类-常规词义辨析 |
| 熟词僻义 | D2 | 词汇选项类-熟词僻义 |

### 新前端颜色映射

```typescript
// 按大类着色
const CATEGORY_COLORS: Record<string, string> = {
    'A': 'blue',      // 语篇理解
    'B': 'cyan',      // 逻辑关系
    'C': 'green',     // 句法语法
    'D': 'orange',    // 词汇选项
    'E': 'purple',    // 常识主题
}

// 按优先级着色
const PRIORITY_COLORS: Record<number, string> = {
    1: 'red',     // P1 - 核心
    2: 'gold',    // P2 - 重要
    3: 'default', // P3 - 一般
}
```

---

## 参考文件

| 文件 | 说明 |
|------|------|
| `backend/app/models/cloze.py` | 数据库模型定义 |
| `backend/app/services/cloze_analyzer.py` | 考点分析服务（Prompt + API 调用） |
| `backend/app/schemas/cloze.py` | Pydantic Schema 定义 |
| `backend/app/api/cloze.py` | REST API 路由 |
| `frontend/src/types/index.ts` | 前端类型定义 |
| `frontend/src/components/cloze/ClozeDetailContent.tsx` | 详情页组件 |
| `frontend/src/pages/ClozePointsPage.tsx` | 考点汇总页 |
