"""Code execution service implementation.

DEPRECATED: This module is maintained for backward compatibility.
New code should import from src.services.execution package instead.

The CodeExecutionService has been split into:
- src/services/execution/runner.py: Core execution logic
- src/services/execution/output.py: Output processing and validation
"""

# Re-export from new package for backward compatibility
from .execution import CodeExecutionRunner, CodeExecutionService, OutputProcessor

__all__ = ["CodeExecutionService", "CodeExecutionRunner", "OutputProcessor"]
