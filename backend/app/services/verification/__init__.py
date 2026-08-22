"""Verification service package.

Keep package initialization lightweight. Advanced security modules live under
``app.services.verification.advanced`` and are imported while
``advanced_security_service`` itself is still being initialized. Eagerly importing the
verification service here creates a circular dependency:

advanced_security_service -> verification.advanced -> verification.__init__ ->
verification.service -> verification.security_gate -> advanced_security_service

The public compatibility exports remain available lazily without executing that cycle
when a verification submodule is imported.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.verification.service import ENGINE_VERSION, calculate_verification

__all__ = ["ENGINE_VERSION", "calculate_verification"]


def __getattr__(name: str) -> Any:
    if name == "ENGINE_VERSION":
        from app.services.verification.service import ENGINE_VERSION

        return ENGINE_VERSION
    if name == "calculate_verification":
        from app.services.verification.service import calculate_verification

        return calculate_verification
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
