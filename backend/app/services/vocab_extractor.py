"""
词汇提取服务

从文章中提取高频词汇，记录位置信息用于定位功能
"""
import re
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
from collections import Counter

import nltk

# 确保NLTK数据已下载
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('taggers/averaged_perceptron_tagger')
except LookupError:
    nltk.download('averaged_perceptron_tagger', quiet=True)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)


@dataclass
class WordOccurrence:
    """词汇出现位置"""
    word: str
    sentence: str
    char_position: int  # 在原文中的字符位置（起始）
    end_position: int  # 在原文中的字符位置（结束）
    word_position: int  # 词序位置


@dataclass
class ExtractedWord:
    """提取的词汇"""
    word: str
    lemma: str
    frequency: int
    occurrences: List[WordOccurrence]


class VocabExtractor:
    """词汇提取器"""

    # 中考常见简单词（停用词）
    STOP_WORDS: Set[str] = {
        # 基础代词
        "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
        "you", "your", "yours", "yourself", "yourselves",
        "he", "him", "his", "himself", "she", "her", "hers", "herself",
        "it", "its", "itself", "they", "them", "their", "theirs", "themselves",
        # 基础冠词/介词
        "a", "an", "the", "and", "but", "or", "nor", "for", "yet", "so",
        "in", "on", "at", "to", "of", "with", "by", "from", "as", "into",
        "through", "during", "before", "after", "above", "below", "between",
        "under", "again", "further", "then", "once", "here", "there", "when",
        "where", "why", "how", "all", "each", "few", "more", "most", "other",
        "some", "such", "no", "not", "only", "own", "same", "than", "too",
        # 基础动词
        "is", "am", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "having", "do", "does", "did", "doing",
        "will", "would", "shall", "should", "can", "could", "may", "might",
        "must", "need", "dare", "ought", "used",
        # 其他简单词
        "this", "that", "these", "those", "what", "which", "who", "whom",
        "any", "both", "either", "neither", "much", "many", "little", "less",
        "very", "just", "also", "even", "still", "already", "always", "never",
        "often", "sometimes", "usually", "ever", "never",
        # 数字
        "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
        "first", "second", "third",
        # 时间词
        "year", "years", "day", "days", "time", "times", "way", "ways",
        "thing", "things", "people", "man", "men", "woman", "women", "child", "children",
    }

    # 最小词长度
    MIN_WORD_LENGTH = 3

    # 最小词频
    MIN_FREQUENCY = 1

    def __init__(self, min_length: int = 3, min_frequency: int = 1):
        self.min_length = min_length
        self.min_frequency = min_frequency

    def extract(self, content: str) -> List[ExtractedWord]:
        """
        从文章中提取高频词汇

        Args:
            content: 文章内容

        Returns:
            提取的词汇列表
        """
        # 1. 分句
        sentences = self._split_sentences(content)

        # 2. 对每个句子提取词汇
        all_occurrences: List[WordOccurrence] = []

        for sentence in sentences:
            sentence_occurrences = self._extract_from_sentence(sentence, content)
            all_occurrences.extend(sentence_occurrences)

        # 3. 统计词频并分组
        word_occurrences: Dict[str, List[WordOccurrence]] = {}
        for occ in all_occurrences:
            word_lower = occ.word.lower()
            if word_lower not in word_occurrences:
                word_occurrences[word_lower] = []
            word_occurrences[word_lower].append(occ)

        # 4. 构建结果
        result = []
        for word, occurrences in word_occurrences.items():
            if len(occurrences) >= self.min_frequency:
                result.append(ExtractedWord(
                    word=word,
                    lemma=self._get_lemma(word),
                    frequency=len(occurrences),
                    occurrences=occurrences
                ))

        # 5. 按词频排序
        result.sort(key=lambda x: x.frequency, reverse=True)

        return result

    def _split_sentences(self, content: str) -> List[str]:
        """分割句子"""
        # 使用NLTK分句
        sentences = nltk.sent_tokenize(content)
        # 过滤空句子
        return [s.strip() for s in sentences if s.strip()]

    def _extract_from_sentence(self, sentence: str, full_content: str) -> List[WordOccurrence]:
        """从单个句子中提取词汇"""
        occurrences = []

        # 在原文中找到句子的位置
        sentence_start = full_content.find(sentence)
        if sentence_start == -1:
            return occurrences

        # 分词
        words = nltk.word_tokenize(sentence)

        # 词性标注
        tagged = nltk.pos_tag(words)

        word_position = 0
        current_pos = 0

        for word, pos in tagged:
            # 过滤条件
            if self._should_filter(word, pos):
                current_pos += len(word) + 1  # +1 for space
                continue

            # 在句子中找到词的位置
            word_in_sentence = sentence.find(word, current_pos)
            if word_in_sentence == -1:
                current_pos += len(word) + 1
                continue

            # 计算在原文中的绝对位置
            char_position = sentence_start + word_in_sentence
            end_position = char_position + len(word)

            occurrences.append(WordOccurrence(
                word=word.lower(),
                sentence=sentence,
                char_position=char_position,
                end_position=end_position,
                word_position=word_position
            ))

            word_position += 1
            current_pos = word_in_sentence + len(word)

        return occurrences

    def _should_filter(self, word: str, pos: str) -> bool:
        """判断是否应该过滤该词"""
        word_lower = word.lower()

        # 过滤短词
        if len(word_lower) < self.min_length:
            return True

        # 过滤停用词
        if word_lower in self.STOP_WORDS:
            return True

        # 过滤纯数字
        if word.isdigit():
            return True

        # 过滤标点符号
        if not word.isalpha():
            # 允许带连字符的词（如well-known）
            if '-' not in word or not all(part.isalpha() for part in word.split('-')):
                return True

        return False

    def _get_lemma(self, word: str) -> str:
        """获取词元形式（简化版）"""
        # 简单的词形还原规则
        if word.endswith('ies') and len(word) > 4:
            return word[:-3] + 'y'  # stories -> story
        elif word.endswith('es') and len(word) > 3:
            return word[:-2]  # watches -> watch
        elif word.endswith('s') and not word.endswith('ss') and len(word) > 2:
            return word[:-1]  # books -> book
        elif word.endswith('ed') and len(word) > 3:
            return word[:-2]  # worked -> work
        elif word.endswith('ing') and len(word) > 4:
            return word[:-3]  # working -> work
        elif word.endswith('ly') and len(word) > 3:
            return word[:-2]  # quickly -> quick
        elif word.endswith('er') and len(word) > 3:
            return word[:-2]  # taller -> tall
        elif word.endswith('est') and len(word) > 4:
            return word[:-3]  # tallest -> tall
        return word


# 便捷函数
def extract_vocabulary(content: str, min_length: int = 3, min_frequency: int = 1) -> List[ExtractedWord]:
    """
    从文章中提取高频词汇

    Args:
        content: 文章内容
        min_length: 最小词长度
        min_frequency: 最小词频

    Returns:
        提取的词汇列表
    """
    extractor = VocabExtractor(min_length=min_length, min_frequency=min_frequency)
    return extractor.extract(content)
