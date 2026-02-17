"""Tests for lineage engine — SQL parsing and graph traversal."""

from aegis.core.lineage import LineageGraph
from aegis.utils.sql_parser import extract_lineage_edges


class TestSQLParser:
    def test_insert_select(self):
        sql = "INSERT INTO analytics.orders SELECT * FROM staging.orders"
        edges = extract_lineage_edges(sql, "postgres")

        assert len(edges) == 1
        assert edges[0].source == "staging.orders"
        assert edges[0].target == "analytics.orders"
        assert edges[0].confidence == 1.0

    def test_create_table_as_select(self):
        sql = "CREATE TABLE analytics.summary AS SELECT * FROM analytics.orders"
        edges = extract_lineage_edges(sql, "postgres")

        assert len(edges) == 1
        assert edges[0].source == "analytics.orders"
        assert edges[0].target == "analytics.summary"

    def test_multi_source_join(self):
        sql = (
            "INSERT INTO analytics.combined "
            "SELECT o.id, c.name FROM orders o JOIN customers c ON o.cust_id = c.id"
        )
        edges = extract_lineage_edges(sql, "postgres")

        assert len(edges) == 2
        sources = {e.source for e in edges}
        assert "orders" in sources
        assert "customers" in sources
        assert all(e.target == "analytics.combined" for e in edges)

    def test_select_only_no_edges(self):
        sql = "SELECT * FROM orders WHERE status = 'active'"
        edges = extract_lineage_edges(sql, "postgres")

        assert len(edges) == 0

    def test_unparseable_sql_returns_empty(self):
        sql = "THIS IS NOT VALID SQL %%% !!!"
        edges = extract_lineage_edges(sql, "postgres")

        assert len(edges) == 0

    def test_subquery_lower_confidence(self):
        sql = (
            "INSERT INTO analytics.report "
            "SELECT * FROM (SELECT id FROM staging.data) sub"
        )
        edges = extract_lineage_edges(sql, "postgres")

        # Should find staging.data as source
        data_edges = [e for e in edges if e.source == "staging.data"]
        assert len(data_edges) >= 1


class TestLineageGraph:
    def test_get_downstream(self, db, sample_lineage_edges):
        graph = LineageGraph(db)
        downstream = graph.get_downstream("staging.orders", depth=3)

        tables = {n["table"] for n in downstream}
        assert "analytics.orders" in tables
        assert "analytics.daily_revenue" in tables
        assert "analytics.customer_ltv" in tables

    def test_get_upstream(self, db, sample_lineage_edges):
        graph = LineageGraph(db)
        upstream = graph.get_upstream("analytics.orders", depth=3)

        tables = {n["table"] for n in upstream}
        assert "staging.orders" in tables
        assert "raw.orders" in tables

    def test_blast_radius(self, db, sample_lineage_edges):
        graph = LineageGraph(db)
        radius = graph.get_blast_radius("staging.orders")

        assert radius["total_affected"] >= 3
        assert radius["max_depth"] >= 2

    def test_get_path(self, db, sample_lineage_edges):
        graph = LineageGraph(db)
        path = graph.get_path("raw.orders", "analytics.daily_revenue")

        assert path is not None
        assert path[0] == "raw.orders"
        assert path[-1] == "analytics.daily_revenue"

    def test_no_path_returns_none(self, db, sample_lineage_edges):
        graph = LineageGraph(db)
        path = graph.get_path("analytics.daily_revenue", "raw.orders")

        # No reverse path in a DAG
        assert path is None

    def test_get_full_graph(self, db, sample_lineage_edges):
        graph = LineageGraph(db)
        full = graph.get_full_graph()

        assert len(full["nodes"]) == 5
        assert len(full["edges"]) == 4
