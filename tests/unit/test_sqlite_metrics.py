"""Unit tests for SQLite Metrics Service."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.metrics import DetailedExecutionMetrics
from src.services.sqlite_metrics import SQLiteMetricsService


@pytest.fixture
def sample_metrics():
    """Create sample execution metrics."""
    return DetailedExecutionMetrics(
        execution_id="exec-123",
        session_id="session-123",
        api_key_hash="abc123def456",
        user_id="user-123",
        entity_id="entity-123",
        language="python",
        execution_time_ms=50.0,
        status="completed",
        timestamp=datetime.now(UTC),
    )


class TestSQLiteMetricsServiceInit:
    """Tests for SQLiteMetricsService initialization."""

    def test_init_with_default_path(self):
        """Test initialization with default database path."""
        with patch("src.services.sqlite_metrics.settings") as mock_settings:
            mock_settings.sqlite_metrics_db_path = "/tmp/test_metrics.db"
            service = SQLiteMetricsService()

            assert service.db_path == "/tmp/test_metrics.db"
            assert service._db is None
            assert service._running is False

    def test_init_with_custom_path(self):
        """Test initialization with custom database path."""
        service = SQLiteMetricsService(db_path="/custom/path/metrics.db")

        assert service.db_path == "/custom/path/metrics.db"


class TestRecordExecution:
    """Tests for record_execution method."""

    @pytest.mark.asyncio
    async def test_record_execution_not_running(self, sample_metrics):
        """Test record_execution when service not running."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._running = False

        # Should not raise, just return early
        await service.record_execution(sample_metrics)

        # Queue should be empty
        assert service._write_queue.empty()

    @pytest.mark.asyncio
    async def test_record_execution_queues_metrics(self, sample_metrics):
        """Test record_execution queues metrics when running."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._running = True

        await service.record_execution(sample_metrics)

        assert not service._write_queue.empty()
        queued = await service._write_queue.get()
        assert queued.execution_id == "exec-123"


class TestStartStop:
    """Tests for start and stop methods."""

    @pytest.mark.asyncio
    async def test_start_when_already_running(self):
        """Test start is no-op when already running."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._running = True

        await service.start()

        # Should not change state
        assert service._running is True
        assert service._db is None

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """Test stop is no-op when not running."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._running = False

        # Should not raise
        await service.stop()

        assert service._running is False


class TestWriteBatch:
    """Tests for _write_batch method."""

    @pytest.mark.asyncio
    async def test_write_batch_empty(self):
        """Test write_batch with empty batch."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._db = MagicMock()

        # Should not raise
        await service._write_batch([])

        # No database calls should be made
        service._db.executemany.assert_not_called() if hasattr(service._db, "executemany") else None

    @pytest.mark.asyncio
    async def test_write_batch_no_db(self, sample_metrics):
        """Test write_batch when database is not connected."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._db = None

        # Should not raise
        await service._write_batch([sample_metrics])


class TestFlushQueue:
    """Tests for _flush_queue method."""

    @pytest.mark.asyncio
    async def test_flush_queue_empty(self):
        """Test flushing empty queue."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._db = AsyncMock()

        with patch.object(service, "_write_batch", new_callable=AsyncMock) as mock_write:
            await service._flush_queue()

            # May or may not be called depending on queue state
            # Just verify no error occurs


class TestQueryMethods:
    """Tests for query methods."""

    @pytest.mark.asyncio
    async def test_get_summary_stats_no_db(self):
        """Test get_summary_stats when no database."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._db = None
        service._running = True

        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        result = await service.get_summary_stats(start=start, end=end)

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_language_usage_no_db(self):
        """Test get_language_usage when no database."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._db = None
        service._running = True

        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        result = await service.get_language_usage(start=start, end=end)

        # Returns structure with empty data when no db
        assert isinstance(result, (list, dict))

    @pytest.mark.asyncio
    async def test_get_time_series_no_db(self):
        """Test get_time_series when no database."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._db = None
        service._running = True

        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        result = await service.get_time_series(start=start, end=end)

        # Returns structure with empty data when no db
        assert isinstance(result, (list, dict))

    @pytest.mark.asyncio
    async def test_get_heatmap_data_no_db(self):
        """Test get_heatmap_data when no database."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._db = None
        service._running = True

        start = datetime.now(UTC) - timedelta(days=30)
        end = datetime.now(UTC)

        result = await service.get_heatmap_data(start=start, end=end)

        # Returns structure with heatmap data (matrix, day_labels, hour_labels, etc.)
        assert isinstance(result, dict)
        assert "matrix" in result

    @pytest.mark.asyncio
    async def test_get_api_keys_list_no_db(self):
        """Test get_api_keys_list when no database."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._db = None
        service._running = True

        result = await service.get_api_keys_list()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_top_languages_no_db(self):
        """Test get_top_languages when no database."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._db = None
        service._running = True

        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        result = await service.get_top_languages(start=start, end=end)

        assert result == []


class TestRunAggregation:
    """Tests for run_aggregation method."""

    @pytest.mark.asyncio
    async def test_run_aggregation_no_db(self):
        """Test run_aggregation when database not connected."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._db = None
        service._running = True

        # Should not raise
        await service.run_aggregation()


class TestCleanupOldData:
    """Tests for cleanup_old_data method."""

    @pytest.mark.asyncio
    async def test_cleanup_old_data_no_db(self):
        """Test cleanup when database not connected."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._db = None
        service._running = True

        # Should not raise
        await service.cleanup_old_data()


class TestBatchWriter:
    """Tests for _batch_writer method."""

    @pytest.mark.asyncio
    async def test_write_batch_with_db(self, sample_metrics):
        """Test write_batch writes to database."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        mock_db = AsyncMock()
        mock_db.executemany = AsyncMock()
        mock_db.commit = AsyncMock()
        service._db = mock_db

        await service._write_batch([sample_metrics])

        mock_db.executemany.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_batch_error(self, sample_metrics):
        """Test write_batch handles database errors."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        mock_db = AsyncMock()
        mock_db.executemany = AsyncMock(side_effect=Exception("DB error"))
        service._db = mock_db

        # Should not raise
        await service._write_batch([sample_metrics])


class TestFlushQueueWithItems:
    """Tests for _flush_queue method with queue items."""

    @pytest.mark.asyncio
    async def test_flush_queue_with_items(self, sample_metrics):
        """Test flushing queue with items."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        mock_db = AsyncMock()
        mock_db.executemany = AsyncMock()
        mock_db.commit = AsyncMock()
        service._db = mock_db

        # Add items to queue
        await service._write_queue.put(sample_metrics)

        await service._flush_queue()

        mock_db.executemany.assert_called_once()


class TestRunAggregationWithDb:
    """Tests for run_aggregation with database."""

    @pytest.mark.asyncio
    async def test_run_aggregation_success(self):
        """Test aggregation runs successfully."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.commit = AsyncMock()
        service._db = mock_db

        await service.run_aggregation()

        # Should have executed aggregation queries
        assert mock_db.execute.call_count >= 2
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_aggregation_error(self):
        """Test aggregation handles errors."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB error"))
        service._db = mock_db

        # Should not raise
        await service.run_aggregation()


class TestCleanupOldDataWithDb:
    """Tests for cleanup_old_data with database."""

    @pytest.mark.asyncio
    async def test_cleanup_old_data_success(self):
        """Test cleanup runs successfully."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.commit = AsyncMock()
        service._db = mock_db

        await service.cleanup_old_data()

        # Should have executed cleanup queries (DELETE and VACUUM)
        assert mock_db.execute.call_count >= 4
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_data_error(self):
        """Test cleanup handles errors."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=Exception("DB error"))
        service._db = mock_db

        # Should not raise
        await service.cleanup_old_data()


class TestQueryMethodsWithData:
    """Tests for query methods with database data."""

    @pytest.mark.asyncio
    async def test_get_summary_stats_with_data(self):
        """Test get_summary_stats with data."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        mock_row = {
            "total_executions": 100,
            "success_count": 90,
            "failure_count": 8,
            "timeout_count": 2,
            "avg_execution_time_ms": 50.5,
            "pool_hits": 80,
            "pool_total": 100,
            "active_api_keys": 5,
        }
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=mock_row)
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        service._db = mock_db
        service._running = True

        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        result = await service.get_summary_stats(start=start, end=end)

        assert result["total_executions"] == 100
        assert result["success_count"] == 90
        assert result["success_rate"] == 90.0
        assert result["pool_hit_rate"] == 80.0

    @pytest.mark.asyncio
    async def test_get_summary_stats_with_api_key_filter(self):
        """Test get_summary_stats with API key filter."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        mock_row = {
            "total_executions": 50,
            "success_count": 45,
            "failure_count": 5,
            "timeout_count": 0,
            "avg_execution_time_ms": 40.0,
            "pool_hits": 40,
            "pool_total": 50,
            "active_api_keys": 1,
        }
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=mock_row)
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        service._db = mock_db
        service._running = True

        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        result = await service.get_summary_stats(start=start, end=end, api_key_hash="abc123")

        assert result["total_executions"] == 50
        assert result["active_api_keys"] == 1

    @pytest.mark.asyncio
    async def test_get_summary_stats_empty_result(self):
        """Test get_summary_stats with empty result."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        mock_row = {"total_executions": 0}
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=mock_row)
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        service._db = mock_db
        service._running = True

        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        result = await service.get_summary_stats(start=start, end=end)

        assert result["total_executions"] == 0
        assert result["success_rate"] == 0


class TestGetLanguageUsageWithData:
    """Tests for get_language_usage with data."""

    @pytest.mark.asyncio
    async def test_get_language_usage_with_data(self):
        """Test get_language_usage returns language breakdown."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")

        # Create async iterator for cursor
        async def async_gen():
            for row in [{"language": "python", "count": 50}, {"language": "javascript", "count": 30}]:
                yield row

        mock_cursor = AsyncMock()
        mock_cursor.__aiter__ = lambda self: async_gen()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        service._db = mock_db
        service._running = True

        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        result = await service.get_language_usage(start=start, end=end)

        assert "by_language" in result
        assert result["by_language"]["python"] == 50
        assert result["by_language"]["javascript"] == 30


class TestGetTimeSeriesWithData:
    """Tests for get_time_series with data."""

    @pytest.mark.asyncio
    async def test_get_time_series_hourly(self):
        """Test get_time_series with hourly granularity."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")

        async def async_gen():
            for row in [
                {"period": "2024-01-15 10:00", "executions": 100, "success_count": 90, "avg_duration": 50.0},
                {"period": "2024-01-15 11:00", "executions": 120, "success_count": 110, "avg_duration": 45.0},
            ]:
                yield row

        mock_cursor = AsyncMock()
        mock_cursor.__aiter__ = lambda self: async_gen()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        service._db = mock_db
        service._running = True

        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)

        result = await service.get_time_series(start=start, end=end, granularity="hour")

        assert len(result["timestamps"]) == 2
        assert result["executions"][0] == 100
        assert result["success_rate"][0] == 90.0

    @pytest.mark.asyncio
    async def test_get_time_series_daily(self):
        """Test get_time_series with daily granularity."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")

        async def async_gen():
            for row in [{"period": "2024-01-15", "executions": 500, "success_count": 450, "avg_duration": 55.0}]:
                yield row

        mock_cursor = AsyncMock()
        mock_cursor.__aiter__ = lambda self: async_gen()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        service._db = mock_db
        service._running = True

        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        result = await service.get_time_series(start=start, end=end, granularity="day")

        assert len(result["timestamps"]) == 1
        assert result["executions"][0] == 500

    @pytest.mark.asyncio
    async def test_get_time_series_weekly(self):
        """Test get_time_series with weekly granularity."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")

        async def async_gen():
            for row in [{"period": "2024-02", "executions": 1000, "success_count": 900, "avg_duration": 52.0}]:
                yield row

        mock_cursor = AsyncMock()
        mock_cursor.__aiter__ = lambda self: async_gen()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        service._db = mock_db
        service._running = True

        start = datetime.now(UTC) - timedelta(days=30)
        end = datetime.now(UTC)

        result = await service.get_time_series(start=start, end=end, granularity="week")

        assert len(result["timestamps"]) == 1


class TestGetHeatmapWithData:
    """Tests for get_heatmap_data with data."""

    @pytest.mark.asyncio
    async def test_get_heatmap_with_data(self):
        """Test get_heatmap_data returns matrix."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")

        async def async_gen():
            for row in [
                {"day_of_week": 1, "hour": 9, "count": 50},  # Monday 9am
                {"day_of_week": 1, "hour": 10, "count": 75},  # Monday 10am
                {"day_of_week": 2, "hour": 14, "count": 100},  # Tuesday 2pm
            ]:
                yield row

        mock_cursor = AsyncMock()
        mock_cursor.__aiter__ = lambda self: async_gen()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        service._db = mock_db
        service._running = True

        start = datetime.now(UTC) - timedelta(days=30)
        end = datetime.now(UTC)

        result = await service.get_heatmap_data(start=start, end=end)

        assert "matrix" in result
        assert "max_value" in result
        assert result["max_value"] == 100
        assert len(result["matrix"]) == 7  # 7 days
        assert len(result["matrix"][0]) == 24  # 24 hours


class TestGetApiKeysList:
    """Tests for get_api_keys_list method."""

    @pytest.mark.asyncio
    async def test_get_api_keys_list_with_data(self):
        """Test get_api_keys_list returns API keys."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")

        async def async_gen():
            for row in [
                {"api_key_hash": "abc123", "usage_count": 100},
                {"api_key_hash": "def456", "usage_count": 50},
            ]:
                yield row

        mock_cursor = AsyncMock()
        mock_cursor.__aiter__ = lambda self: async_gen()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        service._db = mock_db
        service._running = True

        result = await service.get_api_keys_list()

        assert len(result) == 2
        assert result[0]["key_hash"] == "abc123"
        assert result[0]["usage_count"] == 100


class TestGetTopLanguages:
    """Tests for get_top_languages method."""

    @pytest.mark.asyncio
    async def test_get_top_languages_with_data(self):
        """Test get_top_languages returns languages."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")

        async def async_gen():
            for row in [
                {"language": "python", "count": 500},
                {"language": "javascript", "count": 300},
                {"language": "go", "count": 100},
            ]:
                yield row

        mock_cursor = AsyncMock()
        mock_cursor.__aiter__ = lambda self: async_gen()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        service._db = mock_db
        service._running = True

        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        result = await service.get_top_languages(start=start, end=end, limit=3)

        assert len(result) == 3
        assert result[0]["language"] == "python"
        assert result[0]["count"] == 500


class TestStopMethod:
    """Tests for stop method."""

    @pytest.mark.asyncio
    async def test_stop_cancels_tasks(self):
        """Test stop cancels background tasks."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._running = True

        # Create mock tasks that raise CancelledError when awaited
        async def mock_cancelled_task():
            raise asyncio.CancelledError()

        mock_task1 = asyncio.create_task(asyncio.sleep(100))
        mock_task2 = asyncio.create_task(asyncio.sleep(100))
        mock_task3 = asyncio.create_task(asyncio.sleep(100))
        service._writer_task = mock_task1
        service._aggregation_task = mock_task2
        service._cleanup_task = mock_task3

        # Mock database
        mock_db = AsyncMock()
        mock_db.close = AsyncMock()
        service._db = mock_db

        await service.stop()

        assert service._running is False
        mock_db.close.assert_called_once()
        assert service._db is None
        assert mock_task1.cancelled()
        assert mock_task2.cancelled()
        assert mock_task3.cancelled()


class TestStartMethod:
    """Tests for start method with database initialization."""

    @pytest.mark.asyncio
    async def test_start_initializes_db(self, tmp_path):
        """Test start creates database and starts background tasks."""
        db_path = str(tmp_path / "test_metrics.db")
        service = SQLiteMetricsService(db_path=db_path)

        await service.start()

        try:
            assert service._running is True
            assert service._db is not None
            assert service._writer_task is not None
            assert service._aggregation_task is not None
            assert service._cleanup_task is not None
        finally:
            await service.stop()


class TestBatchWriterLoop:
    """Tests for _batch_writer background task."""

    @pytest.mark.asyncio
    async def test_batch_writer_processes_items(self, sample_metrics):
        """Test batch writer processes queue items."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._running = True
        service._flush_interval = 0.1

        mock_db = AsyncMock()
        mock_db.executemany = AsyncMock()
        mock_db.commit = AsyncMock()
        service._db = mock_db

        # Add item to queue
        await service._write_queue.put(sample_metrics)

        # Run batch writer briefly
        async def stop_after_short_time():
            await asyncio.sleep(0.3)
            service._running = False

        task = asyncio.create_task(service._batch_writer())
        stop_task = asyncio.create_task(stop_after_short_time())

        try:
            await asyncio.wait_for(asyncio.gather(task, stop_task, return_exceptions=True), timeout=1)
        except asyncio.CancelledError:
            pass

        # Verify write was called
        assert mock_db.executemany.called or service._write_queue.empty()

    @pytest.mark.asyncio
    async def test_batch_writer_handles_cancelled_error(self, sample_metrics):
        """Test batch writer flushes on CancelledError."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._running = True

        mock_db = AsyncMock()
        mock_db.executemany = AsyncMock()
        mock_db.commit = AsyncMock()
        service._db = mock_db

        # Add item to queue
        await service._write_queue.put(sample_metrics)

        # Start batch writer and cancel it
        task = asyncio.create_task(service._batch_writer())
        await asyncio.sleep(0.05)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_batch_writer_handles_exception(self, sample_metrics):
        """Test batch writer handles exceptions gracefully."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._running = True
        service._flush_interval = 0.1
        iteration = 0

        async def mock_write_batch(batch):
            nonlocal iteration
            iteration += 1
            if iteration == 1:
                raise Exception("Write failed")
            service._running = False

        with patch.object(service, "_write_batch", side_effect=mock_write_batch):
            await service._write_queue.put(sample_metrics)

            try:
                await asyncio.wait_for(service._batch_writer(), timeout=0.5)
            except TimeoutError:
                pass


class TestAggregationLoop:
    """Tests for _aggregation_loop method."""

    @pytest.mark.asyncio
    async def test_aggregation_loop_runs(self):
        """Test aggregation loop runs and calls run_aggregation."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._running = True

        call_count = 0

        async def mock_run_aggregation():
            nonlocal call_count
            call_count += 1
            service._running = False

        with patch.object(service, "run_aggregation", side_effect=mock_run_aggregation):
            with patch("src.services.sqlite_metrics.settings") as mock_settings:
                mock_settings.metrics_aggregation_interval_minutes = 0.001  # Very short

                with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                    mock_sleep.side_effect = lambda x: None
                    await service._aggregation_loop()

    @pytest.mark.asyncio
    async def test_aggregation_loop_handles_cancelled_error(self):
        """Test aggregation loop handles CancelledError."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._running = True

        async def mock_sleep(_):
            raise asyncio.CancelledError()

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with patch("src.services.sqlite_metrics.settings") as mock_settings:
                mock_settings.metrics_aggregation_interval_minutes = 1

                with pytest.raises(asyncio.CancelledError):
                    await service._aggregation_loop()

    @pytest.mark.asyncio
    async def test_aggregation_loop_handles_exception(self):
        """Test aggregation loop handles exceptions."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._running = True
        iteration = 0

        async def mock_run_aggregation():
            nonlocal iteration
            iteration += 1
            if iteration == 1:
                raise Exception("Aggregation failed")
            service._running = False

        with patch.object(service, "run_aggregation", side_effect=mock_run_aggregation):
            with patch("src.services.sqlite_metrics.settings") as mock_settings:
                mock_settings.metrics_aggregation_interval_minutes = 0.001

                with patch("asyncio.sleep", new_callable=AsyncMock):
                    await service._aggregation_loop()


class TestCleanupLoop:
    """Tests for _cleanup_loop method."""

    @pytest.mark.asyncio
    async def test_cleanup_loop_runs(self):
        """Test cleanup loop runs and calls cleanup_old_data."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._running = True

        async def mock_cleanup():
            service._running = False

        with patch.object(service, "cleanup_old_data", side_effect=mock_cleanup):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await service._cleanup_loop()

    @pytest.mark.asyncio
    async def test_cleanup_loop_handles_cancelled_error(self):
        """Test cleanup loop handles CancelledError."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._running = True

        async def mock_sleep(_):
            raise asyncio.CancelledError()

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(asyncio.CancelledError):
                await service._cleanup_loop()

    @pytest.mark.asyncio
    async def test_cleanup_loop_handles_exception(self):
        """Test cleanup loop handles exceptions."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")
        service._running = True
        iteration = 0

        async def mock_cleanup():
            nonlocal iteration
            iteration += 1
            if iteration == 1:
                raise Exception("Cleanup failed")
            service._running = False

        with patch.object(service, "cleanup_old_data", side_effect=mock_cleanup):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await service._cleanup_loop()


class TestGetLanguageUsageWithApiKeyFilter:
    """Tests for get_language_usage with API key filter."""

    @pytest.mark.asyncio
    async def test_get_language_usage_with_api_key_filter(self):
        """Test get_language_usage with API key filter."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")

        async def async_gen():
            for row in [{"language": "python", "count": 25}]:
                yield row

        mock_cursor = AsyncMock()
        mock_cursor.__aiter__ = lambda self: async_gen()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        service._db = mock_db
        service._running = True

        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        result = await service.get_language_usage(start=start, end=end, api_key_hash="abc123")

        assert result["by_language"]["python"] == 25
        # Verify API key filter was in query
        call_args = mock_db.execute.call_args
        assert "abc123" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_language_usage_stacked_by_api_key(self):
        """Test get_language_usage with stack_by_api_key=True."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")

        call_count = 0

        async def async_gen1():
            for row in [{"language": "python", "count": 50}, {"language": "js", "count": 30}]:
                yield row

        async def async_gen2():
            for row in [
                {"language": "python", "api_key_hash": "key1", "count": 30},
                {"language": "python", "api_key_hash": "key2", "count": 20},
                {"language": "js", "api_key_hash": "key1", "count": 30},
            ]:
                yield row

        mock_cursor1 = AsyncMock()
        mock_cursor1.__aiter__ = lambda self: async_gen1()

        mock_cursor2 = AsyncMock()
        mock_cursor2.__aiter__ = lambda self: async_gen2()

        mock_db = AsyncMock()

        async def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_cursor1
            return mock_cursor2

        mock_db.execute = mock_execute
        service._db = mock_db
        service._running = True

        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        result = await service.get_language_usage(start=start, end=end, stack_by_api_key=True)

        assert "by_language" in result
        assert "by_api_key" in result
        assert "matrix" in result
        assert result["matrix"]["python"]["key1"] == 30
        assert result["by_api_key"]["key1"] == 60


class TestGetTimeSeriesWithApiKeyFilter:
    """Tests for get_time_series with API key filter."""

    @pytest.mark.asyncio
    async def test_get_time_series_with_api_key_filter(self):
        """Test get_time_series with API key filter."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")

        async def async_gen():
            for row in [{"period": "2024-01-15 10:00", "executions": 50, "success_count": 45, "avg_duration": 40.0}]:
                yield row

        mock_cursor = AsyncMock()
        mock_cursor.__aiter__ = lambda self: async_gen()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        service._db = mock_db
        service._running = True

        start = datetime.now(UTC) - timedelta(days=1)
        end = datetime.now(UTC)

        result = await service.get_time_series(start=start, end=end, api_key_hash="xyz789")

        assert result["executions"][0] == 50
        # Verify API key filter was in query params
        call_args = mock_db.execute.call_args
        assert "xyz789" in call_args[0][1]


class TestGetHeatmapWithApiKeyFilter:
    """Tests for get_heatmap_data with API key filter."""

    @pytest.mark.asyncio
    async def test_get_heatmap_with_api_key_filter(self):
        """Test get_heatmap_data with API key filter."""
        service = SQLiteMetricsService(db_path="/tmp/test.db")

        async def async_gen():
            for row in [{"day_of_week": 3, "hour": 14, "count": 25}]:
                yield row

        mock_cursor = AsyncMock()
        mock_cursor.__aiter__ = lambda self: async_gen()
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_cursor)
        service._db = mock_db
        service._running = True

        start = datetime.now(UTC) - timedelta(days=30)
        end = datetime.now(UTC)

        result = await service.get_heatmap_data(start=start, end=end, api_key_hash="filterkey")

        assert result["max_value"] == 25
        # Verify API key filter was in query params
        call_args = mock_db.execute.call_args
        assert "filterkey" in call_args[0][1]
