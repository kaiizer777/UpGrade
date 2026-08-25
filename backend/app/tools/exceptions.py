"""Custom exceptions for LLM tool layer."""

from typing import Any


class ToolError(Exception):
    """Base exception for all tool execution and validation errors."""

    def __init__(
        self,
        message: str,
        code: str = "TOOL_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class ToolValidationError(ToolError):
    """Raised when input parameters fail schema or semantic validation."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=details,
        )


class ToolNotFoundError(ToolError):
    """Raised when an entity referenced by a tool is not found in the database."""

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="NOT_FOUND",
            details=details,
        )


class ToolExecutionError(ToolError):
    """Raised when a tool operation fails during execution."""

    def __init__(
        self,
        message: str,
        code: str = "EXECUTION_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            details=details,
        )


class MaxQuestionsExceededError(ToolExecutionError):
    """Raised when onboarding question limit (10 max) is reached."""

    def __init__(
        self,
        message: str = "Maximum onboarding question limit (10 questions) reached.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="MAX_QUESTIONS_EXCEEDED",
            details=details,
        )
