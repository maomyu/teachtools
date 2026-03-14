"""
课本单词表 API

提供课本单词的 CRUD 操作，用于熟词僻义判断的参照基准
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from pydantic import BaseModel

from app.database import get_db
from app.models.textbook_vocab import TextbookVocab

router = APIRouter()


# Pydantic schemas
class TextbookVocabCreate(BaseModel):
    word: str
    pos: Optional[str] = None
    definition: str
    publisher: str
    grade: str
    semester: str
    unit: Optional[str] = None


class TextbookVocabUpdate(BaseModel):
    word: Optional[str] = None
    pos: Optional[str] = None
    definition: Optional[str] = None
    publisher: Optional[str] = None
    grade: Optional[str] = None
    semester: Optional[str] = None
    unit: Optional[str] = None


class TextbookVocabResponse(BaseModel):
    id: int
    word: str
    pos: Optional[str]
    definition: str
    publisher: str
    grade: str
    semester: str
    unit: Optional[str]

    class Config:
        from_attributes = True


class TextbookVocabListResponse(BaseModel):
    items: List[TextbookVocabResponse]
    total: int
    page: int
    page_size: int


class StatsResponse(BaseModel):
    total: int
    unique_words: int
    by_publisher: dict
    by_grade: dict


@router.get("", response_model=TextbookVocabListResponse)
async def list_textbook_vocab(
    page: int = 1,
    page_size: int = 20,
    publisher: Optional[str] = None,
    grade: Optional[str] = None,
    semester: Optional[str] = None,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取课本单词列表（支持分页和筛选）"""
    query = select(TextbookVocab)
    count_query = select(func.count(TextbookVocab.id))

    # 筛选条件
    if publisher:
        query = query.where(TextbookVocab.publisher == publisher)
        count_query = count_query.where(TextbookVocab.publisher == publisher)
    if grade:
        query = query.where(TextbookVocab.grade == grade)
        count_query = count_query.where(TextbookVocab.grade == grade)
    if semester:
        query = query.where(TextbookVocab.semester == semester)
        count_query = count_query.where(TextbookVocab.semester == semester)
    if keyword:
        keyword_filter = or_(
            TextbookVocab.word.contains(keyword),
            TextbookVocab.definition.contains(keyword)
        )
        query = query.where(keyword_filter)
        count_query = count_query.where(keyword_filter)

    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # 分页
    offset = (page - 1) * page_size
    query = query.order_by(TextbookVocab.publisher, TextbookVocab.grade, TextbookVocab.semester)
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    items = result.scalars().all()

    return TextbookVocabListResponse(
        items=[TextbookVocabResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """获取课本单词统计信息"""
    # 总数
    total_result = await db.execute(select(func.count(TextbookVocab.id)))
    total = total_result.scalar()

    # 唯一单词数
    unique_result = await db.execute(select(func.count(func.distinct(TextbookVocab.word))))
    unique_words = unique_result.scalar()

    # 按出版社统计
    publisher_result = await db.execute(
        select(TextbookVocab.publisher, func.count(TextbookVocab.id))
        .group_by(TextbookVocab.publisher)
    )
    by_publisher = {row[0]: row[1] for row in publisher_result.fetchall()}

    # 按年级统计
    grade_result = await db.execute(
        select(TextbookVocab.grade, func.count(TextbookVocab.id))
        .group_by(TextbookVocab.grade)
    )
    by_grade = {row[0]: row[1] for row in grade_result.fetchall()}

    return StatsResponse(
        total=total,
        unique_words=unique_words,
        by_publisher=by_publisher,
        by_grade=by_grade
    )


@router.get("/lookup")
async def lookup_word(
    word: str,
    db: AsyncSession = Depends(get_db)
):
    """查询单词是否在课本中（用于熟词僻义判断）"""
    query = select(TextbookVocab).where(TextbookVocab.word == word)
    result = await db.execute(query)
    entries = result.scalars().all()

    return {
        "found": len(entries) > 0,
        "entries": [TextbookVocabResponse.model_validate(e) for e in entries]
    }


@router.get("/{vocab_id}", response_model=TextbookVocabResponse)
async def get_vocab(vocab_id: int, db: AsyncSession = Depends(get_db)):
    """获取单个单词详情"""
    result = await db.execute(
        select(TextbookVocab).where(TextbookVocab.id == vocab_id)
    )
    vocab = result.scalar_one_or_none()

    if not vocab:
        raise HTTPException(status_code=404, detail="单词不存在")

    return TextbookVocabResponse.model_validate(vocab)


@router.post("", response_model=TextbookVocabResponse)
async def create_vocab(
    vocab_data: TextbookVocabCreate,
    db: AsyncSession = Depends(get_db)
):
    """添加新单词"""
    vocab = TextbookVocab(**vocab_data.model_dump())
    db.add(vocab)
    await db.commit()
    await db.refresh(vocab)
    return TextbookVocabResponse.model_validate(vocab)


@router.put("/{vocab_id}", response_model=TextbookVocabResponse)
async def update_vocab(
    vocab_id: int,
    vocab_data: TextbookVocabUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新单词"""
    result = await db.execute(
        select(TextbookVocab).where(TextbookVocab.id == vocab_id)
    )
    vocab = result.scalar_one_or_none()

    if not vocab:
        raise HTTPException(status_code=404, detail="单词不存在")

    # 更新字段
    update_data = vocab_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(vocab, key, value)

    await db.commit()
    await db.refresh(vocab)
    return TextbookVocabResponse.model_validate(vocab)


@router.delete("/{vocab_id}")
async def delete_vocab(vocab_id: int, db: AsyncSession = Depends(get_db)):
    """删除单词"""
    result = await db.execute(
        select(TextbookVocab).where(TextbookVocab.id == vocab_id)
    )
    vocab = result.scalar_one_or_none()

    if not vocab:
        raise HTTPException(status_code=404, detail="单词不存在")

    await db.delete(vocab)
    await db.commit()

    return {"message": "删除成功"}


@router.post("/batch-delete")
async def batch_delete(
    ids: List[int],
    db: AsyncSession = Depends(get_db)
):
    """批量删除单词"""
    result = await db.execute(
        select(TextbookVocab).where(TextbookVocab.id.in_(ids))
    )
    vocabs = result.scalars().all()

    if not vocabs:
        raise HTTPException(status_code=404, detail="未找到要删除的单词")

    for vocab in vocabs:
        await db.delete(vocab)

    await db.commit()

    return {"message": f"成功删除 {len(vocabs)} 个单词"}
