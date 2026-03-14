#!/usr/bin/env python3
"""
课本单词表导入脚本

步骤：
1. 从 Word 文档中提取单词表数据，保存为 JSON 文件
2. 从 JSON 文件导入数据库

用于熟词僻义判断的参照基准
"""
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Optional, List, Dict

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from docx import Document
from sqlalchemy import text

from app.database import engine, async_session


# 单词表文件配置
VOCAB_FILES = [
    {"file": "人教版七上单词（2024）.docx", "publisher": "人教版", "grade": "七年级", "semester": "上"},
    {"file": "人教版七下单词（2024）.docx", "publisher": "人教版", "grade": "七年级", "semester": "下"},
    {"file": "人教版八上单词（2024）.docx", "publisher": "人教版", "grade": "八年级", "semester": "上"},
    {"file": "人教版八下单词（2024）.docx", "publisher": "人教版", "grade": "八年级", "semester": "下"},
    {"file": "外研版七上单词（2024）.docx", "publisher": "外研版", "grade": "七年级", "semester": "上"},
    {"file": "外研版七下单词（2024）.docx", "publisher": "外研版", "grade": "七年级", "semester": "下"},
    {"file": "外研版八上单词（2024）.docx", "publisher": "外研版", "grade": "八年级", "semester": "上"},
    {"file": "外研版八下单词（2024）.docx", "publisher": "外研版", "grade": "八年级", "semester": "下"},
]

# 单元标题匹配模式
UNIT_PATTERNS = [
    re.compile(r'^Starter\s*Unit\s*\d+', re.IGNORECASE),  # Starter Unit 1
    re.compile(r'^Unit\s*\d+', re.IGNORECASE),            # Unit 1
    re.compile(r'^Module\s*\d+', re.IGNORECASE),          # Module 1
    re.compile(r'^Stater\s*Unit', re.IGNORECASE),         # Stater Unit (外研版拼写)
]


def is_unit_title(line: str) -> Optional[str]:
    """判断是否为单元标题行"""
    line = line.strip()
    for pattern in UNIT_PATTERNS:
        if pattern.match(line):
            return line
    return None


def parse_vocab_line(line: str) -> Optional[Dict]:
    """
    解析单词行

    格式示例：
    - unit n. 单元
    - starter unit 过渡单元
    - each adj. & pron. 每个；各自
    - Helen 海伦 (专有名词，无词性)
    """
    line = line.strip()
    if not line:
        return None

    # 跳过单元标题行
    if is_unit_title(line):
        return None

    # 词性模式：n., v., adj., adv., pron., interj., prep., conj., num., art., modal, det.
    pos_pattern = r'((?:n|v|adj|adv|pron|interj|prep|conj|num|art|modal|det|aux)\.(?:\s*&\s*(?:n|v|adj|adv|pron|interj|prep|conj|num|art|modal|det|aux)\.)*)'

    # 匹配：单词 + 词性 + 释义
    match = re.match(rf'^([a-zA-Z\s\'\-]+?)\s+{pos_pattern}\s+(.+)$', line, re.IGNORECASE)

    if match:
        word = match.group(1).strip()
        pos = match.group(2).strip()
        definition = match.group(3).strip()
        return {"word": word, "pos": pos, "definition": definition}

    # 尝试匹配无词性的情况（短语或专有名词）
    if re.search(r'[\u4e00-\u9fff]', line):
        match = re.match(r'^([a-zA-Z\s\'\-]+?)\s+([\u4e00-\u9fff].*)$', line)
        if match:
            word = match.group(1).strip()
            definition = match.group(2).strip()
            return {"word": word, "pos": None, "definition": definition}

    return None


def extract_vocab_from_docx(file_path: Path, publisher: str, grade: str, semester: str) -> List[Dict]:
    """
    从 Word 文档中提取单词表

    处理两种格式：
    1. 每行一个单词（人教版大部分文件）
    2. 每个单元一个段落，段落内用换行符分隔（外研版七下）
    """
    doc = Document(file_path)
    vocab_list = []
    current_unit = None

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # 检查是否包含多行内容（外研版七下的格式）
        if '\n' in text:
            lines = text.split('\n')
        else:
            lines = [text]

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 检查是否为单元标题
            unit_title = is_unit_title(line)
            if unit_title:
                current_unit = unit_title
                continue

            # 解析单词行
            vocab_data = parse_vocab_line(line)
            if vocab_data:
                vocab_data["publisher"] = publisher
                vocab_data["grade"] = grade
                vocab_data["semester"] = semester
                vocab_data["unit"] = current_unit
                vocab_list.append(vocab_data)

    return vocab_list


def extract_all_to_json(project_root: Path) -> List[Dict]:
    """从所有文件提取单词，保存为 JSON"""
    all_vocab = []
    output_file = project_root / "backend" / "scripts" / "textbook_vocab.json"

    print("\n[1/2] 解析单词表文件...")

    for config in VOCAB_FILES:
        file_path = project_root / config["file"]

        if not file_path.exists():
            print(f"  ⚠️ 文件不存在: {config['file']}")
            continue

        print(f"  📄 解析: {config['file']}")
        vocab_list = extract_vocab_from_docx(
            file_path,
            config["publisher"],
            config["grade"],
            config["semester"]
        )
        print(f"     提取到 {len(vocab_list)} 个单词")
        all_vocab.extend(vocab_list)

    # 保存为 JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_vocab, f, ensure_ascii=False, indent=2)

    print(f"\n  总计: {len(all_vocab)} 个单词")
    print(f"  已保存到: {output_file}")

    # 去重统计
    unique_words = set(v["word"] for v in all_vocab)
    print(f"  去重后: {len(unique_words)} 个唯一单词")

    return all_vocab


def load_from_json() -> List[Dict]:
    """从 JSON 文件加载单词数据"""
    json_file = Path(__file__).parent / "textbook_vocab.json"

    if not json_file.exists():
        print(f"❌ JSON 文件不存在: {json_file}")
        print("   请先运行提取步骤")
        return []

    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)


async def clear_existing_data():
    """清空现有课本单词表数据"""
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM textbook_vocab"))
        print("  已清空现有数据")


async def import_to_database(vocab_list: List[Dict]) -> int:
    """导入单词数据到数据库"""
    if not vocab_list:
        return 0

    async with async_session() as session:
        for vocab in vocab_list:
            await session.execute(text("""
                INSERT INTO textbook_vocab (word, pos, definition, publisher, grade, semester, unit)
                VALUES (:word, :pos, :definition, :publisher, :grade, :semester, :unit)
            """), vocab)
        await session.commit()

    return len(vocab_list)


async def verify_import():
    """验证导入结果"""
    print("\n[验证] 抽样检查...")
    async with async_session() as session:
        # 检查总数
        result = await session.execute(text("SELECT COUNT(*) FROM textbook_vocab"))
        total = result.scalar()
        print(f"  数据库总记录数: {total}")

        # 按文件统计
        result = await session.execute(text("""
            SELECT publisher, grade, semester, COUNT(*) as cnt
            FROM textbook_vocab
            GROUP BY publisher, grade, semester
            ORDER BY publisher, grade, semester
        """))
        stats = result.fetchall()

        print("\n  按课本统计:")
        for row in stats:
            publisher, grade, semester, cnt = row
            print(f"    {publisher} {grade}{semester}: {cnt} 个单词")

        # 抽样展示
        result = await session.execute(text("""
            SELECT word, pos, definition, publisher, grade, semester, unit
            FROM textbook_vocab
            ORDER BY RANDOM()
            LIMIT 5
        """))
        samples = result.fetchall()

        print("\n  随机抽样 5 条:")
        for i, row in enumerate(samples, 1):
            word, pos, definition, publisher, grade, semester, unit = row
            pos_str = f"[{pos}]" if pos else ""
            unit_str = f" ({unit})" if unit else ""
            print(f"    {i}. {word} {pos_str} {definition} - {publisher}{grade}{semester}{unit_str}")


def show_usage():
    """显示使用说明"""
    print("用法:")
    print("  python scripts/import_textbook_vocab.py extract   # 从 Word 文档提取为 JSON")
    print("  python scripts/import_textbook_vocab.py import    # 从 JSON 导入数据库")
    print("  python scripts/import_textbook_vocab.py all       # 执行完整流程")


async def main():
    """主函数"""
    import sys

    if len(sys.argv) < 2:
        show_usage()
        return

    command = sys.argv[1]

    print("=" * 60)
    print("课本单词表导入脚本")
    print("=" * 60)

    project_root = Path(__file__).parent.parent.parent

    if command == "extract":
        extract_all_to_json(project_root)

    elif command == "import":
        print("\n[1/3] 从 JSON 加载数据...")
        vocab_list = load_from_json()

        if not vocab_list:
            return

        print(f"  加载了 {len(vocab_list)} 条记录")

        print("\n[2/3] 清空现有数据...")
        await clear_existing_data()

        print("\n[3/3] 导入数据到数据库...")
        count = await import_to_database(vocab_list)
        print(f"  ✅ 成功导入 {count} 条记录")

        await verify_import()

    elif command == "all":
        # 完整流程
        extract_all_to_json(project_root)

        print("\n[2/4] 从 JSON 加载数据...")
        vocab_list = load_from_json()

        if not vocab_list:
            return

        print(f"  加载了 {len(vocab_list)} 条记录")

        print("\n[3/4] 清空现有数据...")
        await clear_existing_data()

        print("\n[4/4] 导入数据到数据库...")
        count = await import_to_database(vocab_list)
        print(f"  ✅ 成功导入 {count} 条记录")

        await verify_import()

    else:
        print(f"未知命令: {command}")
        show_usage()

    print("\n" + "=" * 60)
    print("完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
