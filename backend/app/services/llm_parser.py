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
    metadata: Dict = None  # {"year": 2022, "region": "东城", ...}
    error: str = None
    raw_response: str = None


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
- options: 四个选项，格式为 {"A": "选项A内容", "B": "选项B内容", "C": "选项C内容", "D": "选项D内容"}
- correct_answer: 正确答案（A/B/C/D，如果是教师版能找到答案的话）
- answer_explanation: 答案解析（如果是教师版能找到解析的话）

## 注意事项
- 如果是教师版试卷，注意区分题目、学生版内容和答案解析
- 题目通常紧跟在文章后面，题号一般是连续的
- 确保选项内容完整，不要截断
- 如果找不到答案或解析，对应字段可以省略

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
                    "correct_answer": "A",
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
                    "correct_answer": "B",
                    "answer_explanation": "答案解析内容..."
                }
            ]
        }
    ]
}
```

如果无法找到C篇或D篇，passages数组中可以只包含找到的文章。如果完全找不到，passages为空数组。
如果找不到某篇文章的题目，questions数组可以为空。"""

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
