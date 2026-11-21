"""Copy data from the old Node server's database into the new schema.

Old schema (one table):   creations(..., likes TEXT[])
New schema:               creations + creation_likes (one row per like)

Safe to run more than once: existing rows are skipped, not duplicated.
IDs are kept, so links to existing creations keep working.

Usage (from api/):
    uv run python -m app.scripts.import_legacy --source "$LEGACY_DATABASE_URL" --dry-run
    uv run python -m app.scripts.import_legacy --source "$LEGACY_DATABASE_URL"

The target is DATABASE_URL from the app settings. Run `alembic upgrade head` first.
"""

import argparse
import asyncio
import os
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.urls import create_engine
from app.models import CREATION_TYPES, Creation, CreationLike

BATCH_SIZE = 500
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


@dataclass
class ImportReport:
    source_rows: int = 0
    creations_inserted: int = 0
    likes_found: int = 0
    likes_inserted: int = 0
    skipped_ids: list[int] = field(default_factory=list)


def _batches(items: list[Any], size: int = BATCH_SIZE):
    for start in range(0, len(items), size):
        yield items[start : start + size]


async def import_legacy(
    source_url: str,
    target_url: str,
    source_table: str = "creations",
    dry_run: bool = False,
) -> ImportReport:
    # The table name is put into SQL, so only allow plain identifiers.
    if not _IDENTIFIER.match(source_table):
        raise ValueError(f"Invalid table name: {source_table!r}")

    report = ImportReport()

    source = create_engine(source_url, poolclass=NullPool)
    try:
        async with source.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT id, user_id, prompt, content, type, publish, likes, "
                    "COALESCE(created_at, now()) AS created_at, "
                    "COALESCE(updated_at, created_at, now()) AS updated_at "
                    f"FROM {source_table} ORDER BY id"
                )
            )
            rows = result.mappings().all()
    finally:
        await source.dispose()

    report.source_rows = len(rows)

    creations: list[dict[str, Any]] = []
    likes: set[tuple[int, str]] = set()
    for row in rows:
        if row["type"] not in CREATION_TYPES:
            report.skipped_ids.append(row["id"])
            continue
        creations.append(
            {
                "id": row["id"],
                "user_id": row["user_id"],
                "prompt": row["prompt"],
                "content": row["content"],
                "type": row["type"],
                "publish": bool(row["publish"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
        # A set removes duplicate likes in the old array.
        for user_id in row["likes"] or []:
            likes.add((row["id"], user_id))

    report.likes_found = len(likes)
    if dry_run:
        return report

    target = create_engine(target_url, poolclass=NullPool)
    try:
        async with target.begin() as conn:
            for batch in _batches(creations):
                inserted = await conn.execute(
                    insert(Creation)
                    .values(batch)
                    .on_conflict_do_nothing(index_elements=["id"])
                    .returning(Creation.id)
                )
                report.creations_inserted += len(inserted.all())

            like_rows = [{"creation_id": cid, "user_id": uid} for cid, uid in sorted(likes)]
            for batch in _batches(like_rows):
                inserted = await conn.execute(
                    insert(CreationLike)
                    .values(batch)
                    .on_conflict_do_nothing()
                    .returning(CreationLike.creation_id)
                )
                report.likes_inserted += len(inserted.all())

            # IDs were copied as-is, so move the id sequence past the highest one.
            # Otherwise the next new creation would collide with an imported id.
            max_id = (await conn.execute(select(func.max(Creation.id)))).scalar()
            if max_id is not None:
                await conn.execute(
                    text("SELECT setval(pg_get_serial_sequence('creations', 'id'), :max_id)"),
                    {"max_id": max_id},
                )
    finally:
        await target.dispose()

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--source",
        default=os.environ.get("LEGACY_DATABASE_URL"),
        help="Old database URL (default: LEGACY_DATABASE_URL)",
    )
    parser.add_argument("--table", default="creations", help="Old table name")
    parser.add_argument("--dry-run", action="store_true", help="Count rows, write nothing")
    args = parser.parse_args()

    if not args.source:
        parser.error("Pass --source or set LEGACY_DATABASE_URL")

    report = asyncio.run(
        import_legacy(args.source, get_settings().database_url, args.table, args.dry_run)
    )

    # URLs are never printed: they contain passwords.
    mode = "DRY RUN (nothing written)" if args.dry_run else "Import finished"
    print(mode)
    print(f"  rows in old table:   {report.source_rows}")
    print(f"  likes in old table:  {report.likes_found}")
    if not args.dry_run:
        print(f"  creations inserted:  {report.creations_inserted}")
        print(f"  likes inserted:      {report.likes_inserted}")
    if report.skipped_ids:
        print(f"  skipped (unknown type): ids {report.skipped_ids}")


if __name__ == "__main__":
    main()
