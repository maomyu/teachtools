"""
AI词汇提取服务

基于通义千问的语义级词汇提取，分析文章主题，提取与主题相关的核心词汇

[INPUT]: 依赖 httpx、app.config 的 DASHSCOPE_API_KEY
[OUTPUT]: 对外提供 VocabExtractor 类，提取主题相关核心词汇
[POS]: backend/app/services 的词汇提取服务
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
import json
import httpx
from typing import List, Dict, Optional
from dataclasses import dataclass

from app.config import settings


@dataclass
class WordOccurrence:
    """词汇出现位置"""
    word: str
    sentence: str
    char_position: int
    end_position: int
    word_position: int


@dataclass
class ExtractedWord:
    """提取的词汇"""
    word: str
    lemma: str
    frequency: int
    definition: str
    occurrences: List[WordOccurrence]


class VocabExtractor:
    """基于AI的词汇提取器"""

    API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    def __init__(self, min_length: int = 3, min_frequency: int = 1):
        self.min_length = min_length
        self.min_frequency = min_frequency
        self.api_key = settings.DASHSCOPE_API_KEY
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY未配置")

    def _build_prompt(self, content: str) -> str:
        """构建AI提示词"""
        return f"""你是一个英语教学专家。请分析下面这篇英语阅读文章，提取与文章主题相关的核心词汇。

## 要求

1. 提取 8-15 个核心词汇
2. 词汇应该：
   - 与文章主题紧密相关
   - 对中学生有学习价值
   - 包含关键名词、动词、形容词
3. 不要提取：
   - 简单常用词（如 good, bad, make, take）
   - 人名、地名等专有名词
   - 已经很基础的词

## 输出格式

请严格按照以下JSON格式输出，不要包含任何额外文字:

{{"topic": "文章主题（中文）", "words": [{{"word": "单词", "definition": "中文释义"}}]}}

## 文章内容

{content[:4000]}"""

    async def extract_async(self, content: str) -> List[ExtractedWord]:
        """使用AI异步提取核心词汇"""
        if not content or len(content) < 50:
            return []

        try:
            full_prompt = self._build_prompt(content)

            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }

                payload = {
                    "model": "qwen-plus",
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是一个专业的英语教学专家，擅长分析英语阅读文章并提取核心词汇。"
                        },
                        {
                            "role": "user",
                            "content": full_prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 2000
                }

                response = await client.post(
                    self.API_URL,
                    headers=headers,
                    json=payload
                )

                if response.status_code != 200:
                    print(f"AI词汇提取失败: {response.status_code} - {response.text}")
                    return []

                result = response.json()
                ai_content = result['choices'][0]['message']['content']

                return self._parse_ai_response(ai_content, content)

        except Exception as e:
            print(f"AI词汇提取异常: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _parse_ai_response(self, ai_content: str, original_content: str) -> List[ExtractedWord]:
        """解析AI返回的JSON"""
        try:
            # 提取JSON部分
            json_str = ai_content

            if '```json' in ai_content:
                start = ai_content.find('```json') + 7
                end = ai_content.find('```', start)
                json_str = ai_content[start:end].strip()
            elif '```' in ai_content:
                start = ai_content.find('```') + 3
                end = ai_content.find('```', start)
                json_str = ai_content[start:end].strip()

            data = json.loads(json_str)
            words_data = data.get('words', [])

            words_by_key: Dict[str, Dict] = {}
            for w in words_data:
                word = w.get('word', '').lower().strip()
                if not word or len(word) < self.min_length:
                    continue

                # 在原文中查找该词的出现位置
                occurrences = self._find_word_occurrences(word, original_content)

                if not occurrences:
                    continue

                definition = (w.get('definition') or '').strip()
                existing = words_by_key.get(word)
                if not existing:
                    words_by_key[word] = {
                        "definition": definition,
                        "occurrences": occurrences,
                    }
                    continue

                if not existing["definition"] and definition:
                    existing["definition"] = definition

                seen_positions = {occ.char_position for occ in existing["occurrences"]}
                for occ in occurrences:
                    if occ.char_position in seen_positions:
                        continue
                    existing["occurrences"].append(occ)
                    seen_positions.add(occ.char_position)

            result = []
            for word, payload in words_by_key.items():
                ordered_occurrences = sorted(
                    payload["occurrences"],
                    key=lambda occ: occ.char_position
                )
                result.append(ExtractedWord(
                    word=word,
                    lemma=word,
                    frequency=len(ordered_occurrences),
                    definition=payload["definition"],
                    occurrences=ordered_occurrences
                ))

            return result

        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}")
            print(f"AI返回内容: {ai_content[:500]}")
            return []
        except Exception as e:
            print(f"解析异常: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _find_word_occurrences(self, word: str, content: str) -> List[WordOccurrence]:
        """在原文中查找词汇出现位置"""
        occurrences = []
        content_lower = content.lower()

        start = 0
        word_pos = 0
        while True:
            pos = content_lower.find(word, start)
            if pos == -1:
                break

            sentence = self._extract_sentence(content, pos)
            if sentence:
                occurrences.append(WordOccurrence(
                    word=word,
                    sentence=sentence,
                    char_position=pos,
                    end_position=pos + len(word),
                    word_position=word_pos
                ))

            start = pos + len(word)
            word_pos += 1

        return occurrences

    def _extract_sentence(self, content: str, pos: int) -> str:
        """提取包含指定位置的句子"""
        start = pos
        while start > 0 and content[start-1] not in '.!?':
            start -= 1
            if pos - start > 500:
                break

        end = pos
        while end < len(content) and content[end] not in '.!?':
            end += 1
            if end - pos > 500:
                break

        if end < len(content):
            end += 1

        sentence = content[start:end].strip()
        return sentence if sentence else ""

    def extract(self, content: str) -> List[ExtractedWord]:
        """同步提取方法（兼容旧接口）"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.extract_async(content)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self.extract_async(content))
        except RuntimeError:
            return asyncio.run(self.extract_async(content))


async def extract_vocabulary_async(content: str) -> List[ExtractedWord]:
    """便捷函数：使用AI从文章中提取核心词汇"""
    extractor = VocabExtractor()
    return await extractor.extract_async(content)
