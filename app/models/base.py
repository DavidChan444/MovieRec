"""
基础模型类
"""
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.sql import func
from app.data.database import Base


class BaseModel(Base):
    """抽象基础模型"""
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())