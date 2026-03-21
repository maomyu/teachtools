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
        生成作文模板（方法论驱动版 v3）

        Args:
            writing_type: 文体类型（应用文/记叙文）
            application_type: 应用文子类型（书信/通知/邀请等）

        Returns:
            模板内容（包含句型库、词汇表等）
        """
        application_hint = f"\n应用文子类型：{application_type}" if application_type else ""

        prompt = f"""你是北京中考英语写作教学专家。请为以下文体生成专业模板。

## 文体类型
文体：{writing_type}{application_hint}

## 北京中考作文评分标准（必须掌握）

### 一档文（13-15分）特征
1. **内容**：涵盖所有要点，有适当拓展
2. **语言**：词汇丰富、句式多样、基本无语法错误
3. **结构**：段落分明、过渡自然、逻辑清晰
4. **亮点**：至少3处高级表达（词汇或句型）

### 模板设计方法论

#### 应用文（书信/邮件）结构模式
```
第一段（开头，15-25词）：
  - 称呼（Dear...）
  - 写信目的（1句话点明）
  - 常用句式：I am writing to [动词短语]

第二段（主体，40-60词）：
  - 用连接词组织2-3个要点
  - 每个要点：理由/建议/细节
  - 常用句式：
    • First of all, [要点1]. Besides, [要点2]. Finally, [要点3].
    • On one hand, [要点1]. On the other hand, [要点2].

第三段（结尾，15-25词）：
  - 总结/期待/感谢
  - 常用句式：
    • I hope [期待]. Looking forward to [动词-ing].
    • I would appreciate it if [请求].
  - 落款（Yours sincerely, Li Hua）
```

#### 记叙文结构模式
```
第一段（开头，20-30词）：
  - 交代背景：时间、地点、事件
  - 常用句式：Last [时间], I [动词过去式]...

第二段（主体，50-70词）：
  - 按时间顺序展开
  - 细节描写 + 人物感受
  - 常用句式：
    • First, [动作]. Then, [动作]. Finally, [动作].
    • What impressed me most was [名词/从句].

第三段（结尾，15-25词）：
  - 总结感受/收获
  - 常用句式：
    • This experience taught me that [从句].
    • It was really a [形容词] day/experience.
```

## 句型生成规则

### 开头句型构造模式（必须按场景分类）

**模式1：申请类**
- 构造公式：[申请动作] + [职位/机会]
- 高分句式：
  • I am writing to apply for [职位].
  • I would like to express my interest in [机会].
  • I am writing to express my desire to [动词短语].

**模式2：建议类**
- 构造公式：[建议动作] + [建议对象]
- 高分句式：
  • I am writing to offer some suggestions on [主题].
  • After careful consideration, I would like to propose [建议].
  • I would like to share my views on [主题].

**模式3：邀请类**
- 构造公式：[邀请动作] + [活动]
- 高分句式：
  • On behalf of [组织], I sincerely invite you to [活动].
  • It is my honor to invite you to participate in [活动].
  • We would be delighted if you could [动词短语].

**模式4：感谢类**
- 构造公式：[感谢程度] + [感谢原因]
- 高分句式：
  • I am writing to express my sincere gratitude for [原因].
  • Words cannot express how grateful I am for [原因].
  • I would like to thank you from the bottom of my heart for [原因].

**模式5：道歉类**
- 构造公式：[道歉动作] + [道歉原因]
- 高分句式：
  • I am writing to apologize for [原因].
  • Please accept my sincere apology for [原因].
  • I am terribly sorry for [原因].

### 结尾句型构造模式（按场景分类）

**申请类结尾**：
- I would appreciate it if you could give me this opportunity.
- I am looking forward to your favorable reply.

**建议类结尾**：
- I hope my suggestions will be taken into consideration.
- I believe these changes will make a difference.

**邀请类结尾**：
- We would be honored by your presence.
- Your participation would mean a lot to us.

**感谢类结尾**：
- Thank you again for your kindness.
- I will always remember your help.

**道歉类结尾**：
- I hope you can forgive me.
- I promise this will not happen again.

### 过渡词汇分类（按功能）

**递进关系**：Besides, / What's more, / Furthermore, / In addition, / Moreover,
**转折关系**：However, / On the other hand, / Nevertheless, / Instead,
**因果关系**：Therefore, / As a result, / Consequently, / Thus,
**顺序关系**：First of all, / Then, / Finally, / In the end,
**总结关系**：In conclusion, / To sum up, / All in all, / In short,

### 高级词汇替换方法论

**替换原则**：
1. 基础词太泛，需要具体化
2. 高级词要符合语境，不能生搬硬套
3. 每个替换词要给出使用场景

| 基础词 | 高级替换 | 使用场景 |
|--------|----------|----------|
| good | excellent/outstanding | 形容人或事物的优秀品质 |
| good | beneficial | 形容某事的好处 |
| help | assist | 正式场合的帮助 |
| help | support | 支持某人 |
| think | believe | 表达观点 |
| think | consider | 考虑某事 |
| want | desire | 强烈愿望 |
| want | hope to | 希望做某事 |
| use | utilize | 正式场合的使用 |
| use | apply | 应用方法/技能 |
| important | significant | 重要的意义 |
| important | vital | 至关重要 |
| very | extremely | 程度非常高 |
| very | highly | 高度（配合形容词） |
| get | obtain | 获得（正式） |
| get | gain | 获得（收益/经验） |
| make | create | 创造 |
| make | produce | 产生 |
| know | understand | 理解 |
| know | realize | 意识到 |

### 语法要点（按文体分类）

**应用文语法重点**：
1. **情态动词表达礼貌**：
   - should/could/would + 动词原形
   - I would appreciate it if you could...
2. **被动语态增加正式感**：
   - Your application will be considered.
3. **条件句表达请求**：
   - If possible, I would like to...

**记叙文语法重点**：
1. **过去时态的正确使用**：
   - 一般过去时：描述发生的动作
   - 过去进行时：描述背景（was/were doing）
2. **时间顺序词**：
   - First, Then, Finally / Before, After, When
3. **感受表达**：
   - I felt + 形容词
   - It made me + 形容词
   - I was + 形容词 + to do

## 输出格式（JSON）

```json
{{
    "template_name": "应用文-建议信模板",
    "template_content": "Dear [Recipient],\\n\\nI am writing to [purpose].\\n\\n[Body: First, [point1]. Besides, [point2]. Finally, [point3].]\\n\\nI hope [closing]. Looking forward to your reply.\\n\\nYours sincerely,\\n[Your name]",
    "structure": "共三段：\\n第一段（开头）：说明写信目的（约20词）\\n第二段（主体）：展开建议/理由（约50词）\\n第三段（结尾）：总结并期待回复（约20词）",
    "tips": "1. 开头明确说明目的\\n2. 用 First, Besides, Finally 组织理由\\n3. 结尾表达期待",
    "opening_sentences": ["I am writing to offer some suggestions on [topic].", "After careful consideration, I would like to propose [suggestion]."],
    "closing_sentences": ["I hope my suggestions will be helpful.", "I believe these changes will benefit everyone."],
    "transition_words": ["First of all,", "Besides,", "What's more,", "In conclusion,"],
    "advanced_vocabulary": [{{"word": "suggest", "basic": "say", "usage": "正式场合提出建议"}}, {{"word": "consider", "basic": "think", "usage": "表达经过思考的观点"}}],
    "grammar_points": ["使用情态动词should/could表达建议", "使用First/Besides组织段落"],
    "scoring_criteria": {{"content": "涵盖所有要点", "language": "语法正确，词汇丰富", "structure": "段落分明"}}
}}
```

请直接输出 JSON，不要有其他解释。"""

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
                    result = json.loads(json_match.group())
                    # 将数组字段转为 JSON 字符串存储
                    for key in ['opening_sentences', 'closing_sentences', 'transition_words',
                                'advanced_vocabulary', 'grammar_points', 'scoring_criteria']:
                        if key in result and isinstance(result[key], (list, dict)):
                            result[key] = json.dumps(result[key], ensure_ascii=False)
                    return result
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
