"""Utility script to inspect stored programs."""

from __future__ import annotations

import argparse

from openevolve.database import Database, Program


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect the OpenEvolve SQLite database")
    parser.add_argument("--db-path", required=True)
    args = parser.parse_args()

    db = Database(args.db_path)
    with db.session() as session:
        programs = session.query(Program).all()
        for program in programs:
            print(f"[{program.id}] task={program.task} created={program.created_at}")


if __name__ == "__main__":
    main()
