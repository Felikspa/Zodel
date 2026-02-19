from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    username: str = Field(index=True)
    locale: str = Field(default="en")
    password_salt: str = Field(default="")
    password_hash: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Conversation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    user_id: int = Field(index=True)
    title: str = Field(default="New chat")
    is_archived: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    conversation_id: int = Field(index=True)
    role: str = Field(index=True)  # "user" | "assistant" | "system"
    content: str
    model: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class UsageLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    user_id: int = Field(index=True)
    conversation_id: Optional[int] = Field(default=None, index=True)
    model: str = Field(default="", index=True)
    kind: str = Field(default="chat", index=True)  # chat|zflow|rag|stt|tts
    input_chars: int = 0
    output_chars: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class MemorySummary(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    user_id: int = Field(index=True)
    summary: str
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class Flow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    user_id: int = Field(index=True)
    name: str = Field(index=True)
    description: str = Field(default="")
    code: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class Agent(SQLModel, table=True):
    """Custom AI Agent configuration."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    user_id: int = Field(index=True)
    name: str = Field(index=True)
    description: str = Field(default="")
    model: str = Field(default="")
    system_prompt: str = Field(default="")
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=4096)
    top_p: float = Field(default=1.0)
    presence_penalty: float = Field(default=0.0)
    frequency_penalty: float = Field(default=0.0)
    is_default: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class KnowledgeBase(SQLModel, table=True):
    """User's knowledge base for RAG."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    user_id: int = Field(index=True)
    name: str = Field(index=True)
    description: str = Field(default="")
    embedding_model: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class KnowledgeDocument(SQLModel, table=True):
    """Documents in a knowledge base."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(default="default", index=True)
    user_id: int = Field(index=True)
    knowledge_base_id: int = Field(index=True)
    source_name: str = Field(default="")
    file_type: str = Field(default="text")
    chunk_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

