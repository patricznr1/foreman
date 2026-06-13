"""timescaledb + vector setup (Research §3-§4)

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-13

Richtet die Zeitreihen-/Vektor-Schicht ein (verbindliche DDL aus
docs/research/timescaledb-tuning-readings.md §4.1):
  - `vector`-Extension aktivieren + worker_notes.embedding (vector(1024)) ergänzen,
  - `timescaledb`-Extension aktivieren,
  - readings → Hypertable (1-Tages-Chunks),
  - Columnstore/Hypercore (segmentby=data_point_id, orderby=time DESC, after 7d),
  - Continuous Aggregates hierarchisch 1m → 1h → 1d (1m real-time) + Refresh-Policies,
  - Retention: readings 90d, readings_1m 1y, readings_1h 5y, readings_1d unbegrenzt.

Hinweis: Die Continuous Aggregates werden mit WITH NO DATA angelegt
(transaktionssicher); kein refresh_continuous_aggregate in der Migration.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- (1) Vektor-Extension + embedding-Spalte (semantische Suche, ohne Index in F2) ---
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.execute(
        "ALTER TABLE worker_notes ADD COLUMN IF NOT EXISTS embedding vector(1024);"
    )

    # --- (2) TimescaleDB-Extension ---
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")

    # --- (3) Hypertable: 1-Tages-Chunks (Research §3.1/§4.1) ---
    op.execute(
        "SELECT create_hypertable('readings', by_range('time', INTERVAL '1 day'), "
        "if_not_exists => TRUE);"
    )

    # --- (4) Columnstore / Hypercore (Research §3.2) ---
    op.execute(
        """
        ALTER TABLE readings SET (
          timescaledb.enable_columnstore = true,
          timescaledb.segmentby = 'data_point_id',
          timescaledb.orderby   = 'time DESC'
        );
        """
    )
    op.execute(
        "CALL add_columnstore_policy('readings', after => INTERVAL '7 days');"
    )

    # --- (5) Continuous Aggregates, hierarchisch 1m → 1h → 1d (Research §3.3) ---
    op.execute(
        """
        CREATE MATERIALIZED VIEW readings_1m
        WITH (timescaledb.continuous) AS
        SELECT
          time_bucket(INTERVAL '1 minute', time) AS bucket,
          data_point_id,
          avg(value)        AS avg_value,
          min(value)        AS min_value,
          max(value)        AS max_value,
          count(*)          AS n,
          last(value, time) AS last_value
        FROM readings
        GROUP BY bucket, data_point_id
        WITH NO DATA;
        """
    )
    op.execute(
        """
        CREATE MATERIALIZED VIEW readings_1h
        WITH (timescaledb.continuous) AS
        SELECT
          time_bucket(INTERVAL '1 hour', bucket) AS bucket,
          data_point_id,
          avg(avg_value) AS avg_value,
          min(min_value) AS min_value,
          max(max_value) AS max_value,
          sum(n)         AS n
        FROM readings_1m
        GROUP BY 1, 2
        WITH NO DATA;
        """
    )
    op.execute(
        """
        CREATE MATERIALIZED VIEW readings_1d
        WITH (timescaledb.continuous) AS
        SELECT
          time_bucket(INTERVAL '1 day', bucket) AS bucket,
          data_point_id,
          avg(avg_value) AS avg_value,
          min(min_value) AS min_value,
          max(max_value) AS max_value,
          sum(n)         AS n
        FROM readings_1h
        GROUP BY 1, 2
        WITH NO DATA;
        """
    )

    # 1-Minuten-CAGG mit Real-time an (Dashboard + Drift-Reasoner sehen jüngste Minute).
    op.execute(
        "ALTER MATERIALIZED VIEW readings_1m SET (timescaledb.materialized_only = false);"
    )

    # --- (6) Refresh-Policies (Research §3.3; end_offset > Einlauffenster) ---
    op.execute(
        """
        SELECT add_continuous_aggregate_policy('readings_1m',
          start_offset => INTERVAL '2 hours',
          end_offset   => INTERVAL '2 minutes',
          schedule_interval => INTERVAL '1 minute');
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy('readings_1h',
          start_offset => INTERVAL '2 days',
          end_offset   => INTERVAL '1 hour',
          schedule_interval => INTERVAL '10 minutes');
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy('readings_1d',
          start_offset => INTERVAL '15 days',
          end_offset   => INTERVAL '1 day',
          schedule_interval => INTERVAL '1 hour');
        """
    )

    # --- (7) Retention: Rohdaten kurz, Aggregate gestaffelt lang (Research §3.5) ---
    op.execute(
        "SELECT add_retention_policy('readings',    drop_after => INTERVAL '90 days');"
    )
    op.execute(
        "SELECT add_retention_policy('readings_1m', drop_after => INTERVAL '1 year');"
    )
    op.execute(
        "SELECT add_retention_policy('readings_1h', drop_after => INTERVAL '5 years');"
    )
    # readings_1d: KEINE Retention → unbegrenztes Langzeitgedächtnis.


def downgrade() -> None:
    # Best-effort-Rückbau: Policies + CAGGs entfernen, embedding-Spalte droppen.
    # Die Hypertable-Umwandlung von `readings` wird nicht zurückgenommen
    # (Test-Teardown nutzt ohnehin DROP SCHEMA … CASCADE).
    for view in ("readings_1d", "readings_1h", "readings_1m"):
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS {view} CASCADE;")
    op.execute("ALTER TABLE worker_notes DROP COLUMN IF EXISTS embedding;")
