"""Unit tests for core event system."""

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.events import Event, EventBus


@dataclass
class SampleEvent(Event):
    """Sample event for testing."""

    value: str = "test"


@dataclass
class OtherEvent(Event):
    """Another test event."""

    data: int = 42


@pytest.fixture
def event_bus():
    """Create a fresh event bus."""
    return EventBus()


class TestEventBusRegister:
    """Tests for register_handler method."""

    def test_register_handler(self, event_bus):
        """Test registering a handler."""

        async def handler(event: SampleEvent):
            pass

        event_bus.register_handler(SampleEvent, handler)

        assert SampleEvent in event_bus._handlers
        assert handler in event_bus._handlers[SampleEvent]

    def test_register_multiple_handlers(self, event_bus):
        """Test registering multiple handlers for same event."""

        async def handler1(event: SampleEvent):
            pass

        async def handler2(event: SampleEvent):
            pass

        event_bus.register_handler(SampleEvent, handler1)
        event_bus.register_handler(SampleEvent, handler2)

        assert len(event_bus._handlers[SampleEvent]) == 2


class TestEventBusUnregister:
    """Tests for unregister_handler method."""

    def test_unregister_handler_success(self, event_bus):
        """Test unregistering an existing handler."""

        async def handler(event: SampleEvent):
            pass

        event_bus.register_handler(SampleEvent, handler)
        result = event_bus.unregister_handler(SampleEvent, handler)

        assert result is True
        assert handler not in event_bus._handlers[SampleEvent]

    def test_unregister_handler_not_found(self, event_bus):
        """Test unregistering a handler that doesn't exist."""

        async def handler(event: SampleEvent):
            pass

        result = event_bus.unregister_handler(SampleEvent, handler)

        assert result is False

    def test_unregister_handler_wrong_event_type(self, event_bus):
        """Test unregistering from wrong event type."""

        async def handler(event: SampleEvent):
            pass

        event_bus.register_handler(SampleEvent, handler)
        result = event_bus.unregister_handler(OtherEvent, handler)

        assert result is False


class TestEventBusPublish:
    """Tests for publish method."""

    @pytest.mark.asyncio
    async def test_publish_no_handlers(self, event_bus):
        """Test publishing with no handlers."""
        event = SampleEvent(value="test")

        # Should not raise
        await event_bus.publish(event)

    @pytest.mark.asyncio
    async def test_publish_with_handler(self, event_bus):
        """Test publishing calls handler."""
        called_with = []

        async def handler(event: SampleEvent):
            called_with.append(event)

        event_bus.register_handler(SampleEvent, handler)
        event = SampleEvent(value="hello")

        await event_bus.publish(event)

        assert len(called_with) == 1
        assert called_with[0].value == "hello"

    @pytest.mark.asyncio
    async def test_publish_multiple_handlers(self, event_bus):
        """Test publishing calls all handlers concurrently."""
        results = []

        async def handler1(event: SampleEvent):
            await asyncio.sleep(0.01)
            results.append("handler1")

        async def handler2(event: SampleEvent):
            results.append("handler2")

        event_bus.register_handler(SampleEvent, handler1)
        event_bus.register_handler(SampleEvent, handler2)

        await event_bus.publish(SampleEvent())

        assert len(results) == 2
        assert "handler1" in results
        assert "handler2" in results

    @pytest.mark.asyncio
    async def test_publish_handler_error(self, event_bus):
        """Test publishing handles handler errors gracefully."""
        good_handler_called = []

        async def error_handler(event: SampleEvent):
            raise ValueError("Handler error")

        async def good_handler(event: SampleEvent):
            good_handler_called.append(True)

        event_bus.register_handler(SampleEvent, error_handler)
        event_bus.register_handler(SampleEvent, good_handler)

        # Should not raise despite handler error
        await event_bus.publish(SampleEvent())

        # Good handler should still be called
        assert len(good_handler_called) == 1


class TestEventBusPublishAndWait:
    """Tests for publish_and_wait method."""

    @pytest.mark.asyncio
    async def test_publish_and_wait_no_errors(self, event_bus):
        """Test publish_and_wait returns empty list on success."""

        async def handler(event: SampleEvent):
            pass

        event_bus.register_handler(SampleEvent, handler)
        errors = await event_bus.publish_and_wait(SampleEvent())

        assert errors == []

    @pytest.mark.asyncio
    async def test_publish_and_wait_collects_errors(self, event_bus):
        """Test publish_and_wait collects all errors."""

        async def error_handler(event: SampleEvent):
            raise ValueError("Error 1")

        async def another_error_handler(event: SampleEvent):
            raise RuntimeError("Error 2")

        event_bus.register_handler(SampleEvent, error_handler)
        event_bus.register_handler(SampleEvent, another_error_handler)

        errors = await event_bus.publish_and_wait(SampleEvent())

        assert len(errors) == 2
        assert any(isinstance(e, ValueError) for e in errors)
        assert any(isinstance(e, RuntimeError) for e in errors)

    @pytest.mark.asyncio
    async def test_publish_and_wait_no_handlers(self, event_bus):
        """Test publish_and_wait with no handlers."""
        errors = await event_bus.publish_and_wait(SampleEvent())

        assert errors == []


class TestEventBusClearHandlers:
    """Tests for clear_handlers method."""

    def test_clear_handlers_specific_type(self, event_bus):
        """Test clearing handlers for specific event type."""

        async def handler1(event: SampleEvent):
            pass

        async def handler2(event: OtherEvent):
            pass

        event_bus.register_handler(SampleEvent, handler1)
        event_bus.register_handler(OtherEvent, handler2)

        event_bus.clear_handlers(SampleEvent)

        assert SampleEvent not in event_bus._handlers
        assert OtherEvent in event_bus._handlers

    def test_clear_handlers_all(self, event_bus):
        """Test clearing all handlers."""

        async def handler1(event: SampleEvent):
            pass

        async def handler2(event: OtherEvent):
            pass

        event_bus.register_handler(SampleEvent, handler1)
        event_bus.register_handler(OtherEvent, handler2)

        event_bus.clear_handlers()

        assert len(event_bus._handlers) == 0

    def test_clear_handlers_nonexistent_type(self, event_bus):
        """Test clearing handlers for type that has none."""
        # Should not raise
        event_bus.clear_handlers(SampleEvent)
