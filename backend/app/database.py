"""
数据库连接和会话管理
"""
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

        # 迁移：添加 is_rare_meaning 列（如果不存在）
        # SQLite 不支持 IF NOT EXISTS，需要捕获异常
        try:
            await conn.execute(
                "ALTER TABLE cloze_points ADD COLUMN is_rare_meaning BOOLEAN DEFAULT 0"
            )
        except Exception:
            # 列已存在，忽略
            pass
