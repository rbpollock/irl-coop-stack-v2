"""SQLAlchemy metadata 與 declarative base。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM model 共用的 declarative base。"""

