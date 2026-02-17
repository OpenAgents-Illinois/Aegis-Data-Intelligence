"""Initial schema — all Aegis tables.

Revision ID: 001
Revises:
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # connections
    op.create_table(
        "connections",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String, nullable=False, unique=True),
        sa.Column("dialect", sa.String, nullable=False),
        sa.Column("connection_uri", sa.String, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # monitored_tables
    op.create_table(
        "monitored_tables",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "connection_id",
            sa.Integer,
            sa.ForeignKey("connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("schema_name", sa.String, nullable=False),
        sa.Column("table_name", sa.String, nullable=False),
        sa.Column("fully_qualified_name", sa.String, nullable=False),
        sa.Column(
            "check_types",
            sa.Text,
            nullable=False,
            server_default='["schema", "freshness"]',
        ),
        sa.Column("freshness_sla_minutes", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("connection_id", "schema_name", "table_name"),
    )

    # schema_snapshots
    op.create_table(
        "schema_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "table_id",
            sa.Integer,
            sa.ForeignKey("monitored_tables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("columns", sa.Text, nullable=False),
        sa.Column("snapshot_hash", sa.String, nullable=False),
        sa.Column("captured_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_snapshots_table_id", "schema_snapshots", ["table_id", "captured_at"])

    # anomalies
    op.create_table(
        "anomalies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "table_id",
            sa.Integer,
            sa.ForeignKey("monitored_tables.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("severity", sa.String, nullable=False),
        sa.Column("detail", sa.Text, nullable=False),
        sa.Column("detected_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_anomalies_table_type", "anomalies", ["table_id", "type", "detected_at"])

    # incidents
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("anomaly_id", sa.Integer, sa.ForeignKey("anomalies.id"), nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="open"),
        sa.Column("diagnosis", sa.Text, nullable=True),
        sa.Column("blast_radius", sa.Text, nullable=True),
        sa.Column("remediation", sa.Text, nullable=True),
        sa.Column("severity", sa.String, nullable=False),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
        sa.Column("resolved_by", sa.String, nullable=True),
        sa.Column("dismiss_reason", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_incidents_status", "incidents", ["status", "severity", "created_at"])

    # lineage_edges
    op.create_table(
        "lineage_edges",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_table", sa.String, nullable=False),
        sa.Column("target_table", sa.String, nullable=False),
        sa.Column("relationship_type", sa.String, nullable=False, server_default="direct"),
        sa.Column("query_hash", sa.String, nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("first_seen_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source_table", "target_table"),
    )
    op.create_index("idx_lineage_source", "lineage_edges", ["source_table"])
    op.create_index("idx_lineage_target", "lineage_edges", ["target_table"])


def downgrade() -> None:
    op.drop_table("lineage_edges")
    op.drop_table("incidents")
    op.drop_table("anomalies")
    op.drop_table("schema_snapshots")
    op.drop_table("monitored_tables")
    op.drop_table("connections")
