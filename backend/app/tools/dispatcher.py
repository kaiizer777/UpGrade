"""Tool execution dispatcher, schema registry, and structured error handling."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.tools.exceptions import ToolError
from app.tools.handlers import (
    execute_ask_question,
    execute_create_roadmap,
    execute_finalize_profile,
    execute_generate_feed_batch,
    execute_log_chat_message,
    execute_mark_topic_complete,
    execute_save_answer,
    execute_update_profile_slots,
)
from app.tools.schemas import (
    AskQuestionInput,
    CreateRoadmapInput,
    FinalizeProfileInput,
    GenerateFeedBatchInput,
    LogChatMessageInput,
    MarkTopicCompleteInput,
    SaveAnswerInput,
    ToolResult,
    UpdateProfileSlotsInput,
)


@dataclass(frozen=True)
class ToolDefinition:
    """Metadata and execution spec for a registered LLM tool."""

    name: str
    description: str
    input_schema: type[BaseModel]
    handler: Callable[[AsyncSession, Any], Coroutine[Any, Any, BaseModel]]


# Registry of all available tools
TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "ask_question": ToolDefinition(
        name="ask_question",
        description=(
            "Ask a clarifying question to the user during onboarding. "
            "Capped at 10 questions maximum per subject."
        ),
        input_schema=AskQuestionInput,
        handler=execute_ask_question,
    ),
    "save_answer": ToolDefinition(
        name="save_answer",
        description=(
            "Persist the user's answer to an onboarding question into "
            "onboarding_answers."
        ),
        input_schema=SaveAnswerInput,
        handler=execute_save_answer,
    ),
    "finalize_profile": ToolDefinition(
        name="finalize_profile",
        description=(
            "Lock the subject profile with personalized slots (goal, current level, "
            "background, motivation, pace) and set status to 'ready'."
        ),
        input_schema=FinalizeProfileInput,
        handler=execute_finalize_profile,
    ),
    "update_profile_slots": ToolDefinition(
        name="update_profile_slots",
        description=(
            "Persist profile slot values (goal, current_level, background, "
            "motivation, pace_preference) the moment you learn them from the "
            "user's replies during onboarding. Only pass the slots you just "
            "learned - omitted slots are left unchanged. Call this tool as "
            "soon as new information becomes available, before continuing."
        ),
        input_schema=UpdateProfileSlotsInput,
        handler=execute_update_profile_slots,
    ),
    "create_roadmap": ToolDefinition(
        name="create_roadmap",
        description=(
            "Bulk insert ordered roadmap topics for a subject with prerequisite "
            "dependencies. The first topic is automatically activated."
        ),
        input_schema=CreateRoadmapInput,
        handler=execute_create_roadmap,
    ),
    "generate_feed_batch": ToolDefinition(
        name="generate_feed_batch",
        description="Bulk insert generated lesson bites/feed posts for a topic.",
        input_schema=GenerateFeedBatchInput,
        handler=execute_generate_feed_batch,
    ),
    "mark_topic_complete": ToolDefinition(
        name="mark_topic_complete",
        description=(
            "Mark the current topic done, purge its old ephemeral feed posts, "
            "and activate the next pending topic in a single atomic transaction."
        ),
        input_schema=MarkTopicCompleteInput,
        handler=execute_mark_topic_complete,
    ),
    "log_chat_message": ToolDefinition(
        name="log_chat_message",
        description=(
            "Persist an Open Chat conversation turn (user or assistant) for a topic."
        ),
        input_schema=LogChatMessageInput,
        handler=execute_log_chat_message,
    ),
}


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return OpenAI/Groq compatible function definitions for all registered tools."""
    definitions: list[dict[str, Any]] = []
    for tool in TOOL_REGISTRY.values():
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema.model_json_schema(),
                },
            }
        )
    return definitions


class ToolRetryTracker:
    """Track consecutive failed tool call attempts with a hard stop cap."""

    def __init__(self, max_retries: int = 3) -> None:
        self.max_retries = max_retries
        self._failure_counts: dict[str, int] = {}

    def record_failure(self, tool_name: str) -> int:
        """Increment failure count for a tool and return new count."""
        count = self._failure_counts.get(tool_name, 0) + 1
        self._failure_counts[tool_name] = count
        return count

    def record_success(self, tool_name: str) -> None:
        """Reset failure count on successful execution."""
        self._failure_counts[tool_name] = 0

    def is_exhausted(self, tool_name: str) -> bool:
        """Return True if consecutive failures reached or exceeded max_retries."""
        return self._failure_counts.get(tool_name, 0) >= self.max_retries

    def get_failure_count(self, tool_name: str) -> int:
        """Return current failure count for a tool."""
        return self._failure_counts.get(tool_name, 0)

    def reset_all(self) -> None:
        """Reset all tracked tool failure counts."""
        self._failure_counts.clear()


async def execute_tool(
    session: AsyncSession,
    name: str,
    arguments: dict[str, Any] | BaseModel,
) -> ToolResult:
    """Dispatch and execute an LLM tool call with validated schemas.

    Guarantees:
    - Never throws unhandled exceptions to caller.
    - Always returns a structured ToolResult with success, tool_name, data or error.
    - Validation errors return structured field breakdowns for the LLM to self-correct.
    - Automatic rollback on unexpected execution failures.
    """
    tool_def = TOOL_REGISTRY.get(name)
    if not tool_def:
        available_tools = list(TOOL_REGISTRY.keys())
        return ToolResult(
            success=False,
            tool_name=name,
            error=f"Tool '{name}' is not registered. Tools: {available_tools}",
            error_code="TOOL_NOT_FOUND",
            details={"available_tools": available_tools},
        )

    # 1. Parse and validate arguments against tool's Pydantic input schema
    try:
        if isinstance(arguments, BaseModel):
            if isinstance(arguments, tool_def.input_schema):
                validated_params = arguments
            else:
                validated_params = tool_def.input_schema.model_validate(
                    arguments.model_dump()
                )
        elif isinstance(arguments, dict):
            validated_params = tool_def.input_schema.model_validate(arguments)
        else:
            got_type = type(arguments).__name__
            return ToolResult(
                success=False,
                tool_name=name,
                error=(
                    f"Invalid arguments type for tool '{name}'. "
                    f"Expected dict or model, got {got_type}"
                ),
                error_code="INVALID_ARGUMENT_TYPE",
            )
    except ValidationError as err:
        errors = [
            {
                "loc": [str(loc) for loc in e.get("loc", [])],
                "msg": e.get("msg", ""),
                "type": e.get("type", ""),
            }
            for e in err.errors()
        ]
        return ToolResult(
            success=False,
            tool_name=name,
            error=f"Validation failed for tool '{name}': {err.error_count()} error(s).",
            error_code="VALIDATION_ERROR",
            details={"validation_errors": errors},
        )

    # 2. Execute the handler function
    try:
        result_model = await tool_def.handler(session, validated_params)
        return ToolResult(
            success=True,
            tool_name=name,
            data=result_model.model_dump(),
            error=None,
            error_code=None,
            details=None,
        )
    except ToolError as err:
        await session.rollback()
        return ToolResult(
            success=False,
            tool_name=name,
            error=err.message,
            error_code=err.code,
            details=err.details,
        )
    except Exception as err:  # Broad catch-all to guarantee structured result
        await session.rollback()
        return ToolResult(
            success=False,
            tool_name=name,
            error=f"Internal error executing tool '{name}': {str(err)}",
            error_code="INTERNAL_ERROR",
            details={"exception_type": type(err).__name__},
        )
