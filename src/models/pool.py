"""Pod pool data models.

These models track pods in the pool. The pool is stateless with respect
to sessions - pods are provided fresh and destroyed after each execution.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Literal


@dataclass
class PooledPod:
    """Represents a pod available in the pool.

    Pods in the pool are pre-warmed and ready to be used.
    After use, pods are destroyed (not returned to pool).
    """

    pod_name: str
    language: str
    image: str
    created_at: datetime
    status: Literal["available", "starting", "unhealthy"] = "available"

    def __hash__(self):
        return hash(self.pod_name)

    def __eq__(self, other):
        if not isinstance(other, PooledPod):
            return False
        return self.pod_name == other.pod_name


# Backward compatibility alias
PooledContainer = PooledPod


@dataclass
class PoolStats:
    """Pod pool statistics for monitoring."""

    language: str
    available_count: int
    assigned_count: int  # Kept for backward compatibility (always 0 now)
    total_acquisitions: int = 0
    pool_hits: int = 0  # Acquired from pool
    pool_misses: int = 0  # Created fresh (pool empty)
    pods_created: int = 0
    pods_destroyed: int = 0
    avg_acquire_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class PoolConfig:
    """Configuration for a language-specific pod pool."""

    language: str
    size: int  # Single pool size (0 = on-demand only)
    warmup_on_startup: bool = True

    @classmethod
    def from_settings(cls, language: str) -> "PoolConfig":
        """Create pool config from settings for a specific language."""
        from ..config import settings

        # Map language to its pool size setting
        pool_sizes = {
            "py": settings.pod_pool_py,
            "js": settings.pod_pool_js,
            "ts": settings.pod_pool_ts,
            "go": settings.pod_pool_go,
            "java": settings.pod_pool_java,
            "c": settings.pod_pool_c,
            "cpp": settings.pod_pool_cpp,
            "php": settings.pod_pool_php,
            "rs": settings.pod_pool_rs,
            "r": settings.pod_pool_r,
            "f90": settings.pod_pool_f90,
            "d": settings.pod_pool_d,
        }

        size = pool_sizes.get(language, 0)
        return cls(
            language=language,
            size=size,
            warmup_on_startup=size > 0 and settings.pod_pool_warmup_on_startup,
        )
