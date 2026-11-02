import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.models import Creation, CreationLike, CreationType, UserUsage

pytestmark = pytest.mark.db


def make_creation(**overrides) -> Creation:
    values = {
        "user_id": "user_1",
        "prompt": "Write about AI",
        "content": "AI text",
        "type": CreationType.ARTICLE,
    }
    return Creation(**(values | overrides))


async def test_creation_gets_defaults_from_the_database(session):
    creation = make_creation()
    session.add(creation)
    await session.commit()
    await session.refresh(creation)

    assert creation.id is not None
    assert creation.publish is False
    assert creation.created_at is not None
    assert creation.created_at.tzinfo is not None


async def test_unknown_creation_type_is_rejected(session):
    session.add(make_creation(type="video"))

    with pytest.raises(IntegrityError, match="ck_creations_valid_type"):
        await session.commit()


async def test_a_user_can_like_a_creation_only_once(session):
    creation = make_creation()
    session.add(creation)
    await session.commit()

    session.add(CreationLike(creation_id=creation.id, user_id="user_2"))
    await session.commit()
    session.add(CreationLike(creation_id=creation.id, user_id="user_2"))

    with pytest.raises(IntegrityError, match="pk_creation_likes"):
        await session.commit()


async def test_deleting_a_creation_deletes_its_likes(session):
    creation = make_creation()
    session.add(creation)
    await session.commit()
    session.add_all(
        [
            CreationLike(creation_id=creation.id, user_id="user_2"),
            CreationLike(creation_id=creation.id, user_id="user_3"),
        ]
    )
    await session.commit()

    # Plain SQL, to prove the database itself cascades (not just SQLAlchemy).
    await session.execute(text("DELETE FROM creations WHERE id = :id"), {"id": creation.id})
    await session.commit()

    remaining = await session.scalar(select(func.count()).select_from(CreationLike))
    assert remaining == 0


async def test_like_for_missing_creation_is_rejected(session):
    session.add(CreationLike(creation_id=999, user_id="user_2"))

    with pytest.raises(IntegrityError, match="fk_creation_likes_creation_id_creations"):
        await session.commit()


async def test_free_usage_cannot_go_negative(session):
    session.add(UserUsage(user_id="user_1", free_usage=-1))

    with pytest.raises(IntegrityError, match="ck_user_usage_free_usage_not_negative"):
        await session.commit()


async def test_community_feed_query_uses_partial_index(session):
    # With an almost empty table Postgres prefers a full scan, so turn that off
    # for this transaction to check that the index *can* serve the feed query.
    await session.execute(text("SET LOCAL enable_seqscan = off"))
    explain = await session.scalar(
        text(
            "EXPLAIN (FORMAT JSON) "
            "SELECT * FROM creations WHERE publish ORDER BY created_at DESC LIMIT 20"
        )
    )

    assert "ix_creations_published_feed" in str(explain)
