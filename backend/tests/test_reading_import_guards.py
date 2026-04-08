import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.papers import infer_question_type_from_payload
from app.services.image_extractor import ImageExtractor, QuestionBlockAnalysis


def test_analyze_single_question_block_recognizes_options_without_punctuation(tmp_path: Path) -> None:
    extractor = ImageExtractor(storage_dir=str(tmp_path))
    block = [
        {"index": 10, "text": "39From the passage we know a black hole is .", "images": []},
        {"index": 11, "text": "A a huge hole in the universe", "images": []},
        {"index": 12, "text": "B a group of stars packed together", "images": []},
        {"index": 13, "text": "C a dead star that is packed tightly", "images": []},
        {"index": 14, "text": "D complete silent darkness in space", "images": []},
    ]

    analysis = extractor._analyze_single_question_block(
        question_number=39,
        block=block,
        question_key="0:0",
    )

    assert analysis.has_option_markers is True


def test_enrich_passages_does_not_downgrade_text_options_to_open_ended(tmp_path: Path) -> None:
    extractor = ImageExtractor(storage_dir=str(tmp_path))
    extractor.analyze_question_blocks = lambda **_: [
        QuestionBlockAnalysis(
            question_number=39,
            option_images=[],
            question_images=[],
            has_option_markers=False,
            question_key="0:0",
        )
    ]

    passages = [
        {
            "questions": [
                {
                    "question_number": 39,
                    "question_text": "From the passage we know a black hole is .",
                    "options": {
                        "A": "a huge hole in the universe",
                        "B": "a group of stars packed together",
                        "C": "a dead star that is packed tightly",
                        "D": "complete silent darkness in space",
                    },
                    "correct_answer": "C",
                }
            ]
        }
    ]

    extractor.enrich_passages_with_images("unused.docx", paper_id=1, passages=passages)

    question = passages[0]["questions"][0]
    assert question.get("is_open_ended") is not True


def test_enrich_passages_keeps_true_open_ended_question(tmp_path: Path) -> None:
    extractor = ImageExtractor(storage_dir=str(tmp_path))
    extractor.analyze_question_blocks = lambda **_: [
        QuestionBlockAnalysis(
            question_number=45,
            option_images=[],
            question_images=[],
            has_option_markers=False,
            question_key="0:0",
        )
    ]

    passages = [
        {
            "questions": [
                {
                    "question_number": 45,
                    "question_text": "What do you think of screen-free days?",
                    "options": {},
                    "correct_answer": "",
                }
            ]
        }
    ]

    extractor.enrich_passages_with_images("unused.docx", paper_id=1, passages=passages)

    assert passages[0]["questions"][0]["is_open_ended"] is True


def test_infer_question_type_prefers_multiple_choice_when_options_exist() -> None:
    question_data = {
        "question_text": "What is the writer's purpose of writing this article?",
        "is_open_ended": True,
        "correct_answer": "B",
        "options": {
            "A": "To explain why people have different feelings.",
            "B": "To advise parents to teach children about feelings.",
            "C": "To guide young kids to get along well with parents.",
            "D": "To help kids understand different roles in TV series.",
        },
    }

    assert infer_question_type_from_payload(question_data) == "multiple_choice"


def test_infer_question_type_keeps_real_open_ended_questions() -> None:
    question_data = {
        "question_text": "What do you think of screen-free days?",
        "is_open_ended": True,
        "correct_answer": "",
        "options": {},
    }

    assert infer_question_type_from_payload(question_data) == "open_ended"
