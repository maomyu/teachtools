"""
数据库连接和会话管理
"""
from sqlalchemy import text, event
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from app.config import settings
from app.writing_category_registry import flatten_writing_categories

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.LOG_LEVEL == "DEBUG",
    future=True
)


if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.close()

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
        await _migrate_writing_schema(conn)
        await _migrate_handout_fields(conn)

        # 迁移：添加 is_rare_meaning 列（如果不存在）
        # SQLite 不支持 IF NOT EXISTS，需要捕获异常
        try:
            await conn.exec_driver_sql(
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


async def _migrate_writing_schema(conn):
    """迁移作文分类树相关结构并预置分类数据。"""
    await conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS writing_categories (
            id INTEGER NOT NULL PRIMARY KEY,
            code VARCHAR(80) NOT NULL UNIQUE,
            name VARCHAR(100) NOT NULL,
            level INTEGER NOT NULL,
            parent_id INTEGER,
            path VARCHAR(255) NOT NULL,
            template_key VARCHAR(100) NOT NULL,
            prompt_hint TEXT,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME,
            updated_at DATETIME,
            FOREIGN KEY(parent_id) REFERENCES writing_categories(id)
        )
        """
    )

    await _ensure_column(conn, "writing_tasks", "group_category_id", "INTEGER")
    await _ensure_column(conn, "writing_tasks", "major_category_id", "INTEGER")
    await _ensure_column(conn, "writing_tasks", "category_id", "INTEGER")
    await _ensure_column(conn, "writing_tasks", "category_confidence", "FLOAT DEFAULT 0")
    await _ensure_column(conn, "writing_tasks", "category_reasoning", "TEXT")

    await _ensure_column(conn, "writing_templates", "category_id", "INTEGER")
    await _ensure_column(conn, "writing_templates", "template_key", "VARCHAR(100)")
    await _ensure_column(conn, "writing_templates", "template_schema_json", "TEXT")
    await _ensure_column(conn, "writing_templates", "template_version", "INTEGER DEFAULT 1")
    await _ensure_column(conn, "writing_templates", "quality_status", "VARCHAR(20) DEFAULT 'pending'")
    await _ensure_column(conn, "writing_templates", "representative_sample_content", "TEXT")
    await _ensure_column(conn, "writing_templates", "representative_translation", "TEXT")
    await _ensure_column(conn, "writing_templates", "representative_rendered_slots_json", "TEXT")
    await _ensure_column(conn, "writing_templates", "representative_word_count", "INTEGER")
    await _ensure_column(conn, "writing_templates", "updated_at", "DATETIME")
    await _ensure_column(conn, "writing_samples", "rendered_slots_json", "TEXT")
    await _ensure_column(conn, "writing_samples", "template_version", "INTEGER DEFAULT 1")
    await _ensure_column(conn, "writing_samples", "generation_mode", "VARCHAR(30) DEFAULT 'slot_fill'")
    await _ensure_column(conn, "writing_samples", "quality_status", "VARCHAR(20) DEFAULT 'pending'")

    await _seed_writing_categories(conn)
    await _dedupe_writing_templates(conn)
    await _dedupe_writing_samples(conn)
    await _ensure_writing_indexes(conn)


async def _migrate_handout_fields(conn):
    """迁移：添加讲义生成状态字段"""
    await _ensure_column(conn, "exam_papers", "reading_handout_at", "DATETIME")
    await _ensure_column(conn, "exam_papers", "cloze_handout_at", "DATETIME")
    await _ensure_column(conn, "exam_papers", "writing_handout_at", "DATETIME")


async def _ensure_column(conn, table_name: str, column_name: str, definition: str) -> None:
    """为 SQLite 表补充缺失列。"""
    result = await conn.execute(text(f"PRAGMA table_info({table_name})"))
    columns = {row[1] for row in result.fetchall()}
    if column_name in columns:
        return

    await conn.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


async def _dedupe_writing_templates(conn) -> None:
    """收敛为一子类一模板，保留最新一条。"""
    await conn.exec_driver_sql(
        """
        DELETE FROM writing_templates
        WHERE category_id IS NOT NULL
          AND id NOT IN (
            SELECT MAX(id)
            FROM writing_templates
            WHERE category_id IS NOT NULL
            GROUP BY category_id
          )
        """
    )
    await conn.exec_driver_sql(
        """
        UPDATE writing_templates
        SET template_version = COALESCE(NULLIF(template_version, 0), 1)
        WHERE template_version IS NULL OR template_version = 0
        """
    )
    await conn.exec_driver_sql(
        """
        UPDATE writing_templates
        SET quality_status = COALESCE(NULLIF(quality_status, ''), 'pending')
        WHERE quality_status IS NULL OR quality_status = ''
        """
    )


async def _dedupe_writing_samples(conn) -> None:
    """收敛为一题一篇正式范文，保留最新一条。"""
    await conn.exec_driver_sql(
        """
        DELETE FROM writing_samples
        WHERE task_id IS NOT NULL
          AND id NOT IN (
            SELECT MAX(id)
            FROM writing_samples
            WHERE task_id IS NOT NULL
            GROUP BY task_id
          )
        """
    )
    await conn.exec_driver_sql(
        """
        UPDATE writing_samples
        SET template_version = COALESCE(NULLIF(template_version, 0), 1)
        WHERE template_version IS NULL OR template_version = 0
        """
    )
    await conn.exec_driver_sql(
        """
        UPDATE writing_samples
        SET generation_mode = COALESCE(NULLIF(generation_mode, ''), 'slot_fill'),
            quality_status = COALESCE(NULLIF(quality_status, ''), 'pending')
        WHERE generation_mode IS NULL OR generation_mode = '' OR quality_status IS NULL OR quality_status = ''
        """
    )


async def _ensure_writing_indexes(conn) -> None:
    """补充写作模块唯一索引。"""
    await conn.exec_driver_sql(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_writing_templates_category_unique
        ON writing_templates(category_id)
        WHERE category_id IS NOT NULL
        """
    )
    await conn.exec_driver_sql(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_writing_samples_task_unique
        ON writing_samples(task_id)
        WHERE task_id IS NOT NULL
        """
    )


async def _seed_writing_categories(conn) -> None:
    """按 code 幂等写入/更新预置分类树。"""
    rows = flatten_writing_categories()
    code_to_id: dict[str, int] = {}

    for level in (1, 2, 3):
        for row in [item for item in rows if item["level"] == level]:
            parent_id = code_to_id.get(row["parent_code"])
            exists_result = await conn.execute(
                text("SELECT id FROM writing_categories WHERE code = :code"),
                {"code": row["code"]},
            )
            existing_id = exists_result.scalar_one_or_none()

            if existing_id is None:
                await conn.execute(
                    text(
                        """
                        INSERT INTO writing_categories (
                            code, name, level, parent_id, path, template_key, prompt_hint,
                            sort_order, is_active, created_at, updated_at
                        )
                        VALUES (
                            :code, :name, :level, :parent_id, :path, :template_key, :prompt_hint,
                            :sort_order, :is_active, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                        """
                    ),
                    {
                        "code": row["code"],
                        "name": row["name"],
                        "level": row["level"],
                        "parent_id": parent_id,
                        "path": row["path"],
                        "template_key": row["template_key"],
                        "prompt_hint": row["prompt_hint"],
                        "sort_order": row["sort_order"],
                        "is_active": 1 if row["is_active"] else 0,
                    },
                )
            else:
                await conn.execute(
                    text(
                        """
                        UPDATE writing_categories
                        SET
                            name = :name,
                            level = :level,
                            parent_id = :parent_id,
                            path = :path,
                            template_key = :template_key,
                            prompt_hint = :prompt_hint,
                            sort_order = :sort_order,
                            is_active = :is_active,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE code = :code
                        """
                    ),
                    {
                        "code": row["code"],
                        "name": row["name"],
                        "level": row["level"],
                        "parent_id": parent_id,
                        "path": row["path"],
                        "template_key": row["template_key"],
                        "prompt_hint": row["prompt_hint"],
                        "sort_order": row["sort_order"],
                        "is_active": 1 if row["is_active"] else 0,
                    },
                )
            category_id_result = await conn.execute(
                text("SELECT id FROM writing_categories WHERE code = :code"),
                {"code": row["code"]},
            )
            code_to_id[row["code"]] = category_id_result.scalar_one()
