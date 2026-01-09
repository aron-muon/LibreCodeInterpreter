"""Service dependency injection for the Code Interpreter API."""

# Standard library imports
from functools import lru_cache
from typing import Annotated

import structlog

# Third-party imports
from fastapi import Depends

# Local application imports
from ..services import CodeExecutionService, FileService, SessionService
from ..services.interfaces import (
    ExecutionServiceInterface,
    FileServiceInterface,
    SessionServiceInterface,
)
from ..services.state import StateService
from ..services.state_archival import StateArchivalService

logger = structlog.get_logger(__name__)

# Global reference to Kubernetes manager (set by main.py lifespan)
_kubernetes_manager = None


def set_kubernetes_manager(manager) -> None:
    """Set the global Kubernetes manager reference.

    Called by main.py after the manager is initialized in lifespan.
    """
    global _kubernetes_manager
    _kubernetes_manager = manager
    logger.info("Kubernetes manager registered with dependency injection")


def get_kubernetes_manager():
    """Get the Kubernetes manager instance (may be None if disabled)."""
    return _kubernetes_manager


@lru_cache
def get_file_service() -> FileServiceInterface:
    """Get file service instance."""
    return FileService()


@lru_cache
def get_state_service() -> StateService:
    """Get state service instance for Python session state persistence."""
    return StateService()


@lru_cache
def get_state_archival_service() -> StateArchivalService:
    """Get state archival service instance for MinIO cold storage."""
    state_service = get_state_service()
    return StateArchivalService(state_service=state_service)


@lru_cache
def get_execution_service() -> ExecutionServiceInterface:
    """Get execution service instance.

    Note: Kubernetes manager is injected separately after creation.
    """
    return CodeExecutionService()


def inject_kubernetes_manager_to_execution_service():
    """Inject Kubernetes manager into the execution service.

    Called after manager is initialized to wire it into the cached execution service.
    """
    global _kubernetes_manager
    if _kubernetes_manager:
        execution_service = get_execution_service()
        execution_service._kubernetes_manager = _kubernetes_manager
        logger.info("Kubernetes manager injected into execution service")


@lru_cache
def get_session_service() -> SessionServiceInterface:
    """Get session service instance with proper dependency injection."""
    try:
        # Don't inject dependencies during initialization to avoid circular imports
        # The services will coordinate during runtime
        session_service = SessionService()

        # Set up service references after initialization
        execution_service = get_execution_service()
        file_service = get_file_service()

        # Wire up the dependencies
        session_service._execution_service = execution_service
        session_service._file_service = file_service

        logger.info("Session service initialized with dependencies")
        return session_service

    except Exception as e:
        logger.error("Failed to initialize session service", error=str(e))
        # Return basic session service without dependencies as fallback
        return SessionService()


# Type aliases for dependency injection
FileServiceDep = Annotated[FileServiceInterface, Depends(get_file_service)]
SessionServiceDep = Annotated[SessionServiceInterface, Depends(get_session_service)]
ExecutionServiceDep = Annotated[ExecutionServiceInterface, Depends(get_execution_service)]
StateServiceDep = Annotated[StateService, Depends(get_state_service)]
StateArchivalServiceDep = Annotated[StateArchivalService, Depends(get_state_archival_service)]
