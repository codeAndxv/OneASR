"""声明 Base 类，所有 ORM 模型继承此类。"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
