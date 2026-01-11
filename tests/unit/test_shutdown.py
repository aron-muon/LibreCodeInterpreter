"""Unit tests for graceful shutdown handling."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.shutdown import (
    GracefulShutdownHandler,
    cleanup_active_containers,
    cleanup_services,
    flush_logs_and_metrics,
    setup_graceful_shutdown,
    shutdown_handler,
)


class TestGracefulShutdownHandlerInit:
    """Tests for GracefulShutdownHandler initialization."""

    def test_init(self):
        """Test handler initialization."""
        handler = GracefulShutdownHandler()

        assert handler._shutdown_callbacks == []
        assert handler._is_shutting_down is False


class TestAddShutdownCallback:
    """Tests for add_shutdown_callback method."""

    def test_add_single_callback(self):
        """Test adding a single callback."""
        handler = GracefulShutdownHandler()

        async def my_callback():
            pass

        handler.add_shutdown_callback(my_callback)

        assert len(handler._shutdown_callbacks) == 1
        assert handler._shutdown_callbacks[0] == my_callback

    def test_add_multiple_callbacks(self):
        """Test adding multiple callbacks."""
        handler = GracefulShutdownHandler()

        async def callback1():
            pass

        async def callback2():
            pass

        handler.add_shutdown_callback(callback1)
        handler.add_shutdown_callback(callback2)

        assert len(handler._shutdown_callbacks) == 2


class TestShutdown:
    """Tests for shutdown method."""

    @pytest.mark.asyncio
    async def test_shutdown_executes_callbacks(self):
        """Test that shutdown executes all callbacks."""
        handler = GracefulShutdownHandler()
        call_order = []

        async def callback1():
            call_order.append(1)

        async def callback2():
            call_order.append(2)

        handler.add_shutdown_callback(callback1)
        handler.add_shutdown_callback(callback2)

        await handler.shutdown()

        # Callbacks should be executed in reverse order
        assert call_order == [2, 1]

    @pytest.mark.asyncio
    async def test_shutdown_only_runs_once(self):
        """Test that shutdown only runs once."""
        handler = GracefulShutdownHandler()
        call_count = 0

        async def my_callback():
            nonlocal call_count
            call_count += 1

        handler.add_shutdown_callback(my_callback)

        await handler.shutdown()
        await handler.shutdown()  # Second call should be no-op

        assert call_count == 1
        assert handler._is_shutting_down is True

    @pytest.mark.asyncio
    async def test_shutdown_handles_callback_exception(self):
        """Test that shutdown handles callback exceptions."""
        handler = GracefulShutdownHandler()
        successful_callbacks = []

        async def failing_callback():
            raise Exception("Callback failed")

        async def successful_callback():
            successful_callbacks.append(1)

        handler.add_shutdown_callback(successful_callback)
        handler.add_shutdown_callback(failing_callback)

        # Should not raise
        await handler.shutdown()

        # Successful callback should still run
        assert len(successful_callbacks) == 1

    @pytest.mark.asyncio
    async def test_shutdown_handles_timeout(self):
        """Test that shutdown handles callback timeout."""
        handler = GracefulShutdownHandler()

        async def slow_callback():
            await asyncio.sleep(100)  # Very slow

        handler.add_shutdown_callback(slow_callback)

        # Use a shorter timeout for testing - but the real code has 10s timeout
        # Just verify it doesn't hang forever
        with patch("src.utils.shutdown.asyncio.wait_for", new_callable=AsyncMock) as mock_wait:
            mock_wait.side_effect = TimeoutError()

            # Should not raise
            await handler.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_empty_callbacks(self):
        """Test shutdown with no callbacks."""
        handler = GracefulShutdownHandler()

        # Should not raise
        await handler.shutdown()

        assert handler._is_shutting_down is True


class TestCleanupServices:
    """Tests for cleanup_services function."""

    @pytest.mark.asyncio
    async def test_cleanup_services_success(self):
        """Test successful service cleanup."""
        mock_session_service = AsyncMock()
        mock_session_service.close = AsyncMock()

        with patch("src.dependencies.services.get_session_service", return_value=mock_session_service):
            with patch("src.utils.shutdown.metrics_collector") as mock_metrics:
                mock_metrics.stop = AsyncMock()
                with patch("src.utils.shutdown.health_service") as mock_health:
                    mock_health.close = AsyncMock()

                    await cleanup_services()

        mock_session_service.close.assert_called_once()
        mock_metrics.stop.assert_called_once()
        mock_health.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_services_handles_import_error(self):
        """Test cleanup handles import error - by raising import error during import."""
        with patch.dict("sys.modules", {"src.dependencies.services": None}):
            with patch("src.utils.shutdown.metrics_collector") as mock_metrics:
                mock_metrics.stop = AsyncMock()
                with patch("src.utils.shutdown.health_service") as mock_health:
                    mock_health.close = AsyncMock()

                    # Should not raise - handles import error gracefully
                    await cleanup_services()

    @pytest.mark.asyncio
    async def test_cleanup_services_handles_timeout(self):
        """Test cleanup handles timeout."""
        mock_session_service = AsyncMock()

        async def slow_close():
            raise TimeoutError()

        mock_session_service.close = slow_close

        with patch("src.dependencies.services.get_session_service", return_value=mock_session_service):
            with patch("src.utils.shutdown.metrics_collector") as mock_metrics:
                mock_metrics.stop = AsyncMock()
                with patch("src.utils.shutdown.health_service") as mock_health:
                    mock_health.close = AsyncMock()

                    # Should not raise
                    await cleanup_services()

    @pytest.mark.asyncio
    async def test_cleanup_services_handles_error(self):
        """Test cleanup handles general errors."""
        mock_session_service = AsyncMock()
        mock_session_service.close = AsyncMock(side_effect=Exception("Service error"))

        with patch("src.dependencies.services.get_session_service", return_value=mock_session_service):
            with patch("src.utils.shutdown.metrics_collector") as mock_metrics:
                mock_metrics.stop = AsyncMock()
                with patch("src.utils.shutdown.health_service") as mock_health:
                    mock_health.close = AsyncMock()

                    # Should not raise
                    await cleanup_services()


class TestCleanupActiveContainers:
    """Tests for cleanup_active_containers function."""

    @pytest.mark.asyncio
    async def test_cleanup_containers_success(self):
        """Test successful container cleanup."""
        mock_execution_service = AsyncMock()
        mock_execution_service.cleanup_all_containers = AsyncMock()

        with patch("src.dependencies.services.get_execution_service", return_value=mock_execution_service):
            await cleanup_active_containers()

        mock_execution_service.cleanup_all_containers.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_containers_handles_import_error(self):
        """Test cleanup handles import error."""
        with patch.dict("sys.modules", {"src.dependencies.services": None}):
            # Should not raise
            await cleanup_active_containers()

    @pytest.mark.asyncio
    async def test_cleanup_containers_handles_timeout(self):
        """Test cleanup handles timeout."""
        mock_execution_service = AsyncMock()

        async def slow_cleanup():
            raise TimeoutError()

        mock_execution_service.cleanup_all_containers = slow_cleanup

        with patch("src.dependencies.services.get_execution_service", return_value=mock_execution_service):
            # Should not raise
            await cleanup_active_containers()

    @pytest.mark.asyncio
    async def test_cleanup_containers_handles_error(self):
        """Test cleanup handles general errors."""
        mock_execution_service = AsyncMock()
        mock_execution_service.cleanup_all_containers = AsyncMock(side_effect=Exception("Cleanup failed"))

        with patch("src.dependencies.services.get_execution_service", return_value=mock_execution_service):
            # Should not raise
            await cleanup_active_containers()


class TestFlushLogsAndMetrics:
    """Tests for flush_logs_and_metrics function."""

    @pytest.mark.asyncio
    async def test_flush_success(self):
        """Test successful flush."""
        # Should not raise
        await flush_logs_and_metrics()

    @pytest.mark.asyncio
    async def test_flush_handles_error(self):
        """Test flush handles errors."""
        with patch("asyncio.sleep", side_effect=Exception("Sleep error")):
            # Should not raise
            await flush_logs_and_metrics()


class TestSetupGracefulShutdown:
    """Tests for setup_graceful_shutdown function."""

    def test_setup_adds_callbacks(self):
        """Test that setup adds all shutdown callbacks."""
        # Create a new handler for testing
        test_handler = GracefulShutdownHandler()

        with patch("src.utils.shutdown.shutdown_handler", test_handler):
            setup_graceful_shutdown()

        assert len(test_handler._shutdown_callbacks) == 3
        assert flush_logs_and_metrics in test_handler._shutdown_callbacks
        assert cleanup_active_containers in test_handler._shutdown_callbacks
        assert cleanup_services in test_handler._shutdown_callbacks


class TestGlobalShutdownHandler:
    """Tests for global shutdown_handler instance."""

    def test_global_handler_exists(self):
        """Test that global handler exists."""
        assert shutdown_handler is not None
        assert isinstance(shutdown_handler, GracefulShutdownHandler)
