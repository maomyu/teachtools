"""
数据库连接和会话管理
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.config import settings

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.LOG_LEVEL == "DEBUG",
    future=True
)

# 创建异步会话工厂
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# 为SSE等场景导出的会话工厂别名
async_session_factory = async_session

# 声明基类
Base = declarative_base()


async def get_db():
    """获取数据库会话的依赖函数"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_exam_papers_nullable_metadata(conn)

        # 迁移：添加 is_rare_meaning 列（如果不存在）
        # SQLite 不支持 IF NOT EXISTS，需要捕获异常
        try:
            await conn.execute(
                "ALTER TABLE cloze_points ADD COLUMN is_rare_meaning BOOLEAN DEFAULT 0"
            )
        except Exception:
            # 列已存在，忽略
            pass


async def _migrate_exam_papers_nullable_metadata(conn):
    """将 exam_papers 的 year/grade 迁移为可空，兼容历史文件名解析失败场景。"""
    result = await conn.execute(text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='exam_papers'"
    ))
    row = result.fetchone()
    if row is None or not row[0]:
        return

    create_sql = row[0]
    table_info = await conn.execute(text("PRAGMA table_info(exam_papers)"))
    columns = {item[1]: item for item in table_info.fetchall()}

    year_notnull = bool(columns.get("year", [None, None, None, 0])[3])
    grade_notnull = bool(columns.get("grade", [None, None, None, 0])[3])
    grade_check_strict = "grade IN ('初一', '初二', '初三')" in create_sql and "grade IS NULL OR" not in create_sql

    if not (year_notnull or grade_notnull or grade_check_strict):
        return

    await conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    await conn.exec_driver_sql("DROP TABLE IF EXISTS exam_papers_new")
    await conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS exam_papers_new (
            id INTEGER NOT NULL PRIMARY KEY,
            filename VARCHAR(255) NOT NULL,
            original_path VARCHAR(500),
            year INTEGER,
            region VARCHAR(50),
            school VARCHAR(100),
            grade VARCHAR(20),
            semester VARCHAR(10),
            season VARCHAR(20),
            exam_type VARCHAR(20),
            version VARCHAR(20),
            import_status VARCHAR(20),
            parse_strategy VARCHAR(20),
            confidence FLOAT,
            error_message TEXT,
            created_at DATETIME,
            updated_at DATETIME,
            CONSTRAINT ck_papers_grade CHECK (grade IS NULL OR grade IN ('初一', '初二', '初三')),
            CONSTRAINT ck_papers_status CHECK (import_status IN ('pending', 'processing', 'completed', 'failed', 'partial'))
        )
        """
    )
    await conn.exec_driver_sql(
        """
        INSERT INTO exam_papers_new (
            id, filename, original_path, year, region, school, grade, semester,
            season, exam_type, version, import_status, parse_strategy, confidence,
            error_message, created_at, updated_at
        )
        SELECT
            id, filename, original_path, year, region, school, grade, semester,
            season, exam_type, version, import_status, parse_strategy, confidence,
            error_message, created_at, updated_at
        FROM exam_papers
        """
    )
    await conn.exec_driver_sql("DROP TABLE exam_papers")
    await conn.exec_driver_sql("ALTER TABLE exam_papers_new RENAME TO exam_papers")
    await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
