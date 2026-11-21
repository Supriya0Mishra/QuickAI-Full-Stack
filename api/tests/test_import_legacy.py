"""The legacy import script, against a copy of the old Node schema."""

import pytest
from sqlalchemy import func, select, text

from app.models import Creation, CreationLike
from app.scripts.import_legacy import import_legacy

pytestmark = pytest.mark.db

# The old table exactly as the Node server's README creates it, in its own schema.
LEGACY_TABLE_SQL = """
CREATE TABLE legacy.creations (
  id SERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  prompt TEXT NOT NULL,
  content TEXT NOT NULL,
  type TEXT NOT NULL,
  publish BOOLEAN DEFAULT FALSE,
  likes TEXT[] DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
)
"""

LEGACY_ROWS_SQL = """
INSERT INTO legacy.creations (id, user_id, prompt, content, type, publish, likes) VALUES
  (1, 'user_a', 'p1', 'article text', 'article',       true,  '{user_b,user_c}'),
  (2, 'user_a', 'p2', 'titles',       'blog-title',    false, '{}'),
  (5, 'user_b', 'p3', 'https://img',  'image',         true,  '{user_a,user_a,user_c}'),
  (6, 'user_c', 'p4', 'review',       'resume-review', false, NULL),
  (7, 'user_c', 'p5', 'old thing',    'video',         false, '{user_a}')
"""


@pytest.fixture
async def legacy(engine, session):
    """Creates legacy.creations with sample rows; drops it afterwards."""
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS legacy CASCADE"))
        await conn.execute(text("CREATE SCHEMA legacy"))
        await conn.execute(text(LEGACY_TABLE_SQL))
        await conn.execute(text(LEGACY_ROWS_SQL))
    yield "legacy.creations"
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA legacy CASCADE"))


async def count(session, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))


async def test_dry_run_counts_but_writes_nothing(migrated_db, legacy, session):
    report = await import_legacy(migrated_db, migrated_db, legacy, dry_run=True)

    assert report.source_rows == 5
    assert report.likes_found == 4  # duplicate like and the skipped row's like not counted
    assert report.skipped_ids == [7]
    assert await count(session, Creation) == 0


async def test_import_copies_creations_and_splits_likes(migrated_db, legacy, session):
    report = await import_legacy(migrated_db, migrated_db, legacy)

    assert report.creations_inserted == 4
    assert report.likes_inserted == 4
    assert report.skipped_ids == [7]  # 'video' is not a valid type

    ids = (await session.scalars(select(Creation.id).order_by(Creation.id))).all()
    assert ids == [1, 2, 5, 6]  # original ids kept

    image_likes = (
        await session.scalars(
            select(CreationLike.user_id)
            .where(CreationLike.creation_id == 5)
            .order_by(CreationLike.user_id)
        )
    ).all()
    assert image_likes == ["user_a", "user_c"]  # duplicate 'user_a' collapsed


async def test_running_the_import_twice_adds_nothing(migrated_db, legacy, session):
    await import_legacy(migrated_db, migrated_db, legacy)

    second = await import_legacy(migrated_db, migrated_db, legacy)

    assert second.creations_inserted == 0
    assert second.likes_inserted == 0
    assert await count(session, Creation) == 4


async def test_new_creations_get_ids_after_imported_ones(migrated_db, legacy, session):
    await import_legacy(migrated_db, migrated_db, legacy)

    creation = Creation(user_id="user_d", prompt="new", content="new", type="article")
    session.add(creation)
    await session.commit()

    assert creation.id == 7  # highest imported id was 6


async def test_table_name_must_be_a_plain_identifier():
    with pytest.raises(ValueError, match="Invalid table name"):
        await import_legacy("postgresql://x@h/d", "postgresql://x@h/d", "creations; DROP TABLE x")
