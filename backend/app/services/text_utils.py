"""
完形填空空格格式标准化工具

支持三层处理：
1. 正则匹配已知格式
2. 格式完整性校验
3. AI 智能分析（回退方案）
"""
import re
import json
import logging
from typing import Tuple, List

from app.services.ai_service import QwenService

logger = logging.getLogger(__name__)

# 已知的空格格式正则：(匹配模式, 替换模式)
BLANK_PATTERNS = [
    # 下划线格式: ____13____ 或 __1__
    (r'_{2,}(\d+)_{2,}', r'(\1)'),
    # 中文括号: （1）或（13）
    (r'（(\d+)）', r'(\1)'),
    # 方括号: [1] 或 [13]
    (r'\[(\d+)\]', r'(\1)'),
]

# 带圈数字映射（支持 1-20）
CIRCLED_NUMBERS = {
    '①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5,
    '⑥': 6, '⑦': 7, '⑧': 8, '⑨': 9, '⑩': 10,
    '⑪': 11, '⑫': 12, '⑬': 13, '⑭': 14, '⑮': 15,
    '⑯': 16, '⑰': 17, '⑱': 18, '⑲': 19, '⑳': 20,
}


def normalize_known_patterns(content: str) -> Tuple[str, set]:
    """
    使用正则表达式标准化已知格式

    Args:
        content: 原始文章内容

    Returns:
        (标准化后的内容, 找到的空格编号集合)
    """
    if not content:
        return content, set()

    result = content
    found_blanks = set()

    # 处理带圈数字
    for char, num in CIRCLED_NUMBERS.items():
        if char in result:
            result = result.replace(char, f'({num})')
            found_blanks.add(num)

    # 处理其他正则格式
    for pattern, replacement in BLANK_PATTERNS:
        matches = re.findall(pattern, result)
        for match in matches:
            found_blanks.add(int(match))
        result = re.sub(pattern, replacement, result)

    return result, found_blanks


def validate_blanks(content: str, expected_count: int) -> bool:
    """
    校验空格格式是否完整且正确

    Args:
        content: 文章内容
        expected_count: 预期的空格数量

    Returns:
        是否校验通过
    """
    if expected_count <= 0:
        return False

    pattern = r'\((\d+)\)'
    matches = re.findall(pattern, content)
    if not matches:
        return False

    found_numbers = set(int(m) for m in matches)
    # 检查是否连续：1, 2, 3, ..., expected_count
    expected_set = set(range(1, expected_count + 1))
    return found_numbers == expected_set


def extract_blank_numbers(content: str) -> List[int]:
    """提取标准化正文中的空格编号。"""
    if not content:
        return []
    return [int(match) for match in re.findall(r'\((\d+)\)', content)]


def align_blank_numbers_with_content(
    content: str,
    blank_numbers: List[int],
) -> List[int]:
    """
    兼容“正文空格是 1..N，但 LLM 返回题号是 38..49”这类情况。

    当正文中的空格标记已经被标准化为连续的 1..N，且 blanks 列表数量一致时，
    优先按正文出现顺序回写空格编号，保证前端定位和后续语境提取一致。
    """
    content_blank_numbers = extract_blank_numbers(content)
    if not content_blank_numbers or len(content_blank_numbers) != len(blank_numbers):
        return blank_numbers

    if content_blank_numbers == blank_numbers:
        return blank_numbers

    expected_sequence = list(range(1, len(content_blank_numbers) + 1))
    if content_blank_numbers != expected_sequence:
        return blank_numbers

    sorted_blank_numbers = sorted(blank_numbers)
    if sorted_blank_numbers == expected_sequence:
        return blank_numbers

    is_consecutive = sorted_blank_numbers == list(
        range(sorted_blank_numbers[0], sorted_blank_numbers[0] + len(sorted_blank_numbers))
    )
    if is_consecutive:
        logger.info(
            "检测到完形空格编号与正文标记不一致，按正文顺序兼容映射: %s -> %s",
            blank_numbers,
            content_blank_numbers,
        )
        return content_blank_numbers

    return blank_numbers


async def normalize_with_ai(content: str, expected_count: int) -> str:
    """
    使用 AI 分析并标准化空格格式

    Args:
        content: 原始文章内容
        expected_count: 预期的空格数量

    Returns:
        标准化后的文章内容
    """
    try:
        qwen = QwenService()

        prompt = f"""请分析以下完形填空文章，找出所有空格标记的位置和编号。

文章内容：
{content}

已知空格数量：{expected_count}

请识别文章中的空格标记（可能是各种格式如：①②③、(1)(2)(3)、____1____、[1]等），
并将它们标准化为 (数字) 格式。

请返回 JSON 格式：
{{
    "found": true/false,
    "blanks": [
        {{"original": "原文中的空格标记", "number": 1}},
        ...
    ],
    "normalized_content": "标准化后的完整文章（所有空格标记都替换为 (数字) 格式）"
}}

如果无法识别空格格式，请返回 {{"found": false}}

注意：只返回 JSON，不要有其他内容。"""

        response = qwen.chat(prompt)

        # 尝试解析 JSON
        # 处理可能的 markdown 代码块
        json_str = response.strip()
        if json_str.startswith('```'):
            # 移除 markdown 代码块标记
            lines = json_str.split('\n')
            json_str = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

        result = json.loads(json_str)

        if result.get("found"):
            return result.get("normalized_content", content)

    except json.JSONDecodeError as e:
        logger.warning(f"AI 返回 JSON 解析失败: {e}")
    except Exception as e:
        logger.warning(f"AI 分析失败: {e}")

    return content


async def normalize_cloze_blanks(
    content: str,
    expected_count: int,
    use_ai_fallback: bool = True
) -> str:
    """
    完形填空空格格式标准化主函数

    Args:
        content: 原始文章内容
        expected_count: 预期的空格数量
        use_ai_fallback: 是否使用 AI 回退

    Returns:
        标准化后的文章内容
    """
    if not content:
        return content

    # Step 1: 正则匹配已知格式
    normalized, found_blanks = normalize_known_patterns(content)

    # Step 2: 校验格式完整性
    if validate_blanks(normalized, expected_count):
        logger.info(f"正则匹配成功，找到 {len(found_blanks)} 个空格")
        return normalized

    # Step 3: AI 回退（如果启用）
    if use_ai_fallback:
        logger.info(f"正则无法完全匹配 (预期 {expected_count} 个，找到 {found_blanks})，使用 AI 分析")
        ai_result = await normalize_with_ai(content, expected_count)
        if validate_blanks(ai_result, expected_count):
            logger.info("AI 分析成功")
            return ai_result
        logger.warning("AI 分析结果校验失败，返回正则结果")

    return normalized
