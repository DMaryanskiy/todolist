import os
from typing import AsyncIterable

import sqlalchemy
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.curdir, '.env'))

SQLACHEMY_DATABASE_URL = f"postgresql+asyncpg://{os.environ.get('DB_USER')}:{os.environ.get('DB_PASSWORD')}@{os.environ.get('DB_HOST')}:{os.environ.get('DB_PORT')}/{os.environ.get('DB_NAME')}"

engine = create_async_engine(SQLACHEMY_DATABASE_URL, echo=True, future=True)
metadata = sqlalchemy.MetaData()

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

async def get_session() -> AsyncIterable[AsyncSession]:
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    async with async_session() as session:
        yield session

async def session_commit(error, exception: HTTPException, session: AsyncSession) -> None:
    try:
        await session.commit()
    except error as _:
        await session.rollback()
        raise exception
