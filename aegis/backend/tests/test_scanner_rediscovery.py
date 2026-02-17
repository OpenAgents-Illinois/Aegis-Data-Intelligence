"""Tests for scanner rediscovery integration."""

from unittest.mock import MagicMock, patch

from aegis.services.scanner import _run_rediscovery


def test_run_rediscovery_calls_investigator():
    with patch("aegis.services.scanner.SyncSessionLocal") as MockSession, \
         patch("aegis.services.scanner.WarehouseConnector") as MockConnector, \
         patch("aegis.services.scanner.Investigator") as MockInvestigator, \
         patch("aegis.services.notifier.notifier") as mock_notifier:

        mock_db = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_db)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        # Mock one active connection
        from aegis.core.models import ConnectionModel
        mock_conn = MagicMock(spec=ConnectionModel)
        mock_conn.id = 1
        mock_conn.name = "test"
        mock_conn.connection_uri = "postgresql://x"
        mock_conn.dialect = "postgresql"
        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_conn]

        mock_inv = MockInvestigator.return_value
        mock_inv.rediscover.return_value = []

        _run_rediscovery()

        mock_inv.rediscover.assert_called_once()


def test_run_rediscovery_broadcasts_deltas():
    with patch("aegis.services.scanner.SyncSessionLocal") as MockSession, \
         patch("aegis.services.scanner.WarehouseConnector") as MockConnector, \
         patch("aegis.services.scanner.Investigator") as MockInvestigator, \
         patch("aegis.services.notifier.notifier") as mock_notifier:

        mock_db = MagicMock()
        MockSession.return_value.__enter__ = MagicMock(return_value=mock_db)
        MockSession.return_value.__exit__ = MagicMock(return_value=False)

        mock_conn = MagicMock()
        mock_conn.id = 1
        mock_conn.name = "test"
        mock_conn.connection_uri = "postgresql://x"
        mock_conn.dialect = "postgresql"
        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_conn]

        mock_delta = MagicMock()
        mock_inv = MockInvestigator.return_value
        mock_inv.rediscover.return_value = [mock_delta, mock_delta]

        _run_rediscovery()

        mock_notifier.broadcast.assert_called_once_with(
            "discovery.update", {"total_deltas": 2}
        )
