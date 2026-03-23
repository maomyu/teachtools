"""
测试图片提取服务

使用昌平试卷测试两阶段提取策略
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.image_extractor import ImageExtractor

# 测试文件路径
TEST_FILE = "/Users/maoyu/personal/code/teachtools/试卷库/区校试卷_2023_初二春季期末_昌平_2023北京昌平初二（下）期末英语（教师版）.docx"

def test_image_extraction():
    """测试图片提取"""
    print("=" * 60)
    print("测试图片提取服务")
    print("=" * 60)
    print(f"测试文件: {TEST_FILE}")
    print()

    # 检查文件是否存在
    if not os.path.exists(TEST_FILE):
        print(f"错误: 文件不存在: {TEST_FILE}")
        return

    # 创建提取器
    extractor = ImageExtractor(storage_dir="static/images/options")

    # 提取图片
    print("开始提取图片...")
    option_images = extractor.extract_option_images(TEST_FILE, paper_id=999)

    print()
    print("=" * 60)
    print("提取结果")
    print("=" * 60)
    print(f"共提取 {len(option_images)} 个选项图片")

    for img in option_images:
        print(f"  题目 {img.question_number}, 选项 {img.option_label}: {img.image_url}")

    # 统计每个题目的图片数量
    counts = extractor.get_image_count_by_question(option_images)
    print()
    print("各题目图片数量:")
    for q_num, count in sorted(counts.items()):
        print(f"  题目 {q_num}: {count} 张图片")

if __name__ == "__main__":
    test_image_extraction()
