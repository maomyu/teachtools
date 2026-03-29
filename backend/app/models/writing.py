"""
作文模型

[INPUT]: 依赖 SQLAlchemy Base、ExamPaper
[OUTPUT]: 对外提供 WritingTask、WritingTemplate、WritingSample、WritingMaterial 模型
[POS]: backend/app/models 的作文相关数据模型
[PROTOCOL]: 变更时更新此头部，然后检查 CLAUDE.md
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, CheckConstraint, Float, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


# ==============================================================================
#                              CONSTANTS
# ==============================================================================

GRADE_OPTIONS = ('初一', '初二', '初三')
SEMESTER_OPTIONS = ('上学期', '下学期')
EXAM_TYPE_OPTIONS = ('期中', '期末', '一模', '中考', '其他')
WRITING_TYPE_OPTIONS = ('应用文', '记叙文', '其他')
SAMPLE_TYPE_OPTIONS = ('AI生成', '人工编写', '真题范文')


# ==============================================================================
#                              WRITING TASK
# ==============================================================================

class WritingTask(Base):
    """作文题目表"""
    __tablename__ = "writing_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    paper_id = Column(Integer, ForeignKey("exam_papers.id"), nullable=False)

    task_content = Column(Text, nullable=False)  # 题目要求
    requirements = Column(Text)  # 具体要求
    word_limit = Column(String(50))
    points_value = Column(String(20))  # 分值

    # 新分类字段（数据库分类树驱动）
    group_category_id = Column(Integer, ForeignKey("writing_categories.id"))
    major_category_id = Column(Integer, ForeignKey("writing_categories.id"))
    category_id = Column(Integer, ForeignKey("writing_categories.id"))
    category_confidence = Column(Float, default=0.0)
    category_reasoning = Column(Text)

    # ─────────────────────────────────────────────────────────────────────────
    #                              分类字段
    # ─────────────────────────────────────────────────────────────────────────
    grade = Column(String(10))       # 初一/初二/初三（从试卷元数据继承）
    semester = Column(String(10))    # 上学期/下学期
    exam_type = Column(String(20))   # 期中/期末/一模/中考/其他

    # 文体分类
    writing_type = Column(String(50))  # 应用文, 记叙文, 其他
    application_type = Column(String(50))  # 应用文子类：书信、通知、邀请等

    # 话题分类
    primary_topic = Column(String(100))
    topic_verified = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # ─────────────────────────────────────────────────────────────────────────
    #                              关系
    # ─────────────────────────────────────────────────────────────────────────
    paper = relationship("ExamPaper", back_populates="writing_tasks")
    samples = relationship("WritingSample", back_populates="task", cascade="all, delete-orphan")
    group_category = relationship("WritingCategory", foreign_keys=[group_category_id])
    major_category = relationship("WritingCategory", foreign_keys=[major_category_id])
    category = relationship("WritingCategory", foreign_keys=[category_id], back_populates="tasks")

    __table_args__ = (
        CheckConstraint(
            f"writing_type IN {WRITING_TYPE_OPTIONS}",
            name="ck_writing_type"
        ),
        CheckConstraint(
            f"grade IS NULL OR grade IN {GRADE_OPTIONS}",
            name="ck_grade"
        ),
        CheckConstraint(
            f"semester IS NULL OR semester IN {SEMESTER_OPTIONS}",
            name="ck_semester"
        ),
        CheckConstraint(
            f"exam_type IS NULL OR exam_type IN {EXAM_TYPE_OPTIONS}",
            name="ck_exam_type"
        ),
    )

    def __repr__(self):
        return f"<WritingTask(id={self.id}, grade={self.grade}, type={self.writing_type})>"


class WritingTemplate(Base):
    """作文模板表"""
    __tablename__ = "writing_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    category_id = Column(Integer, ForeignKey("writing_categories.id"), nullable=False)
    writing_type = Column(String(50), nullable=False)
    application_type = Column(String(50))
    template_name = Column(String(100), nullable=False)
    template_content = Column(Text, nullable=False)
    tips = Column(Text)  # 写作技巧
    structure = Column(Text)  # 结构说明
    template_key = Column(String(100))

    # === 新增专业要素字段 ===
    opening_sentences = Column(Text)    # 开头句型（JSON数组）
    closing_sentences = Column(Text)    # 结尾句型（JSON数组）
    transition_words = Column(Text)     # 过渡词汇（JSON数组）
    advanced_vocabulary = Column(Text)  # 高级词汇替换（JSON数组）
    grammar_points = Column(Text)       # 语法要点（JSON数组）
    scoring_criteria = Column(Text)     # 评分标准提示（JSON）

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    samples = relationship("WritingSample", back_populates="template")
    category = relationship("WritingCategory", back_populates="templates")

    __table_args__ = (
        UniqueConstraint("category_id", "template_key", name="uq_writing_templates_category_template_key"),
    )

    def __repr__(self):
        return f"<WritingTemplate(id={self.id}, name={self.template_name})>"


class WritingSample(Base):
    """作文范文表"""
    __tablename__ = "writing_samples"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("writing_tasks.id"))
    template_id = Column(Integer, ForeignKey("writing_templates.id"))

    sample_content = Column(Text, nullable=False)
    sample_type = Column(String(20))  # AI生成, 人工编写, 真题范文
    score_level = Column(String(20))  # 档次：一档、二档等

    # === 新增评估字段 ===
    word_count = Column(Integer)          # 实际字数
    highlights = Column(Text)             # 亮点表达（JSON数组）
    grammar_analysis = Column(Text)       # 语法分析（JSON）
    issues = Column(Text)                 # 存在问题（JSON数组，用于三档文）
    translation = Column(Text)            # 中文翻译

    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    task = relationship("WritingTask", back_populates="samples")
    template = relationship("WritingTemplate", back_populates="samples")

    __table_args__ = (
        CheckConstraint(
            "sample_type IN ('AI生成', '人工编写', '真题范文')",
            name="ck_sample_type"
        ),
    )

    def __repr__(self):
        return f"<WritingSample(id={self.id}, type={self.sample_type})>"


class WritingCategory(Base):
    """作文分类树"""
    __tablename__ = "writing_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(80), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    level = Column(Integer, nullable=False)
    parent_id = Column(Integer, ForeignKey("writing_categories.id"))
    path = Column(String(255), nullable=False)
    template_key = Column(String(100), nullable=False)
    prompt_hint = Column(Text)
    sort_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = relationship("WritingCategory", remote_side=[id], back_populates="children")
    children = relationship("WritingCategory", back_populates="parent")
    tasks = relationship("WritingTask", back_populates="category", foreign_keys=[WritingTask.category_id])
    templates = relationship("WritingTemplate", back_populates="category", foreign_keys=[WritingTemplate.category_id])

    def __repr__(self):
        return f"<WritingCategory(id={self.id}, code={self.code}, level={self.level})>"
