"""Open Chat router: POST chat turn + GET history, topic-scoped."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.database import get_session
from app.services.ai import AiConfigError, AiGenerationError
from app.services.chat import (
    SubjectNotFoundError,
    TopicNotFoundError,
    chat_turn,
    get_chat_history,
)

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    """POST body for chat turn."""

    message: str = Field(..., min_length=1, description="User message content")

    @property
    def cleaned(self) -> str:
        return self.message.strip()


class ChatMessageRead(BaseModel):
    id: int
    topic_id: int
    role: str
    content: str
    created_at: str | None = None


def _to_read(m: dict) -> ChatMessageRead:
    return ChatMessageRead(**m)


@router.post(
    "/subjects/{subject_id}/topics/{topic_id}/chat",
    summary="Send a chat message scoped to topic+subject",
)
async def post_chat(
    subject_id: uuid.UUID,
    topic_id: int,
    payload: ChatRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Persist user turn, call LLM, persist AI turn, return reply + full history."""
    cleaned = payload.message.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="message must be non-empty"
        )
    try:
        result = await chat_turn(session, subject_id, topic_id, cleaned)
    except SubjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from None
    except TopicNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from None
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from None
    except AiConfigError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI provider not configured",
        ) from None
    except AiGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Chat generation failed: {exc}",
        ) from None
    # Serialize messages (already dicts)
    return {"reply": result["reply"], "messages": result["messages"]}


@router.get(
    "/subjects/{subject_id}/topics/{topic_id}/chat",
    summary="Get chat history for a topic",
)
async def get_chat(
    subject_id: uuid.UUID,
    topic_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return ordered chat history for the topic."""
    try:
        history = await get_chat_history(session, subject_id, topic_id)
    except SubjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from None
    except TopicNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from None
    messages = [
        {
            "id": m.id,
            "topic_id": m.topic_id,
            "role": m.role.value if hasattr(m.role, "value") else str(m.role),
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in history
    ]
    return {"messages": messages, "topic_id": topic_id, "subject_id": str(subject_id)}
