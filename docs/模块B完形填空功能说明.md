# 模块B：完形填空功能说明

## 一、功能概述

本模块是北京中考英语教研资料系统的**完形填空**处理子系统，核心功能是将中考英语试卷中的完形填空题目自动提取、分类、分析考点，形成可检索、可定位的考点数据库。

### 系统能力

| 能力 | 说明 |
|------|------|
| 完形提取 | 自动识别并提取试卷中的完形填空文章 |
| 空格解析 | 识别每个空格的位置、选项、正确答案 |
| 话题分类 | AI自动分类文章话题 |
| 考点分析 | AI分析三类考点（固定搭配/词义辨析/熟词僻义）
| 考点汇总 | 按考点类型聚合查看所有实例 |
| 定位功能 | 点击考点跳转到原文位置 |

> **高频词汇**：完形高频词汇已整合到**统一高频词库**（与阅读共享入口），支持按来源筛选（阅读/完形/全部）。详见「试卷导入与内容提取功能说明」的词库管理章节。

### 适用场景

- **教研备课**：快速掌握考点分布，针对性讲解
- **专项训练**：按考点类型（固定搭配/词义辨析等）筛选练习
- **学生复习**：查看某考点的所有真题实例
- **考点归纳**：整理高频考点词汇和易混淆词

---

## 二、完形填空提取（纯AI方式）

### 2.1 提取策略

**采用纯AI提取**（与阅读模块一致），不使用正则匹配。

> **为什么不用正则？**
> - 试卷格式不统一，正则匹配不可靠
> - 空格编号格式多样（①②③ / (1)(2)(3) / [1][2][3]）
> - 选项分布位置不固定
> - AI提取更准确、更灵活

### 2.2 AI提取流程

```
上传试卷 → 发送文档到通义千问 → AI识别完形部分 → 提取文章和空格 → 保存到数据库
                ↓
         结构化JSON输出
```

### 2.3 AI提取Prompt

```
你是中考英语试卷解析专家。
请从以下试卷内容中提取完形填空部分的信息。

试卷内容：
{document_content}

请返回JSON格式：
{
  "found": true/false,
  "passage": {
    "content_with_blanks": "带空格标记的原文（保留空格编号）",
    "content_full": "填入正确答案后的完整文章",
    "word_count": 词数
  },
  "blanks": [
    {
      "blank_number": 1,
      "char_position": 字符位置,
      "options": {
        "A": "选项A内容",
        "B": "选项B内容",
        "C": "选项C内容",
        "D": "选项D内容"
      },
      "correct_answer": "A/B/C/D",
      "correct_word": "正确答案对应的词",
      "explanation": "答案解析（如果有教师版解析）"
    }
  ]
}
```

### 2.4 用户进度展示

导入过程中，用户可实时看到每个步骤的进度：

```
┌─────────────────────────────────────────────────────────────────┐
│  导入进度: 2022东城初三期末英语.docx                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✅ 上传文件                                        完成         │
│  ✅ 解析文件名                                      完成         │
│  🔄 AI解析文档                                      处理中...    │
│     ├─ 阅读C/D篇: ✅ 提取2篇文章                               │
│     └─ 完形填空: 🔄 正在提取...                                 │
│  ⏳ 保存数据                                        等待中       │
│  ⏳ AI话题分类                                      等待中       │
│  ⏳ 考点分析 + 词汇提取                             等待中       │
│                                                                 │
│  总体进度: ████████░░░░ 40%                                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.5 提取结果示例

**带空格原文示例**：
```
I have always enjoyed reading. I remember the day when I ① my first book.
It was a children's story about a rabbit. I was so ② that I read it three times.
```

**选项关联示例**：
```json
{
  "blank_number": 1,
  "options": {
    "A": "bought",
    "B": "borrowed",
    "C": "read",
    "D": "wrote"
  },
  "correct_answer": "A",
  "correct_word": "bought"
}
```

---

## 三、三类考点分析

### 3.1 考点类型定义

> **说明**：词汇考查已整合到**统一高频词库**（与阅读共享），> 本模块专注于**三类结构性考点**分析。

| 类型 | 说明 | 识别特征 |
|------|------|----------|
| **固定搭配** | 短语动词、动词+名词、形容词+介词、介词短语、惯用表达 | 正确答案与某个词形成固定搭配 |
| **词义辨析** | 同义/近义词、词形辨析、词性辨析、语义强度、语域辨析 | 四个选项在某种维度上有相似性 |
| **熟词僻义** | 常见词的非常规含义（词性转换、专业术语、比喻引申） | 常见词，当前语境下使用非常规含义 |

### 3.2 固定搭配考点

**识别特征**：
- 正确答案与某个词形成固定搭配
- 选项中其他词无法与该词形成合理的搭配
- 搭配具有固定性，不能随意替换

**包含类型**：

1. **短语动词**：look up, depend on, take off, give up, work out
2. **动词+名词**：make a decision, take a break, have a look, take a chance
3. **形容词+介词**：be good at, be interested in, be proud of, be keen on
4. **名词+介词**：access to, key to, answer to, attention to
5. **介词短语**：at night, in the morning, on Sunday, by bus, in English
6. **惯用表达**：as soon as, as well as, neither...nor, as a matter of fact

**典型示例**：
- He decided to ___ a break. (take - take a break固定搭配)
- She is good ___ playing piano. (at - be good at固定搭配)
- I have access ___ the library. (to - access to固定搭配)
- ___ night, I usually read books. (At - at night固定搭配)

**AI分析输出**：
```json
{
  "point_type": "固定搭配",
  "phrase": "take a break",
  "translation": "休息一下",
  "context_sentence": "He decided to ___ a break.",
  "explanation": "take a break是固定搭配，表示"休息一下"。break在此语境下只能与take搭配。",
  "confusion_words": [
    {"word": "make", "meaning": "制作", "reason": "make a break不是固定搭配"},
    {"word": "have", "meaning": "有", "reason": "have a break不常用，不是标准搭配"},
    {"word": "do", "meaning": "做", "reason": "do a break不符合英语习惯"}
  ],
  "similar_phrases": ["take a chance", "take a look", "take a rest"],
  "tips": "记忆技巧：固定搭配需要整体记忆，不要逐词翻译"
}
```

### 3.3 词义辨析考点

**识别特征**：
- 四个选项在某种维度上有相似性
- 需要根据语境、搭配或语法规则区分
- 选项之间形成干扰项关系

**核心分析维度（三维度法）**：

| 维度 | 说明 | 示例 |
|------|------|------|
| **使用对象** | 该词用于描述什么/谁 | say强调内容，tell强调告知某人 |
| **使用场景** | 在什么情况下使用 | start可非正式使用，begin较正式 |
| **正负态度** | 词义隐含的褒贬色彩 | stubborn（贬）vs persistent（褒） |

> **词典来源**：使用柯林斯词典（Collins COBUILD）的英英解释作为词义辨析的标准参照。

**典型示例**：

**同义词辨析**：
- Please ___ me the truth. (tell - say后不能直接接人，speak不强调内容，tell强调告知)

**词形辨析**：
- The weather will ___ our plans. (affect - 动词"影响"；effect是名词"效果")

**词性辨析**：
- He works ___ to pass the exam. (hard - hard作副词"努力地"；hardly是否定副词"几乎不")

**AI分析输出**：
```json
{
  "point_type": "词义辨析",
  "correct_word": "tell",
  "translation": "告诉",
  "context_sentence": "Please ___ me the truth.",
  "dictionary_source": "柯林斯词典",
  "word_analysis": {
    "tell": {
      "definition": "If you tell someone something, you give them information.",
      "dimensions": {
        "使用对象": "直接接人（tell sb sth）",
        "使用场景": "日常对话、叙事表达",
        "正负态度": "中性词"
      }
    },
    "say": {
      "definition": "When you say something, you speak words.",
      "dimensions": {
        "使用对象": "强调内容，不能直接接人",
        "使用场景": "引用话语、转述",
        "正负态度": "中性词"
      },
      "rejection_reason": "say后不能直接接人"
    },
    "speak": {
      "definition": "When you speak, you use your voice to talk.",
      "dimensions": {
        "使用对象": "强调说话行为本身",
        "使用场景": "正式场合、演讲",
        "正负态度": "中性词"
      },
      "rejection_reason": "speak不强调告知具体内容"
    }
  },
  "distractors": [
    {"option": "A", "word": "say", "reason": "say后不能直接接人，需用say to me"},
    {"option": "C", "word": "speak", "reason": "speak不强调告知具体内容"},
    {"option": "D", "word": "talk", "reason": "talk强调对话交流，不是单向告知"}
  ],
  "tips": "tell强调"告知某人某事"，结构为 tell sb sth"
}
```

### 3.4 熟词僻义考点

**判断标准（基于课本单词表）**：

| 概念 | 判断标准 | 说明 |
|------|----------|------|
| **熟词** | 课本单词表里有这个词 | 人教版/外研版初一至初三课本单词表 |
| **僻义** | 文章中的意思与课本单词表的释义不同 | 当前语境使用了非常规含义 |

> **核心逻辑**：只有同时满足"课本有"且"意思不同"两个条件，才判定为熟词僻义。

**识别流程**：
```
1. 从选项中提取单词
2. 在课本单词表中查找该词
3. 如找到 → 对比课本释义与当前语境含义
4. 如不同 → 判定为熟词僻义
```

**僻义类型**：

1. **词性转换**：book (预订), water (浇水), hand (传递), warm (加热)
2. **专业术语**：mouse (鼠标), web (网站), surf (上网), program (编程)
3. **比喻引申**：cold (冷淡), hot (热门/辣), green (环保的/没经验的)
4. **多义词引申**：tie (平局), head (朝…方向行驶), pad (发射台)

**典型示例**：

**多义词引申**：
- The game ended in a ___. (tie - 平局；课本释义是"领带/系")

**词性转换**：
- Please ___ a hotel room. (book - 预订；课本释义是名词"书")

**AI分析输出**：
```json
{
  "point_type": "熟词僻义",
  "correct_word": "tie",
  "textbook_meaning": "n. 领带；v. 系，绑",
  "textbook_source": "人教版八年级上册 Unit 5",
  "context_meaning": "n. 平局，不分胜负",
  "context_sentence": "The game ended in a ___ after overtime.",
  "explanation": "tie在课本中的常见含义是"领带"或"系、绑"，但在此句中作为体育术语，表示"平局"。这是中考完形填空常见的熟词僻义考点。",
  "similar_words": [
    {"word": "head", "textbook": "头", "rare": "朝…方向行驶"},
    {"word": "pad", "textbook": "垫子", "rare": "发射台"},
    {"word": "bank", "textbook": "银行", "rare": "河岸"},
    {"word": "fine", "textbook": "好的", "rare": "罚款"}
  ],
  "tips": "tie作为"平局"常出现在体育类话题文章中，注意结合语境判断"
}
```

### 3.5 考点判断流程

**AI按以下顺序判断**：
1. 首先检查是否为**固定搭配**（最明显的特征）
2. 其次检查是否为**熟词僻义**（基于课本单词表判断）
3. 最后判断为**词义辨析**（最常见的情况）

---

## 四、课本单词表管理

### 4.1 功能说明

课本单词表是**熟词僻义**识别的参照基准。系统已导入初一至初二的人教版、外研版课本单词表，用于判断某个词是否属于"熟词"。

### 4.2 已导入数据统计

| 出版社 | 年级 | 单词数 |
|--------|------|--------|
| 人教版 | 七年级上 | 352 |
| 人教版 | 七年级下 | 464 |
| 人教版 | 八年级上 | 592 |
| 人教版 | 八年级下 | 545 |
| 外研版 | 七年级上 | 274 |
| 外研版 | 七年级下 | 380 |
| 外研版 | 八年级上 | 264 |
| 外研版 | 八年级下 | 220 |
| **合计** | - | **3091** |

> **注意**：目前缺少九年级（初三）单词表，需要后续补充。

### 4.3 导入脚本

使用 `backend/scripts/import_textbook_vocab.py` 脚本进行导入：

```bash
# 步骤1: 从 Word 文档提取为 JSON（便于检查）
python3 scripts/import_textbook_vocab.py extract

# 步骤2: 从 JSON 导入数据库
python3 scripts/import_textbook_vocab.py import

# 或一步完成
python3 scripts/import_textbook_vocab.py all
```

生成的 JSON 文件位于：`backend/scripts/textbook_vocab.json`

### 4.4 与熟词僻义的关联

```
完形填空选项 "tie"
       ↓
在 textbook_vocab 表中查询 "tie"
       ↓
找到记录：{word: "tie", definition: "n. 领带；v. 系，绑", source: "人教版八上 Unit 5"}
       ↓
对比课本释义与当前语境含义
       ↓
不同 → 判定为"熟词僻义"，记录课本释义和语境释义
```

---

## 五、AI服务配置

### 5.1 考点分析 Prompt

```
你是中考英语完形填空教学专家。
请分析以下完形填空题目的考点类型。

空格编号：{blank_number}
正确答案：{correct_word}
选项：
A. {option_a}
B. {option_b}
C. {option_c}
D. {option_d}

原文语境：
{context_with_blank}

课本释义参照（仅用于熟词僻义判断）：
{textbook_definition}  // 如果单词在课本中存在，提供课本释义

**判断顺序**：
1. 首先判断是否为**固定搭配**（正确答案与某个词形成固定短语）
2. 其次判断是否为**熟词僻义**（课本有该词，但当前语境意思与课本不同）
3. 最后判断为**词义辨析**（选项之间有相似性，需根据语境区分）

请按以下格式返回JSON：

对于固定搭配：
{
  "point_type": "固定搭配",
  "phrase": "短语",
  "translation": "翻译",
  "explanation": "解释",
  "distractors": [...],
  "similar_phrases": [...],
  "tips": "记忆技巧"
}

对于词义辨析（必须包含三维度分析）：
{
  "point_type": "词义辨析",
  "correct_word": "正确词",
  "translation": "翻译",
  "dictionary_source": "柯林斯词典",
  "word_analysis": {
    "正确词": {
      "definition": "英英解释",
      "dimensions": {
        "使用对象": "...",
        "使用场景": "...",
        "正负态度": "..."
      }
    },
    "干扰词1": {
      "definition": "英英解释",
      "dimensions": {...},
      "rejection_reason": "排除理由"
    }
  },
  "distractors": [...],
  "tips": "记忆技巧"
}

对于熟词僻义（必须包含课本参照）：
{
  "point_type": "熟词僻义",
  "correct_word": "正确词",
  "textbook_meaning": "课本释义",
  "textbook_source": "人教版八上 Unit 5",
  "context_meaning": "当前语境释义",
  "explanation": "解释",
  "similar_words": [...],
  "tips": "提示"
}

```

### 5.2 话题分类 Prompt

```
你是北京中考英语教学专家。
请分析以下完形填空文章的话题。

文章内容：
{content_full}

**分析步骤**：
1. 先从话题词库中匹配关键词
2. 如果话题词没有匹配到，深入分析文章主题
3. 选择最贴切的一个话题（只需一个，不需要次要话题）

**统一话题池**（不按年级区分）：
- 校园生活、家庭亲情、兴趣爱好、节日习俗、动物自然、梦想成长、助人为乐、健康饮食
- 个人成长、科技生活、文化交流、环境保护、运动健康、艺术创造、社会现象、友谊合作
- 人生哲理、科技伦理、跨文化理解、全球问题、职业规划、心理健康、社会责任、传统文化、创新思维、教育发展
- 志愿服务、邻里关系、诚实守信、勇气挑战、感恩回馈、时间管理、安全意识、阅读习惯
- 师生关系、环境保护、社区参与、文化传承、体育精神、科学探索、生活技能、情绪管理
- 注意：如果以上话题都不匹配，可以根据文章内容补充新的细粒度话题

请返回JSON：
{
  "primary_topic": "唯一话题",
  "confidence": 0.95,
  "keywords": ["关键词1", "关键词2"],
  "reasoning": "选择理由"
}
```

---

## 六、API接口文档

### 6.1 完形文章列表

```http
GET /api/cloze/
```

**请求参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| grade | string | 年级筛选（初一/初二/初三） |
| topic | string | 话题筛选 |
| point_type | string | 考点类型筛选 |
| region | string | 区县筛选 |
| year | int | 年份筛选 |
| page | int | 页码 |
| page_size | int | 每页数量 |

**响应示例**：
```json
{
  "items": [
    {
      "id": 1,
      "paper": {
        "year": 2022,
        "region": "东城",
        "grade": "初三",
        "exam_type": "期末"
      },
      "word_count": 280,
      "blank_count": 12,
      "primary_topic": "个人成长",
      "point_distribution": {
        "固定搭配": 4,
        "词义辨析": 5,
        "词汇": 2,
        "熟词僻义": 1
      }
    }
  ],
  "total": 156,
  "page": 1,
  "page_size": 20
}
```

### 6.2 完形文章详情

```http
GET /api/cloze/{passage_id}
```

**响应示例**：
```json
{
  "id": 1,
  "content_with_blanks": "I have always ① reading...",
  "content_full": "I have always enjoyed reading...",
  "word_count": 280,
  "primary_topic": "个人成长",
  "topic_verified": false,
  "paper": {
    "year": 2022,
    "region": "东城",
    "grade": "初三",
    "semester": "上",
    "exam_type": "期末",
    "original_file": "2022北京东城初三（上）期末英语（教师版）.docx"
  },
  "blanks": [
    {
      "id": 1,
      "blank_number": 1,
      "char_position": 18,
      "options": {
        "A": "bought",
        "B": "borrowed",
        "C": "read",
        "D": "wrote"
      },
      "correct_answer": "A",
      "correct_word": "bought",
      "point_type": "词义辨析",
      "point_analysis": {...},
      "point_verified": false
    }
  ]
}
```

### 6.3 考点汇总查询

```http
GET /api/cloze-points/
```

**请求参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| point_type | string | 考点类型（固定搭配/词义辨析/熟词僻义） |
| grade | string | 年级筛选 |
| keyword | string | 关键词搜索 |

**响应示例**：
```json
{
  "items": [
    {
      "word": "look up",
      "definition": "查阅，查找",
      "frequency": 8,
      "occurrences": [
        {
          "sentence": "You can look up new words in the dictionary.",
          "source": "2022东城初三期末·完形",
          "analysis": {
            "explanation": "look up 表示查阅词典",
            "distractors": [...]
          }
        }
      ]
    }
  ],
  "total": 45
}
```

### 6.4 更新话题（人工校对）

```http
PUT /api/cloze/{id}/topic
```

**请求体**：
```json
{
  "primary_topic": "个人成长",
  "verified": true
}
```

### 6.5 完形高频词汇查询

```http
GET /api/cloze-vocabulary/
```

**请求参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| grade | string | 年级筛选（初一/初二/初三） |
| topic | string | 话题筛选 |
| min_frequency | int | 最低词频筛选 |
| keyword | string | 关键词搜索 |
| page | int | 页码 |
| page_size | int | 每页数量 |

**响应示例**：
```json
{
  "items": [
    {
      "id": 1,
      "word": "achieve",
      "lemma": "achieve",
      "definition": "v. 实现，达成",
      "frequency": 15,
      "occurrences": [
        {
          "sentence": "He worked hard to achieve his dream.",
          "source": "2022东城初三期末·完形",
          "char_position": 45
        }
      ]
    }
  ],
  "total": 89,
  "page": 1,
  "page_size": 20
}
```

### 6.6 更新考点分析（人工校对）

```http
PUT /api/cloze/blanks/{blank_id}/point
```

**请求体**：
```json
{
  "point_type": "固定搭配",
  "point_analysis": {
    "phrase": "look up",
    "translation": "查阅",
    "explanation": "..."
  },
  "verified": true
}
```

---

## 七、前端交互

### 7.1 完形文章详情页交互

**左右分栏布局**：
- 左侧：带空格标记的文章内容
- 右侧：考点分析列表

**交互行为**：

| 操作 | 效果 |
|------|------|
| 点击右侧考点 | 左侧原文滚动到对应空格位置，空格高亮 |
| 点击左侧空格 | 右侧滚动到对应考点，考点高亮 |
| 悬停空格 | 显示正确答案和考点类型 |
| 点击出处链接 | 跳转到原始试卷页面 |

### 7.2 考点汇总页交互

**筛选功能**：
- 考点类型下拉（固定搭配/词义辨析/熟词僻义）
- 年级筛选
- 关键词搜索

**展示内容**：
- 考点词/短语
- 释义
- 出现次数
- 例句列表（含出处链接）
- 易混淆词

---

## 八、使用示例

### 8.1 查看固定搭配考点

```
1. 进入「考点汇总」页面
2. 选择考点类型：「固定搭配」
3. 选择年级：「初三」
4. 查看结果：
   - look up (8次)
   - take off (6次)
   - depend on (5次)
   ...
5. 点击「look up」查看详情：
   - 释义、例句、出处
   - 易混淆词分析
   - 记忆技巧
6. 点击例句出处，跳转到原文
```

### 8.2 备课特定话题完形

```
1. 进入「完形文章」页面
2. 筛选：初三 + 个人成长
3. 查看文章列表，了解考点分布
4. 点击某篇文章查看详情
5. 左右分栏查看文章和考点
6. 点击考点定位到原文
7. 导出为Word文档
```

### 8.3 查看完形高频词汇

```
1. 进入「完形词库」页面
2. 筛选：初三 + 个人成长话题
3. 按词频排序查看结果
4. 点击词汇查看例句和出处
5. 点击出处链接跳转到原文位置
6. 了解该话题下的核心词汇分布
```

---

## 九、数据模型

### 9.1 核心表结构

**cloze_passages（完形文章表）**：
```sql
CREATE TABLE cloze_passages (
    id INTEGER PRIMARY KEY,
    paper_id INTEGER,              -- 关联试卷
    content_with_blanks TEXT,      -- 带空格原文
    content_full TEXT,             -- 完整文章
    word_count INTEGER,            -- 词数
    primary_topic VARCHAR(100),    -- 话题
    topic_confidence FLOAT,        -- 分类置信度
    topic_verified BOOLEAN         -- 是否人工校对
);
```

**cloze_blanks（空格表）**：
```sql
CREATE TABLE cloze_blanks (
    id INTEGER PRIMARY KEY,
    passage_id INTEGER,            -- 关联文章
    blank_number INTEGER,          -- 空格编号(1-12)
    char_position INTEGER,         -- 字符位置
    option_a VARCHAR(255),         -- 选项A
    option_b VARCHAR(255),         -- 选项B
    option_c VARCHAR(255),         -- 选项C
    option_d VARCHAR(255),         -- 选项D
    correct_answer VARCHAR(1),     -- 正确答案(A/B/C/D)
    correct_word VARCHAR(255),     -- 正确词
    point_type VARCHAR(50),        -- 考点类型
    point_analysis TEXT,           -- 考点解析(JSON)
    point_verified BOOLEAN         -- 是否人工校对
);
```

**vocab_cloze（完形考点词关联表）**：
```sql
CREATE TABLE vocab_cloze (
    id INTEGER PRIMARY KEY,
    word_id INTEGER,               -- 关联基础词库
    blank_id INTEGER,              -- 关联空格
    point_type VARCHAR(50),        -- 考点类型
    analysis TEXT,                 -- 考点解析(JSON)
    distractors TEXT,              -- 易混淆词(JSON)
    sentence TEXT                  -- 原句
);
```

### 9.2 与阅读模块的关系

```
words (基础词库，共享)
  │
  ├── vocab_reading (阅读高频词关联)
  │
  ├── vocab_cloze (完形考点关联)
  │
  └── vocab_cloze_passage (完形高频词关联)  ← 新增，与阅读逻辑一致
```

**vocab_cloze_passage（完形高频词关联表）**：
```sql
CREATE TABLE vocab_cloze_passage (
    id INTEGER PRIMARY KEY,
    word_id INTEGER,               -- 关联基础词库
    passage_id INTEGER,            -- 关联完形文章
    sentence TEXT,                 -- 包含该词的原句
    char_position INTEGER,         -- 字符起始位置
    end_position INTEGER,          -- 字符结束位置
    word_position INTEGER,         -- 词序位置
    FOREIGN KEY (word_id) REFERENCES words(id),
    FOREIGN KEY (passage_id) REFERENCES cloze_passages(id)
);
```

**词频统计示例**：
```sql
-- 完形高频词统计（按话题）
SELECT
    w.word,
    w.definition,
    COUNT(*) as frequency
FROM words w
JOIN vocab_cloze_passage vcp ON w.id = vcp.word_id
JOIN cloze_passages cp ON vcp.passage_id = cp.id
WHERE cp.primary_topic = '个人成长'
GROUP BY w.id
ORDER BY frequency DESC;
```

### 9.3 课本单词表

**textbook_vocab（课本单词表）**：
```sql
CREATE TABLE textbook_vocab (
    id INTEGER PRIMARY KEY,
    word VARCHAR(255) NOT NULL,        -- 单词
    pos VARCHAR(100),                  -- 词性（可为空）
    definition TEXT NOT NULL,          -- 中文释义
    publisher VARCHAR(50) NOT NULL,    -- 出版社（人教版/外研版）
    grade VARCHAR(20) NOT NULL,        -- 年级（七年级/八年级/九年级）
    semester VARCHAR(10) NOT NULL,     -- 学期（上/下）
    unit VARCHAR(50),                  -- 单元（如 Unit 1, Module 4）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引加速查询
CREATE INDEX idx_textbook_vocab_word ON textbook_vocab(word);
CREATE INDEX idx_textbook_vocab_publisher_grade ON textbook_vocab(publisher, grade);
```

**数据示例**：
```sql
INSERT INTO textbook_vocab (word, pos, definition, publisher, grade, semester, unit) VALUES
('tie', 'n./v.', '领带；系，绑', '人教版', '八年级', '上', 'Unit 5'),
('tie', 'n./v.', '领带；系', '外研版', '八年级', '下', 'Module 4'),
('head', 'n.', '头', '人教版', '七年级', '上', 'Unit 3');
```

**与熟词僻义的关联查询**：
```sql
-- 查询单词是否在课本中，并获取课本释义
SELECT word, definition, publisher, grade, semester, unit
FROM textbook_vocab
WHERE word = 'tie';

-- 结果用于熟词僻义判断：
-- 如果查询到记录，说明是"熟词"
-- 如果当前语境含义与 definition 不同，则为"僻义"
```

---

## 十、注意事项

1. **空格识别**： 支持多种编号格式，可能需要人工确认
2. **考点分类**： AI分类结果建议人工校对
3. **话题独立**： 完形话题池与阅读独立，但分析逻辑一致
4. **性能考虑**： 批量导入时注意控制并发数

---

**文档版本**: v1.1
**最后更新**: 2026-03-14

## 更新日志

### v1.1 (2026-03-14)
- **词义辨析**：明确三维度分析法（使用对象、使用场景、正负态度），指定柯林斯词典为英英解释来源
- **熟词僻义**：新增课本参照判断逻辑，基于课本单词表判定"熟词"和"僻义"
- **新增章节**：第四章 课本单词表管理
- **数据模型**：新增 textbook_vocab 表结构
- **AI Prompt**：更新考点分析 Prompt，加入三维度分析和课本参照要求
