"""Seed the Aegis database with demo connection, monitored tables, and lineage."""

import hashlib
import json
from datetime import datetime, timedelta

from aegis.config import settings
from aegis.core.database import Base, sync_engine, SyncSessionLocal
from aegis.core.models import (
    ConnectionModel,
    MonitoredTableModel,
    SchemaSnapshotModel,
    LineageEdgeModel,
)

now = datetime.utcnow()
h = lambda n: now - timedelta(hours=n)


def main():
    Base.metadata.create_all(sync_engine)
    db = SyncSessionLocal()

    # ── Connection ────────────────────────────────────────────────
    conn = ConnectionModel(
        name="prod-warehouse",
        dialect="postgresql",
        connection_uri="postgresql://aegis:aegis@localhost:5433/aegis",
        is_active=True,
        created_at=h(72),
        updated_at=h(1),
    )
    db.add(conn)
    db.flush()

    # ── Monitored Tables ──────────────────────────────────────────
    tables_spec = [
        ("public", "orders",          60,  "fact"),
        ("public", "order_items",     60,  "fact"),
        ("public", "customers",       360, "dimension"),
        ("public", "products",        720, "dimension"),
        ("staging", "stg_payments",   30,  "staging"),
        ("staging", "stg_shipments",  30,  "staging"),
        ("analytics", "daily_revenue", 120, "fact"),
        ("analytics", "customer_ltv", 1440, "dimension"),
        ("raw", "raw_clickstream",    15,  "raw"),
        ("raw", "raw_events",         15,  "raw"),
    ]

    table_models = {}
    for schema, name, sla, _role in tables_spec:
        t = MonitoredTableModel(
            connection_id=conn.id,
            schema_name=schema,
            table_name=name,
            fully_qualified_name=f"{schema}.{name}",
            check_types='["schema", "freshness"]',
            freshness_sla_minutes=sla,
            created_at=h(48),
            updated_at=h(1),
        )
        db.add(t)
        db.flush()
        table_models[name] = t

    # ── Pre-drift schema snapshots (baselines) ────────────────────
    # These represent the ORIGINAL schema before 02-break.sql ran.
    # When the scanner takes its first snapshot of the CURRENT (post-drift)
    # state, it compares against these and detects the changes.

    orders_predrift = [
        {"name": "id", "type": "integer", "nullable": False, "ordinal": 1},
        {"name": "customer_id", "type": "integer", "nullable": False, "ordinal": 2},
        {"name": "total_amount", "type": "numeric", "nullable": False, "ordinal": 3},
        {"name": "status", "type": "character varying", "nullable": True, "ordinal": 4},
        {"name": "created_at", "type": "timestamp without time zone", "nullable": True, "ordinal": 5},
        {"name": "updated_at", "type": "timestamp without time zone", "nullable": True, "ordinal": 6},
    ]

    stg_payments_predrift = [
        {"name": "payment_id", "type": "integer", "nullable": False, "ordinal": 1},
        {"name": "order_id", "type": "integer", "nullable": False, "ordinal": 2},
        {"name": "amount", "type": "numeric", "nullable": False, "ordinal": 3},
        {"name": "method", "type": "character varying", "nullable": False, "ordinal": 4},
        {"name": "processed_at", "type": "timestamp without time zone", "nullable": True, "ordinal": 5},
        {"name": "updated_at", "type": "timestamp without time zone", "nullable": True, "ordinal": 6},
    ]

    customers_predrift = [
        {"name": "id", "type": "integer", "nullable": False, "ordinal": 1},
        {"name": "email", "type": "character varying", "nullable": False, "ordinal": 2},
        {"name": "name", "type": "character varying", "nullable": False, "ordinal": 3},
        {"name": "tier", "type": "character varying", "nullable": True, "ordinal": 4},
        {"name": "created_at", "type": "timestamp without time zone", "nullable": True, "ordinal": 5},
        {"name": "updated_at", "type": "timestamp without time zone", "nullable": True, "ordinal": 6},
    ]

    order_items_predrift = [
        {"name": "id", "type": "integer", "nullable": False, "ordinal": 1},
        {"name": "order_id", "type": "integer", "nullable": False, "ordinal": 2},
        {"name": "product_id", "type": "integer", "nullable": False, "ordinal": 3},
        {"name": "quantity", "type": "integer", "nullable": True, "ordinal": 4},
        {"name": "unit_price", "type": "numeric", "nullable": False, "ordinal": 5},
        {"name": "created_at", "type": "timestamp without time zone", "nullable": True, "ordinal": 6},
        {"name": "updated_at", "type": "timestamp without time zone", "nullable": True, "ordinal": 7},
    ]

    raw_events_predrift = [
        {"name": "id", "type": "integer", "nullable": False, "ordinal": 1},
        {"name": "event_type", "type": "character varying", "nullable": False, "ordinal": 2},
        {"name": "payload", "type": "jsonb", "nullable": True, "ordinal": 3},
        {"name": "received_at", "type": "timestamp without time zone", "nullable": True, "ordinal": 4},
        {"name": "updated_at", "type": "timestamp without time zone", "nullable": True, "ordinal": 5},
    ]

    daily_revenue_predrift = [
        {"name": "id", "type": "integer", "nullable": False, "ordinal": 1},
        {"name": "report_date", "type": "date", "nullable": False, "ordinal": 2},
        {"name": "total_revenue", "type": "numeric", "nullable": False, "ordinal": 3},
        {"name": "order_count", "type": "integer", "nullable": False, "ordinal": 4},
        {"name": "avg_order_value", "type": "numeric", "nullable": True, "ordinal": 5},
        {"name": "created_at", "type": "timestamp without time zone", "nullable": True, "ordinal": 6},
        {"name": "updated_at", "type": "timestamp without time zone", "nullable": True, "ordinal": 7},
    ]

    baselines = [
        ("orders", orders_predrift),
        ("stg_payments", stg_payments_predrift),
        ("customers", customers_predrift),
        ("order_items", order_items_predrift),
        ("raw_events", raw_events_predrift),
        ("daily_revenue", daily_revenue_predrift),
    ]
    for tname, cols in baselines:
        cols_json = json.dumps(cols, sort_keys=True)
        snap_hash = hashlib.sha256(cols_json.encode()).hexdigest()
        db.add(SchemaSnapshotModel(
            table_id=table_models[tname].id,
            columns=cols_json,
            snapshot_hash=snap_hash,
            captured_at=h(24),
        ))

    # ── Lineage Edges ─────────────────────────────────────────────
    edges = [
        ("raw.raw_events", "staging.stg_payments", "direct"),
        ("raw.raw_events", "staging.stg_shipments", "direct"),
        ("raw.raw_clickstream", "staging.stg_payments", "direct"),
        ("staging.stg_payments", "public.orders", "direct"),
        ("staging.stg_shipments", "public.orders", "direct"),
        ("public.orders", "public.order_items", "direct"),
        ("public.orders", "analytics.daily_revenue", "direct"),
        ("public.customers", "analytics.customer_ltv", "direct"),
        ("public.orders", "analytics.customer_ltv", "direct"),
        ("analytics.daily_revenue", "analytics.customer_ltv", "indirect"),
    ]
    for src, tgt, rel in edges:
        db.add(LineageEdgeModel(
            source_table=src,
            target_table=tgt,
            relationship_type=rel,
            confidence=0.95 if rel == "direct" else 0.7,
            first_seen_at=h(48),
            last_seen_at=h(1),
        ))

    db.commit()
    db.close()
    print("Demo data seeded successfully!")
    print(f"  - 1 connection (prod-warehouse -> postgresql://aegis:aegis@localhost:5433/aegis)")
    print(f"  - 10 monitored tables")
    print(f"  - 10 lineage edges")
    print("  (Anomalies, incidents, and snapshots are now detected live by the scanner)")


if __name__ == "__main__":
    main()
