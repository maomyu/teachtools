"""
Word 文档图片提取服务

核心思路：
1. 从 DOCX 中提取所有图片并建立 rel_id -> image_url 映射
2. 还原段落顺序中的图片位置
3. 基于 LLM 已经抽出的题干定位题目块，再只在题目块内匹配图片选项

注意：
- LLM 的题号可能是篇内题号，不一定等于原卷里的总题号
- 不同 passage 里题号也可能重复
所以真正可靠的锚点必须以“题干”为主、题号为辅，并为每道题分配唯一 key。
"""
import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional

from docx import Document


@dataclass
class OptionImage:
    """选项图片数据"""
    question_number: int
    option_label: str  # A, B, C, D
    image_url: str
    paragraph_index: int
    question_key: Optional[str] = None


@dataclass
class QuestionAnchor:
    """题目在文档中的锚点位置"""
    question_number: int
    paragraph_index: int
    score: float = 0.0
    question_key: Optional[str] = None


@dataclass
class QuestionBlockAnalysis:
    """单道题块的结构分析结果"""
    question_number: int
    option_images: List[OptionImage]
    has_option_markers: bool
    question_key: Optional[str] = None


class ImageExtractor:
    """Word 文档图片提取器 - 专门提取阅读题目中的选项图片"""

    # XML 命名空间
    NS_DRAWING = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing"
    NS_BLIP = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
    NS_EMBED = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"

    # 文档结构匹配
    QUESTION_PATTERN = re.compile(r"^\s*[（(]?\s*(\d+)\s*[）)\.．、]?\s*")
    MULTI_OPTION_LABEL_PATTERN = re.compile(
        r"^\s*([A-D])(?:\s*[\.、．])?\s+([A-D])(?:\s*[\.、．])?\s*$"
    )
    SINGLE_OPTION_LABEL_PATTERN = re.compile(r"^\s*([A-D])(?:\s*[\.、．])?\s*$")
    SINGLE_OPTION_WITH_TEXT_PATTERN = re.compile(
        r"^\s*([A-D])(?:\s*[\.、．])\s*(.+?)\s*$"
    )

    STOP_TEXT_PATTERNS = [
        re.compile(r"^【分析】"),
        re.compile(r"^【解答】"),
        re.compile(r"^参考答案"),
        re.compile(r"^答案[:：]"),
        re.compile(r"^解析[:：]"),
    ]

    IMAGE_TOKEN_PATTERN = re.compile(r"\[IMAGE:(.+?)\]")
    MIN_TEXT_ANCHOR_SCORE = 0.45

    def __init__(self, storage_dir: str = "static/images/options"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def enrich_passages_with_images(
        self,
        doc_path: str,
        paper_id: int,
        passages: List[dict]
    ) -> tuple[List[OptionImage], List[str]]:
        """
        读取文档中的选项图片，并把图片 URL 回填到 LLM 提取结果里。

        Returns:
            (option_images, warnings)
        """
        questions: List[dict] = []
        for passage_idx, passage in enumerate(passages or []):
            for question_idx, question in enumerate(passage.get("questions", [])):
                if not question.get("question_number"):
                    continue

                question_key = f"{passage_idx}:{question_idx}"
                question["_image_key"] = question_key
                questions.append({
                    "question_number": question.get("question_number"),
                    "question_text": question.get("question_text", ""),
                    "has_image_options": question.get("has_image_options"),
                    "expected_image_count": question.get("expected_image_count"),
                    "_image_key": question_key,
                })

        if not questions:
            return [], []

        analyses = self.analyze_question_blocks(
            doc_path=doc_path,
            paper_id=paper_id,
            questions=questions
        )
        option_images = [
            image
            for analysis in analyses
            for image in analysis.option_images
        ]

        if not analyses:
            for passage in passages or []:
                for question in passage.get("questions", []):
                    question.pop("_image_key", None)
            return [], []

        block_marker_map: Dict[str, bool] = {}
        for analysis in analyses:
            if analysis.question_key:
                block_marker_map[analysis.question_key] = analysis.has_option_markers

        image_map: Dict[tuple[str, str], str] = {}
        for img in option_images:
            if img.question_key:
                image_map.setdefault((img.question_key, img.option_label), img.image_url)

        for passage in passages or []:
            for question in passage.get("questions", []):
                question_key = question.get("_image_key")
                if not question_key:
                    continue

                options = question.setdefault("options", {})
                matched_count = 0
                has_option_markers = block_marker_map.get(question_key, True)

                for opt_key in ["A", "B", "C", "D"]:
                    image_url = image_map.get((question_key, opt_key))
                    if not image_url:
                        continue

                    current_value = (options.get(opt_key) or "").strip()
                    options[opt_key] = self._merge_option_value(current_value, image_url)
                    matched_count += 1

                if matched_count > 0:
                    question["has_image_options"] = True
                    question["expected_image_count"] = max(
                        int(question.get("expected_image_count", 0) or 0),
                        matched_count
                    )

                if not has_option_markers and matched_count == 0:
                    question["is_open_ended"] = True

        warnings = self.validate_extraction(option_images, questions)

        for passage in passages or []:
            for question in passage.get("questions", []):
                question.pop("_image_key", None)

        return option_images, warnings

    def analyze_question_blocks(
        self,
        doc_path: str,
        paper_id: int,
        questions: Optional[List[dict]] = None
    ) -> List[QuestionBlockAnalysis]:
        """
        分析题目块结构，返回每道题的图片选项和是否存在显式选项标记。
        """
        doc = Document(doc_path)

        image_map = self._extract_all_images(doc, paper_id)
        print(f"[ImageExtractor] 阶段1完成: 共提取 {len(image_map)} 张图片")
        if not image_map:
            print("[ImageExtractor] 未找到任何图片，提前返回")
            return []

        paragraphs = self._build_paragraph_infos(doc, image_map)
        positioned_images = sum(len(p["images"]) for p in paragraphs)
        print(f"[ImageExtractor] 阶段2完成: 共找到 {positioned_images} 个图片位置")
        if positioned_images == 0:
            print("[ImageExtractor] 未找到图片位置映射，提前返回")
            return []

        if questions:
            analyses = self._analyze_by_question_blocks(paragraphs, questions)
        else:
            analyses = self._analyze_by_fallback_scan(paragraphs)

        option_images = [
            image
            for analysis in analyses
            for image in analysis.option_images
        ]
        print(f"[ImageExtractor] 阶段3完成: 共匹配 {len(option_images)} 个选项图片")
        return analyses

    def extract_option_images(
        self,
        doc_path: str,
        paper_id: int,
        questions: Optional[List[dict]] = None
    ) -> List[OptionImage]:
        """
        从 Word 文档中提取选项图片。

        当提供 questions 时，会先定位题目块，再在块内匹配图片；
        否则使用较宽松的整卷扫描兜底。
        """
        analyses = self.analyze_question_blocks(
            doc_path=doc_path,
            paper_id=paper_id,
            questions=questions,
        )
        return [
            image
            for analysis in analyses
            for image in analysis.option_images
        ]

    def _extract_all_images(self, doc: Document, paper_id: int) -> Dict[str, str]:
        """提取文档中所有图片。"""
        image_map: Dict[str, str] = {}
        for rel_id, part in doc.part.related_parts.items():
            part_name = str(part.partname)
            is_image = (
                "/word/media/" in part_name or
                part_name.endswith((".png", ".jpg", ".jpeg", ".gif", ".emf", ".wmf", ".bmp", ".webp"))
            )
            if not is_image:
                continue

            try:
                image_url = self._save_image_with_id(part.blob, paper_id, rel_id)
                image_map[rel_id] = image_url
                print(
                    f"[ImageExtractor] 提取图片: rId={rel_id}, part={part_name}, size={len(part.blob)}"
                )
            except Exception as exc:
                print(f"[ImageExtractor] 保存图片失败: rId={rel_id}, error={exc}")

        return image_map

    def _build_paragraph_infos(self, doc: Document, image_map: Dict[str, str]) -> List[dict]:
        """建立段落顺序中的图片位置映射。"""
        paragraphs: List[dict] = []

        for para_idx, para in enumerate(doc.paragraphs):
            image_urls: List[str] = []

            for run in para.runs:
                for drawing in run._element.iter(self.NS_DRAWING):
                    for blip in drawing.iter(self.NS_BLIP):
                        embed_id = blip.get(self.NS_EMBED)
                        if embed_id and embed_id in image_map:
                            image_urls.append(image_map[embed_id])
                            print(f"[ImageExtractor] 位置映射: 段落{para_idx} -> rId={embed_id}")

            paragraphs.append({
                "index": para_idx,
                "text": para.text.strip(),
                "images": image_urls,
            })

        return paragraphs

    def _analyze_by_question_blocks(
        self,
        paragraphs: List[dict],
        questions: List[dict]
    ) -> List[QuestionBlockAnalysis]:
        """基于题目锚点分析题目块。"""
        anchors = self._locate_questions(paragraphs, questions)

        analyses: List[QuestionBlockAnalysis] = []
        for idx, anchor in enumerate(anchors):
            next_anchor_idx = (
                anchors[idx + 1].paragraph_index
                if idx + 1 < len(anchors)
                else len(paragraphs)
            )
            block = paragraphs[anchor.paragraph_index:next_anchor_idx]
            analyses.append(
                self._analyze_single_question_block(
                    question_number=anchor.question_number,
                    block=block,
                    question_key=anchor.question_key,
                )
            )

        return analyses

    def _analyze_by_fallback_scan(self, paragraphs: List[dict]) -> List[QuestionBlockAnalysis]:
        """
        兜底扫描逻辑。

        只在题号合理（1-100）时建立题目块，避免把年份等数字当作题号。
        """
        anchors: List[QuestionAnchor] = []
        for para in paragraphs:
            q_num = self._extract_question_number(para["text"])
            if q_num is None or not (1 <= q_num <= 100):
                continue
            anchors.append(QuestionAnchor(question_number=q_num, paragraph_index=para["index"]))

        analyses: List[QuestionBlockAnalysis] = []
        for idx, anchor in enumerate(anchors):
            next_anchor_idx = (
                anchors[idx + 1].paragraph_index
                if idx + 1 < len(anchors)
                else len(paragraphs)
            )
            block = paragraphs[anchor.paragraph_index:next_anchor_idx]
            analyses.append(
                self._analyze_single_question_block(
                    question_number=anchor.question_number,
                    block=block,
                )
            )

        return analyses

    def _locate_questions(self, paragraphs: List[dict], questions: List[dict]) -> List[QuestionAnchor]:
        """
        定位 LLM 题目在原文中的题目块起点。

        策略：
        1. 先尝试“题号 + 题干”联合定位
        2. 如果题号是篇内题号、和原卷总题号对不上，就退回题干相似度定位
        3. 按题目顺序递增搜索，尽量避开答案区重复题干
        """
        anchors: List[QuestionAnchor] = []
        search_start = 0

        for question in questions:
            q_num = question.get("question_number")
            if not q_num:
                continue

            candidate = self._find_best_question_anchor(
                paragraphs=paragraphs,
                question_number=q_num,
                question_text=question.get("question_text", ""),
                start_index=search_start,
                question_key=question.get("_image_key"),
            )

            if not candidate:
                candidate = self._find_best_question_anchor(
                    paragraphs=paragraphs,
                    question_number=q_num,
                    question_text=question.get("question_text", ""),
                    start_index=0,
                    question_key=question.get("_image_key"),
                )

            if candidate:
                anchors.append(candidate)
                search_start = candidate.paragraph_index + 1

        return anchors

    def _find_best_question_anchor(
        self,
        paragraphs: List[dict],
        question_number: int,
        question_text: str,
        start_index: int,
        question_key: Optional[str] = None,
    ) -> Optional[QuestionAnchor]:
        number_candidate = self._find_best_number_anchor(
            paragraphs=paragraphs,
            question_number=question_number,
            question_text=question_text,
            start_index=start_index,
            question_key=question_key,
        )
        text_candidate = self._find_best_text_anchor(
            paragraphs=paragraphs,
            question_number=question_number,
            question_text=question_text,
            start_index=start_index,
            question_key=question_key,
        )

        if text_candidate and (number_candidate is None or text_candidate.score > number_candidate.score + 0.15):
            return text_candidate
        return number_candidate or text_candidate

    def _find_best_number_anchor(
        self,
        paragraphs: List[dict],
        question_number: int,
        question_text: str,
        start_index: int,
        question_key: Optional[str] = None,
    ) -> Optional[QuestionAnchor]:
        best: Optional[QuestionAnchor] = None

        for para in paragraphs[start_index:]:
            if self._extract_question_number(para["text"]) != question_number:
                continue

            score = self._score_question_candidate(para["text"], question_text)
            candidate = QuestionAnchor(
                question_number=question_number,
                paragraph_index=para["index"],
                score=score,
                question_key=question_key,
            )

            if best is None or candidate.score > best.score:
                best = candidate

        return best

    def _find_best_text_anchor(
        self,
        paragraphs: List[dict],
        question_number: int,
        question_text: str,
        start_index: int,
        question_key: Optional[str] = None,
    ) -> Optional[QuestionAnchor]:
        best: Optional[QuestionAnchor] = None

        for para in paragraphs[start_index:]:
            if not para["text"]:
                continue

            score = self._score_question_candidate(para["text"], question_text)
            if score < self.MIN_TEXT_ANCHOR_SCORE:
                continue

            candidate = QuestionAnchor(
                question_number=question_number,
                paragraph_index=para["index"],
                score=score,
                question_key=question_key,
            )

            if best is None or candidate.score > best.score:
                best = candidate

        return best

    def _analyze_single_question_block(
        self,
        question_number: int,
        block: List[dict],
        question_key: Optional[str] = None,
    ) -> QuestionBlockAnalysis:
        """
        在单道题的题目块里分析显式选项并抽取图片选项。

        支持三种常见格式：
        1. `A.` 行内直接跟图片
        2. `A.` 单独一行，下一段是图片
        3. `A. B.` / `C. D.` 同行多图
        """
        assignments: Dict[str, OptionImage] = {}
        pending_labels: List[str] = []
        has_option_markers = False

        for para in block:
            text = para["text"]
            images = para["images"]

            if text and self._should_stop_block(text):
                break

            multi_match = self.MULTI_OPTION_LABEL_PATTERN.match(text)
            if multi_match:
                has_option_markers = True
                labels = [multi_match.group(1), multi_match.group(2)]
                pending_labels = self._assign_images(
                    assignments=assignments,
                    question_number=question_number,
                    paragraph_index=para["index"],
                    labels=labels,
                    image_urls=images,
                    question_key=question_key,
                )
                continue

            single_label_match = self.SINGLE_OPTION_LABEL_PATTERN.match(text)
            if single_label_match:
                has_option_markers = True
                label = single_label_match.group(1)
                pending_labels.extend([label])
                pending_labels = self._assign_images(
                    assignments=assignments,
                    question_number=question_number,
                    paragraph_index=para["index"],
                    labels=pending_labels,
                    image_urls=images,
                    question_key=question_key,
                )
                continue

            single_with_text_match = self.SINGLE_OPTION_WITH_TEXT_PATTERN.match(text)
            if single_with_text_match:
                has_option_markers = True
                label = single_with_text_match.group(1)
                pending_labels = self._assign_images(
                    assignments=assignments,
                    question_number=question_number,
                    paragraph_index=para["index"],
                    labels=[label],
                    image_urls=images,
                    question_key=question_key,
                )
                if not images:
                    pending_labels = []
                continue

            if images and pending_labels:
                pending_labels = self._assign_images(
                    assignments=assignments,
                    question_number=question_number,
                    paragraph_index=para["index"],
                    labels=pending_labels,
                    image_urls=images,
                    question_key=question_key,
                )
                continue

            if text and not images:
                pending_labels = []

        order = {"A": 0, "B": 1, "C": 2, "D": 3}
        return QuestionBlockAnalysis(
            question_number=question_number,
            option_images=sorted(
                assignments.values(),
                key=lambda item: order.get(item.option_label, 99),
            ),
            has_option_markers=has_option_markers,
            question_key=question_key,
        )

    def _assign_images(
        self,
        assignments: Dict[str, OptionImage],
        question_number: int,
        paragraph_index: int,
        labels: List[str],
        image_urls: List[str],
        question_key: Optional[str] = None,
    ) -> List[str]:
        """把当前段落的图片按顺序绑定到待匹配选项。"""
        if not labels or not image_urls:
            return labels

        remaining_labels = list(labels)
        for image_url in image_urls:
            if not remaining_labels:
                break

            option_label = remaining_labels.pop(0)
            assignments.setdefault(
                option_label,
                OptionImage(
                    question_number=question_number,
                    option_label=option_label,
                    image_url=image_url,
                    paragraph_index=paragraph_index,
                    question_key=question_key,
                )
            )

        return remaining_labels

    def _extract_question_number(self, text: str) -> Optional[int]:
        match = self.QUESTION_PATTERN.match(text or "")
        if not match:
            return None
        return int(match.group(1))

    def _score_question_candidate(self, candidate_text: str, question_text: str) -> float:
        candidate_body = self._normalize_text(self._strip_question_prefix(candidate_text))
        question_body = self._normalize_text(question_text)

        if not candidate_body and not question_body:
            return 0.0
        if not question_body:
            return 0.0

        score = SequenceMatcher(None, candidate_body[:200], question_body[:200]).ratio()
        if question_body and question_body in candidate_body:
            score += 1.0
        if candidate_body and candidate_body in question_body:
            score += 0.5

        return score

    def _strip_question_prefix(self, text: str) -> str:
        return self.QUESTION_PATTERN.sub("", text or "", count=1).strip()

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r"[\W_]+", "", text.lower())

    def _should_stop_block(self, text: str) -> bool:
        return any(pattern.match(text) for pattern in self.STOP_TEXT_PATTERNS)

    def _merge_option_value(self, current_value: str, image_url: str) -> str:
        image_token = f"[IMAGE:{image_url}]"

        if not current_value or current_value == "[IMAGE]":
            return image_token

        if image_token in current_value:
            return current_value

        if "[IMAGE]" in current_value:
            return current_value.replace("[IMAGE]", image_token, 1)

        if self.IMAGE_TOKEN_PATTERN.search(current_value):
            return current_value

        return f"{current_value}\n{image_token}"

    def _save_image_with_id(self, image_data: bytes, paper_id: int, rel_id: str) -> str:
        """保存图片到本地存储。"""
        content_hash = hashlib.md5(image_data).hexdigest()[:8]
        safe_id = rel_id.replace("rId", "img")
        ext = self._detect_image_format(image_data)
        filename = f"paper_{paper_id}_{safe_id}_{content_hash}{ext}"

        file_path = self.storage_dir / filename
        with open(file_path, "wb") as file:
            file.write(image_data)

        return f"/static/images/options/{filename}"

    def _detect_image_format(self, image_data: bytes) -> str:
        """检测图片格式。"""
        if image_data[:8] == b"\x89PNG\r\n\x1a\n":
            return ".png"
        if image_data[:2] == b"\xff\xd8":
            return ".jpg"
        if image_data[:6] in (b"GIF87a", b"GIF89a"):
            return ".gif"
        if image_data[:2] == b"BM":
            return ".bmp"
        if image_data[:4] == b"RIFF" and len(image_data) > 12 and image_data[8:12] == b"WEBP":
            return ".webp"
        if len(image_data) > 44 and image_data[0:4] == b"\x01\x00\x00\x00":
            return ".emf"
        return ".png"

    def get_image_count_by_question(self, option_images: List[OptionImage]) -> Dict[str, int]:
        """统计每个题目的图片数量。"""
        counts: Dict[str, int] = {}
        for img in option_images:
            key = img.question_key or str(img.question_number)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def validate_extraction(
        self,
        option_images: List[OptionImage],
        llm_questions: List[dict]
    ) -> List[str]:
        """验证图片提取结果。"""
        warnings = []
        image_counts = self.get_image_count_by_question(option_images)

        for question in llm_questions:
            question_key = question.get("_image_key") or str(question.get("question_number"))
            if not question_key:
                continue

            if question.get("has_image_options"):
                expected = int(question.get("expected_image_count", 0) or 0)
                actual = image_counts.get(question_key, 0)
                if expected and expected != actual:
                    warnings.append(
                        f"题目 {question.get('question_number')}: LLM 预期 {expected} 张图片，实际提取 {actual} 张"
                    )

        return warnings
