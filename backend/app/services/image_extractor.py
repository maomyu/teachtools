"""
Word 文档图片提取服务

从 Word 文档中提取选项图片并保存到本地存储
"""
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from docx import Document


@dataclass
class OptionImage:
    """选项图片数据"""
    question_number: int
    option_label: str  # A, B, C, D
    image_url: str
    paragraph_index: int


class ImageExtractor:
    """Word 文档图片提取器 - 专门提取选项图片"""

    # XML 命名空间
    NS_DRAWING = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing'
    NS_BLIP = '{http://schemas.openxmlformats.org/drawingml/2006/main}blip'
    NS_EMBED = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed'

    # 匹配多选项同一行的正则, A. B. 或 C. D.
    MULTI_OPTION_PATTERN = re.compile(r'^([A-D])\s*[\.、．]?\s+([A-D])\s*[\.、．]?\s*$')

    # 匹配单独选项的正则
    SINGLE_OPTION_PATTERN = re.compile(r'^([A-D])\s*[\.、．]?\s*(.*)$')

    def __init__(self, storage_dir: str = "static/images/options"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def extract_option_images(
        self,
        doc_path: str,
        paper_id: int
    ) -> List[OptionImage]:
        """
        从 Word 文档中提取选项图片（两阶段策略）

        阶段1: 提取所有图片，建立 rId -> image_url 映射
        阶段2: 建立图片位置映射 (段落索引 -> 图片信息)
        阶段3: 匹配选项标记与图片位置
        Args:
            doc_path: Word 文档路径
            paper_id: 试卷 ID，用于生成图片文件名
        Returns:
            List[OptionImage]: 提取的选项图片列表
        """
        doc = Document(doc_path)
        # 阶段1: 提取所有图片，建立 rId -> image_url 映射
        image_map = self._extract_all_images(doc, paper_id)
        print(f"[ImageExtractor] 阶段1完成: 共提取 {len(image_map)} 张图片")
        if not image_map:
            print("[ImageExtractor] 未找到任何图片，提前返回")
            return []
        # 阶段2: 建立图片位置映射 (段落索引 -> 图片信息)
        position_map = self._build_position_map(doc, image_map)
        print(f"[ImageExtractor] 阶段2完成: 共找到 {len(position_map)} 个图片位置")
        if not position_map:
            print("[ImageExtractor] 未找到图片位置映射，提前返回")
            return []
        # 阶段3: 匹配选项标记与图片
        option_images = self._match_options(doc, position_map)
        print(f"[ImageExtractor] 阶段3完成: 共匹配 {len(option_images)} 个选项图片")
        return option_images
    def _extract_all_images(self, doc: Document, paper_id: int) -> Dict[str, str]:
        """
        提取文档中所有图片
        Args:
            doc: Document 对象
            paper_id: 试卷 ID
        Returns:
            Dict[rId, image_url] 图片 ID 到 URL 的映射
        """
        image_map = {}
        for rel_id, part in doc.part.related_parts.items():
            part_name = str(part.partname)
            # 检查是否是图片资源
            is_image = (
                '/word/media/' in part_name or
                part_name.endswith(('.png', '.jpg', '.jpeg', '.gif', '.emf', '.wmf'))
            )
            if is_image:
                try:
                    # 保存图片
                    image_url = self._save_image_with_id(part.blob, paper_id, rel_id)
                    image_map[rel_id] = image_url
                    print(f"[ImageExtractor] 提取图片: rId={rel_id}, part={part_name}, size={len(part.blob)}")
                except Exception as e:
                    print(f"[ImageExtractor] 保存图片失败: rId={rel_id}, error={e}")
        return image_map
    def _build_position_map(self, doc: Document, image_map: Dict[str, str]) -> List[Dict]:
        """
        建立段落位置到图片的映射
        Args:
            doc: Document 对象
            image_map: rId -> image_url 映射
        Returns:
            List[{paragraph_idx, rId, image_url}]
        """
        positions = []
        for para_idx, para in enumerate(doc.paragraphs):
            for run in para.runs:
                # 使用 iter() 遍历所有子元素（比 findall() 更可靠）
                for drawing in run._element.iter(self.NS_DRAWING):
                    for blip in drawing.iter(self.NS_BLIP):
                        embed_id = blip.get(self.NS_EMBED)
                        if embed_id and embed_id in image_map:
                            positions.append({
                                "paragraph_idx": para_idx,
                                "rId": embed_id,
                                "image_url": image_map[embed_id]
                            })
                            print(f"[ImageExtractor] 位置映射: 段落{para_idx} -> rId={embed_id}")
        return positions
    def _match_options(self, doc: Document, position_map: List[Dict]) -> List[OptionImage]:
        """
        匹配选项标记与图片位置
        支持两种格式：
        1. 单独一行: "A." "B." 等
        2. 多选项同一行: "A. B." "C. D." 等
        Args:
            doc: Document 对象
            position_map: 段落位置到图片的映射
        Returns:
            List[OptionImage]
        """
        option_images = []
        current_question = None
        for para_idx, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            # 检测题号 "1." "2." "31." "32." 等，            # 支持 (2) 格式
            q_match = re.match(r'^\(?\s*(\d+)\s*\)?\.?\s*', text)
            if q_match:
                current_question = int(q_match.group(1))
                print(f"[ImageExtractor] 检测到题号: {current_question}")
            # 检测多选项同一行的情况，如 "A. B." 或 "C. D."
            multi_match = self.MULTI_OPTION_PATTERN.match(text)
            if multi_match and current_question:
                opt1, opt2 = multi_match.group(1), multi_match.group(2)
                print(f"[ImageExtractor] 检测到多选项: {opt1}, {opt2}")
                # 查找该段落的所有图片，按顺序分配给选项
                imgs = self._find_all_images_at(para_idx, position_map)
                if len(imgs) >= 2:
                    # 两个选项都有图片
                    for i, opt in enumerate([opt1, opt2]):
                        option_images.append(OptionImage(
                            question_number=current_question,
                            option_label=opt,
                            image_url=imgs[i]["image_url"],
                            paragraph_index=para_idx
                        ))
                        print(f"[ImageExtractor] 匹配成功: Q{current_question}-{opt} (多选项)")
                elif len(imgs) == 1:
                    # 只有一个图片，分配给第一个选项
                    option_images.append(OptionImage(
                        question_number=current_question,
                        option_label=opt1,
                        image_url=imgs[0]["image_url"],
                        paragraph_index=para_idx
                    ))
                    print(f"[ImageExtractor] 匹配成功: Q{current_question}-{opt1} (多选项,单图)")
                continue
            # 检测单独选项标记 "A." "B." "C." "D."
            single_match = self.SINGLE_OPTION_PATTERN.match(text)
            if single_match and current_question:
                option_label = single_match.group(1)
                option_text = single_match.group(2).strip()
                print(f"[ImageExtractor] 检测到选项: {option_label}, 文本: '{option_text}'")
                # 如果选项后面没有文字，可能是图片选项
                if not option_text:
                    # 先检查当前段落
                    img = self._find_image_at(para_idx, position_map)
                    if img:
                        option_images.append(OptionImage(
                            question_number=current_question,
                            option_label=option_label,
                            image_url=img["image_url"],
                            paragraph_index=para_idx
                        ))
                        print(f"[ImageExtractor] 匹配成功: Q{current_question}-{option_label} (当前段落)")
                    else:
                        # 检查下一个段落（图片可能在下一行）
                        img = self._find_image_at(para_idx + 1, position_map)
                        if img:
                            option_images.append(OptionImage(
                                question_number=current_question,
                                option_label=option_label,
                                image_url=img["image_url"],
                                paragraph_index=para_idx + 1
                            ))
                            print(f"[ImageExtractor] 匹配成功(下一段落): Q{current_question}-{option_label}")
                else:
                    # 选项有文字内容，但也可能有图片（混合类型）
                    img = self._find_image_at(para_idx, position_map)
                    if img:
                        option_images.append(OptionImage(
                            question_number=current_question,
                            option_label=option_label,
                            image_url=img["image_url"],
                            paragraph_index=para_idx
                        ))
                        print(f"[ImageExtractor] 匹配成功(混合): Q{current_question}-{option_label}")
        return option_images
    def _find_image_at(self, para_idx: int, position_map: List[Dict]) -> Optional[Dict]:
        """查找指定段落位置的图片"""
        for pos in position_map:
            if pos["paragraph_idx"] == para_idx:
                return pos
        return None
    def _find_all_images_at(self, para_idx: int, position_map: List[Dict]) -> List[Dict]:
        """查找指定段落位置的所有图片"""
        return [pos for pos in position_map if pos["paragraph_idx"] == para_idx]
    def _save_image_with_id(self, image_data: bytes, paper_id: int, rel_id: str) -> str:
        """
        保存图片到本地存储
        Args:
            image_data: 图片二进制数据
            paper_id: 试卷 ID
            rel_id: 关系 ID
        Returns:
            图片 URL 路径
        """
        # 生成唯一文件名
        content_hash = hashlib.md5(image_data).hexdigest()[:8]
        # 清理 rel_id 中的特殊字符
        safe_id = rel_id.replace('rId', 'img')
        # 检测图片格式
        ext = self._detect_image_format(image_data)
        filename = f"paper_{paper_id}_{safe_id}_{content_hash}{ext}"
        # 保存文件
        file_path = self.storage_dir / filename
        with open(file_path, 'wb') as f:
            f.write(image_data)
        # 返回 URL 路径
        return f"/static/images/options/{filename}"
    def _detect_image_format(self, image_data: bytes) -> str:
        """
        检测图片格式
        Args:
            image_data: 图片二进制数据
        Returns:
            文件扩展名（如 .png, .jpg）
        """
        # PNG
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            return '.png'
        # JPEG
        elif image_data[:2] == b'\xff\xd8':
            return '.jpg'
        # GIF
        elif image_data[:6] in (b'GIF87a', b'GIF89a'):
            return '.gif'
        # BMP
        elif image_data[:2] == b'BM':
            return '.bmp'
        # WebP
        elif image_data[:4] == b'RIFF' and len(image_data) > 12 and image_data[8:12] == b'WEBP':
            return '.webp'
        # EMF (Windows Enhanced Metafile)
        elif len(image_data) > 44 and image_data[0:4] == b'\x01\x00\x00\x00':
            return '.emf'
        # 默认 png
        return '.png'
    def get_image_count_by_question(self, option_images: List[OptionImage]) -> Dict[int, int]:
        """
        统计每个题目的图片数量
        Args:
            option_images: 选项图片列表
        Returns:
            Dict[题号, 图片数量]
        """
        counts = {}
        for img in option_images:
            counts[img.question_number] = counts.get(img.question_number, 0) + 1
        return counts
    def validate_extraction(
        self,
        option_images: List[OptionImage],
        llm_questions: List[dict]
    ) -> List[str]:
        """
        验证图片提取结果
        Args:
            option_images: 提取的选项图片
            llm_questions: LLM 解析的题目列表
        Returns:
            警告消息列表
        """
        warnings = []
        image_counts = self.get_image_count_by_question(option_images)
        for q in llm_questions:
            q_num = q.get('question_number')
            if not q_num:
                continue
            # 检查 LLM 标记为有图片选项的题目
            if q.get('has_image_options'):
                expected = q.get('expected_image_count', 0)
                actual = image_counts.get(q_num, 0)
                if expected != actual:
                    warnings.append(
                        f"题目 {q_num}: LLM 预期 {expected} 张图片，实际提取 {actual} 张"
                    )
        return warnings
