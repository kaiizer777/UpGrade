"""Pydantic schemas for ChatMessage."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.chat_message import ChatRole


class ChatMessageBase(BaseModel):
    """Base schema for ChatMessage."""

    role: ChatRole
    content: str


class ChatMessageCreate(ChatMessageBase):
    """Schema for logging a chat message."""

    topic_id: int


class ChatMessageRead(ChatMessageBase):
    """Schema for reading a chat message."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_id: int
    created_at: datetime
