import uuid

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def gen_uuid() -> str:
    return uuid.uuid4().hex
