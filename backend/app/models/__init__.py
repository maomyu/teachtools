"""
数据库模型
"""
from app.models.paper import ExamPaper
from app.models.reading import ReadingPassage, Question
from app.models.vocabulary import Vocabulary, VocabularyPassage
from app.models.topic import Topic
from app.models.cloze import ClozePassage, ClozePoint
from app.models.writing import WritingTask, WritingTemplate, WritingSample
from app.models.handout import HandoutConversion
from app.models.log import ImportLog

__all__ = [
    "ExamPaper",
    "ReadingPassage",
    "Question",
    "Vocabulary",
    "VocabularyPassage",
    "Topic",
    "ClozePassage",
    "ClozePoint",
    "WritingTask",
    "WritingTemplate",
    "WritingSample",
    "HandoutConversion",
    "ImportLog",
]
