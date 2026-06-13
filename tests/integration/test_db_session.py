# ============================================================
#  FOREMAN — tests/integration/test_db_session.py
#  Zweck: Engine-/Session-Lebenszyklus (init/get/commit/rollback/dispose).
#  Braucht eine erreichbare Test-DB.
# ============================================================
from __future__ import annotations

import pytest
from sqlalchemy import text

from foreman.config import Settings
from foreman.db import session as dbsession


async def test_session_lifecycle_and_commit(
    test_settings: Settings, _migrated_db: None
) -> None:
    await dbsession.dispose_engine()
    engine = dbsession.init_engine(test_settings)
    # idempotent: zweiter Aufruf liefert dieselbe Engine
    assert dbsession.init_engine(test_settings) is engine
    assert dbsession.get_sessionmaker() is not None

    gen = dbsession.get_session()
    session = await gen.__anext__()
    result = await session.execute(text("SELECT 1"))
    assert result.scalar() == 1
    # Generator erschöpfen → Commit-Pfad
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()

    await dbsession.dispose_engine()


async def test_session_rollback_on_error(
    test_settings: Settings, _migrated_db: None
) -> None:
    await dbsession.dispose_engine()
    dbsession.init_engine(test_settings)
    gen = dbsession.get_session()
    await gen.__anext__()
    # Fehler in den Generator werfen → Rollback-Pfad + Weiterreichen
    with pytest.raises(ValueError):
        await gen.athrow(ValueError("absichtlicher Fehler"))
    await dbsession.dispose_engine()
