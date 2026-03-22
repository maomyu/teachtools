"""
AI 答案识别服务

使用 qwen-long 模型识别需要删除的答案和解析内容
"""
import json
import httpx
from typing import List, Dict, Optional
from dataclasses import dataclass

from app.config import settings


@dataclass
class ItemToRemove:
    """需要删除的内容项"""
    type: str  # answer, analysis, sample_answer, answer_key
    content_pattern: str  # 用于匹配的内容
    match_type: str = "contains"  # exact, starts_with, contains
    remove_following_until: Optional[str] = None  # 删除直到遇到这个标记


@dataclass
class RemoveResult:
    """识别结果"""
    success: bool
    items_to_remove: List[ItemToRemove]
    raw_content: str = ""
    error: str = ""


class AnswerDetector:
    """AI 答案识别服务 - 识别需要删除的内容"""

    API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    IDENTIFY_REMOVE_CONTENT_PROMPT = """你是一个专业的英语试卷编辑。请分析教师版试卷，识别所有需要删除的答案和解析内容。

## 任务

找出文档中所有需要删除的段落，返回它们的内容特征。这些内容将被删除以生成学生版试卷。

## 需要删除的内容类型

### 1. 答案行
**格式示例**：
- `答案：A` / `Answer: B` / `【答案】C`
- `1. A  2. B  3. C` （答案汇总）
- `(答案) A` / `(正确答案) B`

**特征**：单独一行，包含正确选项标识

### 2. 解析段落
**格式示例**：
- `【解析】本题考查...`
- `解析：根据文章...`
- `【分析】这道题...`
- `【点拨】/ 【思路点拨】/ 【易错点】`

**特征**：以解析标记开头，解释为什么选某个答案

### 3. 范文段落
**起始标记**：
- `One possible version:`
- `参考范文：` / `范文：`
- `Sample answer:`

**特征**：从标记开始到下一大题结束的所有内容

### 4. 答案汇总表
**格式示例**：
- `答案速查表`
- `答题卡参考答案`
- `参考答案：1-5 ABCDE`

---

## 不需要删除的内容

- 题目本身（题干）
- 选项（A/B/C/D，不带答案标记）
- 文章原文
- 图片（无法识别，自动保留）
- 注意事项、考试说明

---

## 输出格式

请按以下 JSON 格式输出：

```json
{
    "success": true,
    "items_to_remove": [
        {
            "type": "answer",
            "content_pattern": "答案：A",
            "match_type": "contains"
        },
        {
            "type": "answer",
            "content_pattern": "【答案】",
            "match_type": "contains"
        },
        {
            "type": "analysis",
            "content_pattern": "【解析】",
            "match_type": "starts_with"
        },
        {
            "type": "analysis",
            "content_pattern": "解析：",
            "match_type": "starts_with"
        },
        {
            "type": "sample_answer",
            "content_pattern": "One possible version:",
            "match_type": "starts_with",
            "remove_following_until": "next_section"
        },
        {
            "type": "sample_answer",
            "content_pattern": "参考范文：",
            "match_type": "starts_with",
            "remove_following_until": "next_section"
        },
        {
            "type": "answer_key",
            "content_pattern": "答案速查表",
            "match_type": "contains"
        }
    ]
}
```

### match_type 说明
- `exact`: 段落内容完全等于 content_pattern
- `starts_with`: 段落以 content_pattern 开头
- `contains`: 段落包含 content_pattern

### remove_following_until 说明
- `next_section`: 删除从匹配行开始，直到遇到下一个大题标题（如"完形填空"、"阅读理解"、"书面表达"）
- 留空: 只删除匹配的那一行

---

## 重要原则

1. **宁可漏删，不要误删** - 不确定的内容不要标记
2. **保留题目和选项** - 学生需要看到题目
3. **图片无法识别** - 图片会自动保留
4. 只返回确定是答案/解析/范文的内容

请严格按照上述 JSON 格式输出，不要添加任何其他文字。"""

    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY未配置")

    async def identify_content_to_remove(self, fileid: str) -> RemoveResult:
        """
        使用 qwen-long 识别需要删除的内容

        Args:
            fileid: DashScope 文件 ID

        Returns:
            RemoveResult: 识别结果
        """
        messages = [
            {"role": "system", "content": "You are a professional English exam paper editor. Your task is to identify content that should be removed (answers, explanations, sample answers) from teacher version papers."},
            {"role": "system", "content": f"fileid://{fileid}"},
            {"role": "user", "content": self.IDENTIFY_REMOVE_CONTENT_PROMPT}
        ]

        async with httpx.AsyncClient(timeout=180.0) as client:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }

            payload = {
                "model": "qwen-long",
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 8000
            }

            response = await client.post(
                self.API_URL,
                headers=headers,
                json=payload
            )

            if response.status_code != 200:
                return RemoveResult(
                    success=False,
                    items_to_remove=[],
                    error=f"AI识别失败: {response.status_code} - {response.text}"
                )

            result = response.json()
            content = result['choices'][0]['message']['content']

            return self._parse_response(content)

    def _parse_response(self, content: str) -> RemoveResult:
        """解析 AI 响应"""
        try:
            # 提取 JSON 部分
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

            if not data.get('success', False):
                return RemoveResult(
                    success=False,
                    items_to_remove=[],
                    error="AI 返回失败状态",
                    raw_content=content
                )

            # 解析 items_to_remove
            items = []
            for item in data.get('items_to_remove', []):
                items.append(ItemToRemove(
                    type=item.get('type', 'answer'),
                    content_pattern=item.get('content_pattern', ''),
                    match_type=item.get('match_type', 'contains'),
                    remove_following_until=item.get('remove_following_until')
                ))

            print(f"[AnswerDetector] 识别到 {len(items)} 个需要删除的内容模式")
            for item in items:
                print(f"  - [{item.match_type}] '{item.content_pattern}' ({item.type})")

            return RemoveResult(
                success=True,
                items_to_remove=items,
                raw_content=content
            )

        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            print(f"原始内容: {content[:500]}")
            return RemoveResult(
                success=False,
                items_to_remove=[],
                error=f"JSON解析失败: {str(e)}",
                raw_content=content
            )

    # 保留旧方法以兼容
    async def extract_student_version(self, fileid: str):
        """兼容旧接口"""
        return await self.identify_content_to_remove(fileid)
