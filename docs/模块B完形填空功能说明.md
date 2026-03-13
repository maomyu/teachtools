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
| **固定搭配** | 动词短语、介词搭配 | 短语动词，依赖语境搭配 |
| **词义辨析** | 同义/近义词细微区别 | 四个词含义相近，语境决定 |
| **熟词僻义** | 常见词的非常规含义 | 常见词，非常规用法 |

### 3.2 固定搭配考点

**识别特征**：
- 正确答案是短语动词（如 look up, take off）
- 或介词搭配（如 depend on, interested in）

**AI分析输出**：
```json
{
  "point_type": "固定搭配",
  "phrase": "look up",
  "translation": "查阅，查找",
  "context_sentence": "You can ___ new words in the dictionary.",
  "explanation": "look up 表示"查阅词典"，look up + 名词 + in + 参考书",
  "distractors": [
    {"option": "B", "word": "look for", "reason": "寻找，不搭配dictionary"},
    {"option": "C", "word": "look at", "reason": "看，不符合语境"},
    {"option": "D", "word": "look after", "reason": "照顾，语义不符"}
  ],
  "similar_phrases": ["look up to", "look through", "look into"],
  "tips": "记忆技巧：look up 向上看→向上找→查阅"
}
```

### 3.3 词义辨析考点

**识别特征**：
- 四个选项含义相近（如 say/tell/speak/talk）
- 需要根据语境和搭配区分

**AI分析输出**：
```json
{
  "point_type": "词义辨析",
  "correct_word": "achieve",
  "translation": "v. 实现，达成",
  "context_sentence": "He worked hard to ___ his dream.",
  "explanation": "achieve强调通过努力达成目标，常搭配dream/goal/success",
  "word_comparison": {
    "achieve": "强调努力后达成目标，+ 抽象名词(dream/goal/success)",
    "succeed": "强调成功的结果，+ in doing sth",
    "manage": "强调设法做成某事，+ to do sth",
    "accomplish": "正式用语，表示完成某项任务"
  },
  "distractors": [
    {"option": "B", "word": "succeeded", "reason": "需搭配in achieving"},
    {"option": "C", "word": "managed", "reason": "语义不如achieve贴切"},
    {"option": "D", "word": "completed", "reason": "不搭配dream"}
  ]
}
```

### 3.3 熟词僻义考点

**识别逻辑**：
1. **词库检索**：在已有词库中检索该词的常见含义
2. **语境对比**：发现该词在当前语境下的含义与词库中的常见含义不同
3. **判定为熟词僻义**：该词使用了非常规含义

**典型示例**：
- book（常见义：书 → 僻义：预订）
- bank（常见义：银行 → 僻义：河岸）
- fine（常见义：好的 → 僻义：罚款）

**AI分析输出**：
```json
{
  "point_type": "熟词僻义",
  "correct_word": "book",
  "common_meaning": "n. 书",
  "rare_meaning": "v. 预订",
  "context_sentence": "You'd better ___ a room in advance.",
  "explanation": "book作为动词表示"预订"，是中考常见熟词僻义",
  "similar_words": [
    {"word": "bank", "common": "银行", "rare": "河岸"},
    {"word": "fine", "common": "好的", "rare": "罚款"},
    {"word": "match", "common": "比赛", "rare": "匹配"},
    {"word": "plant", "common": "植物", "rare": "工厂"}
  ],
  "tips": "注意词性变化：名词→动词"
}
```

---

## 四、AI服务配置

### 4.1 考点分析 Prompt

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

对于词义辨析：
{
  "point_type": "词义辨析",
  "correct_word": "正确词",
  "translation": "翻译",
  "explanation": "解释",
  "word_comparison": {...},
  "distractors": [...]
}

对于熟词僻义：
{
  "point_type": "熟词僻义",
  "correct_word": "正确词",
  "common_meaning": "常见义",
  "rare_meaning": "僻义",
  "explanation": "解释",
  "similar_words": [...],
  "tips": "提示"
}

```

### 4.2 话题分类 Prompt

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

## 五、API接口文档

### 5.1 完形文章列表

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

### 5.2 完形文章详情

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

### 5.3 考点汇总查询

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

### 5.4 更新话题（人工校对）

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

### 5.5 完形高频词汇查询

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

### 5.6 更新考点分析（人工校对）

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

## 六、前端交互

### 6.1 完形文章详情页交互

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

### 6.2 考点汇总页交互

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

## 七、使用示例

### 7.1 查看固定搭配考点

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

### 7.2 备课特定话题完形

```
1. 进入「完形文章」页面
2. 筛选：初三 + 个人成长
3. 查看文章列表，了解考点分布
4. 点击某篇文章查看详情
5. 左右分栏查看文章和考点
6. 点击考点定位到原文
7. 导出为Word文档
```

### 7.3 查看完形高频词汇

```
1. 进入「完形词库」页面
2. 筛选：初三 + 个人成长话题
3. 按词频排序查看结果
4. 点击词汇查看例句和出处
5. 点击出处链接跳转到原文位置
6. 了解该话题下的核心词汇分布
```

---

## 八、数据模型

### 8.1 核心表结构

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

### 8.2 与阅读模块的关系

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

---

## 九、注意事项

1. **空格识别**： 支持多种编号格式，可能需要人工确认
2. **考点分类**： AI分类结果建议人工校对
3. **话题独立**： 完形话题池与阅读独立，但分析逻辑一致
4. **性能考虑**： 批量导入时注意控制并发数

---

**文档版本**: v1.0
**最后更新**: 2025-03-07
