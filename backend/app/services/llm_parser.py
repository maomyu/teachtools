"""
基于LLM的文档解析服务

使用通义千问qwen-long模型进行文档理解
"""
import os
import json
import httpx
from typing import Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path

from app.config import settings


@dataclass
class LLMParseResult:
    """LLM解析结果"""
    success: bool
    passages: List[Dict] = None  # [{"type": "C", "content": "...", "word_count": 300}, ...]
    cloze: Dict = None  # {"found": True, "content_with_blanks": "...", "blanks": [...]}
    metadata: Dict = None  # {"year": 2022, "region": "东城", ...}
    error: str = None
    raw_response: str = None


@dataclass
class WritingExtractResult:
    """作文提取结果"""
    success: bool
    content: str = ""                  # 作文题目完整内容
    requirements: str = ""             # 具体要求
    word_limit: str = ""               # 字数限制
    writing_type: str = "其他"         # 应用文/记叙文/其他
    application_type: str = ""         # 应用文子类型
    error: str = ""
    raw_response: str = ""


class LLMDocumentParser:
    """基于LLM的文档解析器"""

    API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    UPLOAD_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/files"

    # 文档理解Prompt
    EXTRACT_PROMPT = """你是一个英语试卷解析专家。请分析这份英语试卷文档，提取以下信息：

## 需要提取的信息

### 1. 试卷元数据
从文件名和文档内容中提取：
- year: 年份（如2022）
- region: 区县（如东城、西城、海淀等）
- grade: 年级（初一/初二/初三）
- semester: 学期（上/下）
- exam_type: 考试类型（期中/期末/一模/二模）
- version: 版本（教师版/学生版）

### 2. 阅读理解C篇和D篇
提取阅读理解部分的C篇和D篇，每篇包含：
- passage_type: "C" 或 "D"
- content: 文章完整正文（不要包含题目）
- word_count: 词数（英文单词数）
- questions: 该文章对应的题目列表

### 3. 题目提取
对于每篇文章，提取对应的阅读理解题目：
- question_number: 题号（如31、32、33等）
- question_text: 题目内容（题干）
- options: 选项对象，格式为 {"A": "选项A内容", "B": "选项B内容", ...}
  - 注意：有些题目只有3个选项（A/B/C），这是正常的
  - 必须提取文档中存在的所有选项，确保至少有一个非空选项
  - 如果某个选项不存在，不要包含在options中或设为空字符串
  - **图片选项**：如果选项内容是图片（无法提取文字），填写 "[IMAGE]" 占位符
  - **绝对不要**把思维导图、流程图、示意图、表格图等图片型选项留空，必须填写 "[IMAGE]"
- has_image_options: 布尔值，表示该题目是否有图片选项（true/false）
- expected_image_count: 整数，预期图片选项的数量（0-4）
- correct_answer: 正确答案（A/B/C/D，如果是教师版能找到答案的话）
- answer_explanation: 答案解析（如果是教师版能找到解析的话）

**重要**：
- 普通文本选项：options 必须至少包含一个有效的选项内容，不能全部为空
- 图片选项：如果选项是图片，填写 "[IMAGE]" 占位符，并设置 has_image_options=true
- 混合选项：部分文本、部分图片的情况也要正确标记
- 如果无法识别图片内容，也不要输出空字符串，统一输出 "[IMAGE]"
- 如果是教师版，且原题已经给出了答案或解析，必须优先提取原题答案/原题解析，不要改写成你自己的版本
- 如果是开放题且教师版给出了示例答案，也要优先保留原题示例答案
- 只有在教师版明确没有答案/解析时，才允许补充简短的“参考答案”或“参考解析”

### 4. 完形填空
提取完形填空部分（如果存在）：
- found: 是否找到完形填空（true/false）
- content_with_blanks: 带空格标记的原文（保留空格编号如①②③或(1)(2)(3)）
- content_full: 填入正确答案后的完整文章（如果教师版有答案）
- word_count: 词数（完整文章的英文单词数）
- blanks: 空格列表，每个空格包含：
  - blank_number: 空格编号（1-12）
  - options: 四个选项 {"A": "...", "B": "...", "C": "...", "D": "..."}
  - correct_answer: 正确答案（A/B/C/D，如果教师版有）
  - correct_word: 正确答案对应的词

## 注意事项
- 如果是教师版试卷，注意区分题目、学生版内容和答案解析
- 教师版中的原题答案、示例答案、解答内容优先级最高，优先保留原文信息
- 题目通常紧跟在文章后面，题号一般是连续的
- 确保选项内容完整，不要截断
- 如果找不到答案或解析，对应字段可以省略
- 完形填空通常在阅读理解之前，一般有12个空格

## 输出格式

请严格按照以下JSON格式输出，不要添加任何其他文字：

```json
{
    "metadata": {
        "year": 2022,
        "region": "东城",
        "grade": "初二",
        "semester": "下",
        "exam_type": "期末",
        "version": "教师版"
    },
    "passages": [
        {
            "passage_type": "C",
            "content": "完整文章正文内容...",
            "word_count": 350,
            "questions": [
                {
                    "question_number": 31,
                    "question_text": "题目内容...",
                    "options": {
                        "A": "选项A内容",
                        "B": "选项B内容",
                        "C": "选项C内容",
                        "D": "选项D内容"
                    },
                    "has_image_options": false,
                    "expected_image_count": 0,
                    "correct_answer": "A",
                    "answer_explanation": "答案解析内容..."
                },
                {
                    "question_number": 32,
                    "question_text": "这道题的选项是图片...",
                    "options": {
                        "A": "[IMAGE]",
                        "B": "[IMAGE]",
                        "C": "[IMAGE]",
                        "D": "[IMAGE]"
                    },
                    "has_image_options": true,
                    "expected_image_count": 4,
                    "correct_answer": "B",
                    "answer_explanation": "答案解析内容..."
                }
            ]
        },
        {
            "passage_type": "D",
            "content": "完整文章正文内容...",
            "word_count": 400,
            "questions": [
                {
                    "question_number": 36,
                    "question_text": "题目内容...",
                    "options": {
                        "A": "选项A内容",
                        "B": "选项B内容",
                        "C": "选项C内容",
                        "D": "选项D内容"
                    },
                    "has_image_options": false,
                    "expected_image_count": 0,
                    "correct_answer": "B",
                    "answer_explanation": "答案解析内容..."
                }
            ]
        }
    ],
    "cloze": {
        "found": true,
        "content_with_blanks": "I have always ① reading. I remember the day when I ② my first book...",
        "content_full": "I have always enjoyed reading. I remember the day when I bought my first book...",
        "word_count": 280,
        "blanks": [
            {
                "blank_number": 1,
                "options": {"A": "hated", "B": "disliked", "C": "enjoyed", "D": "avoided"},
                "correct_answer": "C",
                "correct_word": "enjoyed"
            },
            {
                "blank_number": 2,
                "options": {"A": "bought", "B": "borrowed", "C": "sold", "D": "lost"},
                "correct_answer": "A",
                "correct_word": "bought"
            }
        ]
    }
}
```

如果无法找到C篇或D篇，passages数组中可以只包含找到的文章。如果完全找不到，passages为空数组。
如果找不到某篇文章的题目，questions数组可以为空。
如果找不到完形填空，cloze.found设为false，其他字段可省略。"""

    EXTRACT_WRITING_PROMPT = """你是一个英语试卷解析专家。请分析这份英语试卷文档，提取作文题目信息。

## 需要提取的信息

### 作文题目
- found: 是否找到作文题目（true/false）
- content: 作文题目的完整内容（包括题目描述、情景设置等）
- requirements: 具体写作要求（如字数、格式等）
- word_limit: 字数限制（如"80-100词"、"不少于60词"等）

### 文体类型识别
- writing_type: 文体类型，必须从以下三个选项中选择一个：
  - "应用文"：书信、通知、邀请、邮件、回复、活动介绍、请假条、感谢信等
  - "记叙文"：讲述经历、描述事件、讲故事等
  - "其他"：无法归类或以上两者都不符合的

- application_type: 仅当 writing_type 为"应用文"时填写，具体子类型如：
  - 书信、通知、邀请函、电子邮件、回复信、活动介绍、日记、便条等
  - 如果不是应用文，此字段留空

## 注意事项
1. 仔细识别作文题目的完整内容，包括所有背景信息和要求
2. 文体类型必须准确分类，根据题目要求判断
3. 如果找不到作文题目，将 found 设为 false

## 输出格式

请严格按照以下JSON格式输出，不要添加任何其他文字：

```json
{
    "found": true,
    "content": "假设你是李华，你的英国笔友Tom对中国传统文化很感兴趣...",
    "requirements": "1. 词数80-100；2. 可适当增加细节...",
    "word_limit": "80-100词",
    "writing_type": "应用文",
    "application_type": "书信"
}
```

如果未找到作文题目：
```json
{
    "found": false
}
```"""

    def __init__(self):
        self.api_key = settings.DASHSCOPE_API_KEY
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY未配置")

    async def upload_file(self, file_path: str) -> str:
        """
        上传文件到DashScope文件服务

        Args:
            file_path: 文件路径

        Returns:
            fileid: 文件ID
        """
        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(file_path, 'rb') as f:
                files = {'file': (Path(file_path).name, f, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}
                data = {'purpose': 'file-extract'}  # 必须指定purpose (file-extract或batch)
                headers = {'Authorization': f'Bearer {self.api_key}'}

                response = await client.post(
                    self.UPLOAD_URL,
                    headers=headers,
                    files=files,
                    data=data
                )

            if response.status_code != 200:
                raise Exception(f"上传文件失败: {response.text}")

            result = response.json()
            return result['id']

    async def parse_document(self, file_path: str, use_fileid: bool = True) -> LLMParseResult:
        """
        使用LLM解析文档

        Args:
            file_path: 文档路径
            use_fileid: 是否使用fileid方式（True）还是直接文本方式（False）

        Returns:
            LLMParseResult: 解析结果
        """
        try:
            if use_fileid:
                # 方式1: 上传文件后使用fileid
                fileid = await self.upload_file(file_path)
                messages = [
                    {"role": "system", "content": "You are a helpful assistant specialized in parsing English exam papers."},
                    {"role": "system", "content": f"fileid://{fileid}"},
                    {"role": "user", "content": self.EXTRACT_PROMPT}
                ]
            else:
                # 方式2: 直接读取文本内容（备用方案）
                from docx import Document
                doc = Document(file_path)
                full_text = "\n".join([p.text for p in doc.paragraphs])

                messages = [
                    {"role": "system", "content": "You are a helpful assistant specialized in parsing English exam papers."},
                    {"role": "user", "content": f"{self.EXTRACT_PROMPT}\n\n## 文档内容\n\n{full_text[:30000]}"}  # 限制长度
                ]

            # 调用LLM API
            async with httpx.AsyncClient(timeout=120.0) as client:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }

                payload = {
                    "model": "qwen-long",
                    "messages": messages,
                    "temperature": 0.1,  # 低温度保证稳定性
                    "max_tokens": 16000  # 增加以支持题目和答案
                }

                response = await client.post(
                    self.API_URL,
                    headers=headers,
                    json=payload
                )

                if response.status_code != 200:
                    return LLMParseResult(
                        success=False,
                        error=f"API调用失败: {response.status_code} - {response.text}"
                    )

                result = response.json()
                content = result['choices'][0]['message']['content']

                # 解析JSON响应
                return self._parse_llm_response(content)

        except Exception as e:
            return LLMParseResult(
                success=False,
                error=str(e)
            )

    def _parse_llm_response(self, content: str) -> LLMParseResult:
        """解析LLM返回的JSON内容"""
        try:
            # 尝试提取JSON部分
            json_str = content

            # 如果有markdown代码块，提取其中的JSON
            if '```json' in content:
                start = content.find('```json') + 7
                end = content.find('```', start)
                json_str = content[start:end].strip()
            elif '```' in content:
                start = content.find('```') + 3
                end = content.find('```', start)
                json_str = content[start:end].strip()

            data = json.loads(json_str)

            return LLMParseResult(
                success=True,
                metadata=data.get('metadata', {}),
                passages=data.get('passages', []),
                cloze=data.get('cloze', {}),
                raw_response=content
            )

        except json.JSONDecodeError as e:
            return LLMParseResult(
                success=False,
                error=f"JSON解析失败: {str(e)}",
                raw_response=content
            )

    async def parse_document_with_fileid(self, fileid: str) -> LLMParseResult:
        """
        使用已上传的fileid解析文档

        Args:
            fileid: 已上传到DashScope的文件ID

        Returns:
            LLMParseResult: 解析结果
        """
        try:
            messages = [
                {"role": "system", "content": "You are a helpful assistant specialized in parsing English exam papers."},
                {"role": "system", "content": f"fileid://{fileid}"},
                {"role": "user", "content": self.EXTRACT_PROMPT}
            ]

            # 调用LLM API
            async with httpx.AsyncClient(timeout=120.0) as client:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }

                payload = {
                    "model": "qwen-long",
                    "messages": messages,
                    "temperature": 0.1,
                    "max_tokens": 16000
                }

                response = await client.post(
                    self.API_URL,
                    headers=headers,
                    json=payload
                )

                if response.status_code != 200:
                    return LLMParseResult(
                        success=False,
                        error=f"API调用失败: {response.status_code} - {response.text}"
                    )

                result = response.json()
                content = result['choices'][0]['message']['content']

                return self._parse_llm_response(content)

        except Exception as e:
            return LLMParseResult(
                success=False,
                error=str(e)
            )

    async def extract_writing(self, fileid: str) -> "WritingExtractResult":
        """
        使用 LLM 提取作文题目信息

        Args:
            fileid: 已上传到 DashScope 的文件 ID

        Returns:
            WritingExtractResult: 结构化提取结果
        """
        try:
            messages = [
                {"role": "system", "content": "You are a helpful assistant specialized in parsing English exam papers."},
                {"role": "system", "content": f"fileid://{fileid}"},
                {"role": "user", "content": self.EXTRACT_WRITING_PROMPT}
            ]

            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }

                payload = {
                    "model": "qwen-long",
                    "messages": messages,
                    "temperature": 0.1,
                    "max_tokens": 2000
                }

                response = await client.post(
                    self.API_URL,
                    headers=headers,
                    json=payload
                )

                if response.status_code != 200:
                    return WritingExtractResult(
                        success=False,
                        error=f"API调用失败: {response.status_code}"
                    )

                result = response.json()
                content = result['choices'][0]['message']['content']

                return self._parse_writing_response(content)

        except Exception as e:
            return WritingExtractResult(
                success=False,
                error=str(e)
            )

    def _parse_writing_response(self, content: str) -> "WritingExtractResult":
        """解析作文提取响应"""
        try:
            # 提取 JSON
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

            # 验证是否找到作文
            if not data.get('found', True):
                return WritingExtractResult(
                    success=False,
                    error="未找到作文题目"
                )

            # 验证并规范化 writing_type
            writing_type = data.get('writing_type', '其他')
            if writing_type not in ('应用文', '记叙文', '其他'):
                writing_type = '其他'

            # application_type 仅在应用文时有效
            application_type = data.get('application_type')
            if writing_type != '应用文':
                application_type = None
            elif application_type == 'null' or application_type == '':
                application_type = None

            return WritingExtractResult(
                success=True,
                content=data.get('content', ''),
                requirements=data.get('requirements', ''),
                word_limit=data.get('word_limit', ''),
                writing_type=writing_type,
                application_type=application_type
            )

        except json.JSONDecodeError as e:
            return WritingExtractResult(
                success=False,
                error=f"JSON解析失败: {str(e)}"
            )


# 使用示例
async def test_llm_parser():
    """测试LLM解析器"""
    parser = LLMDocumentParser()

    test_file = "/Users/maoyu/Downloads/personal/项目-code/teachtools/2022-2025北京市各区各学校试题汇总/2022/初二春季期末/朝阳/2022北京朝阳初二（下）期末英语（教师版）.docx"

    print("正在上传文件并解析...")
    result = await parser.parse_document(test_file, use_fileid=True)

    if result.success:
        print("=== 元数据 ===")
        print(json.dumps(result.metadata, ensure_ascii=False, indent=2))

        print("\n=== 文章 ===")
        for p in result.passages:
            print(f"\n{p['passage_type']}篇 ({p['word_count']}词):")
            print(p['content'][:200] + "...")
    else:
        print(f"解析失败: {result.error}")
        if result.raw_response:
            print(f"原始响应: {result.raw_response[:500]}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_llm_parser())
