"""SQLite persistence using SQLModel."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from sqlmodel import Field, Session, SQLModel, create_engine, select


class Program(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task: str
    source: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Evaluation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    program_id: int = Field(foreign_key="program.id")
    score_primary: float
    score_secondary: float | None = None
    metadata: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Database:
    """Thin wrapper around SQLModel sessions."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.engine = create_engine(f"sqlite:///{self.path}", echo=False)
        SQLModel.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with Session(self.engine) as session:
            yield session

    def add_program(self, task: str, source: str) -> Program:
        with self.session() as session:
            program = Program(task=task, source=source)
            session.add(program)
            session.commit()
            session.refresh(program)
            return program

    def latest_program(self, task: str) -> Program | None:
        with self.session() as session:
            statement = select(Program).where(Program.task == task).order_by(Program.id.desc())
            return session.exec(statement).first()
