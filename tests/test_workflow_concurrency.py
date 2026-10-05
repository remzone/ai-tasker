"""Contended claims and decisions use real PostgreSQL sessions."""
import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from agent_kanban.db import _engine_for
from agent_kanban.models import TaskStatus
from agent_kanban.schemas import TaskCreate, TaskUpdate
from agent_kanban.services import create_task, claim_task, claim_review, request_review, submit_review, update_task


@pytest.mark.asyncio
async def test_concurrent_work_and_review_claims(session, db_url):
    factory = async_sessionmaker(_engine_for(db_url), class_=AsyncSession, expire_on_commit=False)
    task = await create_task(session, TaskCreate(title="race", status=TaskStatus.READY))

    async def work_claim(name):
        async with factory() as s:
            return await claim_task(s, task.id, name)
    results = await asyncio.gather(work_claim("one"), work_claim("two"))
    assert sum(r.ok for r in results) == 1
    owner = next(r.task.claimed_by for r in results if r.ok)
    async with factory() as s:
        await request_review(s, task.id, owner, "Implemented, tests pass")

    async def review_claim(name):
        async with factory() as s:
            return await claim_review(s, task.id, name)
    results = await asyncio.gather(review_claim("review-one"), review_claim("review-two"))
    assert sum(r.ok for r in results) == 1
    reviewer = next(r.task.reviewer for r in results if r.ok)

    async def review_decision():
        async with factory() as s:
            try:
                await submit_review(s, task.id, reviewer, "APPROVE", "All criteria verified")
                return True
            except ValueError:
                return False
    results = await asyncio.gather(review_decision(), review_decision())
    assert results.count(True) == 1


@pytest.mark.asyncio
async def test_assignment_checked_in_atomic_update(session, db_url):
    factory = async_sessionmaker(_engine_for(db_url), class_=AsyncSession, expire_on_commit=False)
    task = await create_task(session, TaskCreate(title="reserved", status=TaskStatus.READY))
    # Populate a stale identity map before a concurrent operator assignment.
    async with factory() as stale:
        from agent_kanban.services import get_task
        cached = await get_task(stale, task.id)
        assert cached.assigned_to is None
        async with factory() as fresh:
            await update_task(fresh, task.id, TaskUpdate(assigned_to="owner"))
        assert cached.assigned_to is None  # remains stale until atomic claim
        assert not (await claim_task(stale, task.id, "other")).ok
    assert (await claim_task(session, task.id, "owner")).ok
