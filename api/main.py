from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field

from app.services.chat_service import ChatService, RoutingConfig
from app.services.model_service import ModelService
from app.services.zflow_service import ZflowService
from app.rag.rag_service import RagService
from app.db import init_db, session_scope, engine
from app.persistence.models import Conversation, Message, User, MemorySummary, Flow, UsageLog, Agent, KnowledgeBase, KnowledgeDocument
from sqlmodel import select
from app.helper import infer_provider_from_model, extract_model_name, stream_chat, openai_client
from sqlmodel import SQLModel
from api.auth import issue_token, verify_token, new_salt, hash_password


app = FastAPI(title="ZODEL API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

chat_service = ChatService()
zflow_service = ZflowService()
model_service = ModelService()
rag_service = RagService()
# Ensure newly added tables exist even after incremental edits.
SQLModel.metadata.create_all(engine)


def _sse_event(data: Dict[str, Any], event: str = "message") -> str:
    # Minimal SSE format (no retry/id for now)
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class ChatTurn(BaseModel):
    user: str
    assistant: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    history: List[ChatTurn] = Field(default_factory=list)
    mode: str = Field("chat", description="chat|auto")
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    routing: Optional[Dict[str, Any]] = None
    rag: Optional[Dict[str, Any]] = None
    user: Optional[Dict[str, Any]] = None
    conversation_id: Optional[int] = None


class ZflowRequest(BaseModel):
    script: str = Field(..., min_length=1)

class FlowCreateRequest(BaseModel):
    user_id: int
    name: str = Field(..., min_length=1)
    description: str = ""
    code: str = Field(..., min_length=1)


@app.get("/api/flows")
def list_flows(user_id: int) -> Dict[str, Any]:
    with session_scope() as session:
        rows = session.exec(
            select(Flow).where(Flow.user_id == user_id).order_by(Flow.updated_at.desc())
        ).all()
        return {
            "flows": [
                {"id": f.id, "name": f.name, "description": f.description, "updated_at": f.updated_at.isoformat()}
                for f in rows
            ]
        }


@app.post("/api/flows")
def create_flow(req: FlowCreateRequest) -> Dict[str, Any]:
    with session_scope() as session:
        flow = Flow(user_id=req.user_id, name=req.name.strip(), description=req.description.strip(), code=req.code)
        session.add(flow)
        session.commit()
        session.refresh(flow)
        return {"flow": {"id": flow.id, "name": flow.name, "description": flow.description, "code": flow.code}}


@app.get("/api/flows/{flow_id}")
def get_flow(flow_id: int) -> Dict[str, Any]:
    with session_scope() as session:
        flow = session.get(Flow, flow_id)
        if not flow:
            raise HTTPException(status_code=404, detail="Flow not found")
        return {"flow": {"id": flow.id, "user_id": flow.user_id, "name": flow.name, "description": flow.description, "code": flow.code}}


@app.delete("/api/flows/{flow_id}")
def delete_flow(flow_id: int) -> Dict[str, Any]:
    with session_scope() as session:
        flow = session.get(Flow, flow_id)
        if not flow:
            raise HTTPException(status_code=404, detail="Flow not found")
        session.delete(flow)
        session.commit()
        return {"deleted": True}


# --- Agent Endpoints ---

class AgentCreateRequest(BaseModel):
    user_id: int
    name: str = Field(..., min_length=1)
    description: str = ""
    model: str = ""
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    is_default: bool = False


class AgentUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    is_default: Optional[bool] = None


@app.get("/api/agents")
def list_agents(user_id: int, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    auth = _auth_user(authorization)
    if auth and auth[1] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    with session_scope() as session:
        rows = session.exec(
            select(Agent).where(Agent.user_id == user_id).order_by(Agent.updated_at.desc())
        ).all()
        return {
            "agents": [
                {
                    "id": a.id,
                    "name": a.name,
                    "description": a.description,
                    "model": a.model,
                    "system_prompt": a.system_prompt,
                    "temperature": a.temperature,
                    "max_tokens": a.max_tokens,
                    "top_p": a.top_p,
                    "presence_penalty": a.presence_penalty,
                    "frequency_penalty": a.frequency_penalty,
                    "is_default": a.is_default,
                    "created_at": a.created_at.isoformat(),
                    "updated_at": a.updated_at.isoformat()
                }
                for a in rows
            ]
        }


@app.post("/api/agents")
def create_agent(req: AgentCreateRequest) -> Dict[str, Any]:
    with session_scope() as session:
        # If this agent is set as default, unset other defaults
        if req.is_default:
            existing = session.exec(
                select(Agent).where(Agent.user_id == req.user_id).where(Agent.is_default == True)
            ).all()
            for a in existing:
                a.is_default = False

        agent = Agent(
            user_id=req.user_id,
            name=req.name.strip(),
            description=req.description.strip(),
            model=req.model,
            system_prompt=req.system_prompt,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            top_p=req.top_p,
            presence_penalty=req.presence_penalty,
            frequency_penalty=req.frequency_penalty,
            is_default=req.is_default
        )
        session.add(agent)
        session.commit()
        session.refresh(agent)
        return {
            "agent": {
                "id": agent.id,
                "name": agent.name,
                "description": agent.description,
                "model": agent.model,
                "system_prompt": agent.system_prompt,
                "temperature": agent.temperature,
                "max_tokens": agent.max_tokens,
                "top_p": agent.top_p,
                "presence_penalty": agent.presence_penalty,
                "frequency_penalty": agent.frequency_penalty,
                "is_default": agent.is_default,
                "created_at": agent.created_at.isoformat(),
                "updated_at": agent.updated_at.isoformat()
            }
        }


@app.get("/api/agents/{agent_id}")
def get_agent(agent_id: int, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    with session_scope() as session:
        agent = session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        auth = _auth_user(authorization)
        if auth and auth[1] != agent.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        return {
            "agent": {
                "id": agent.id,
                "user_id": agent.user_id,
                "name": agent.name,
                "description": agent.description,
                "model": agent.model,
                "system_prompt": agent.system_prompt,
                "temperature": agent.temperature,
                "max_tokens": agent.max_tokens,
                "top_p": agent.top_p,
                "presence_penalty": agent.presence_penalty,
                "frequency_penalty": agent.frequency_penalty,
                "is_default": agent.is_default,
                "created_at": agent.created_at.isoformat(),
                "updated_at": agent.updated_at.isoformat()
            }
        }


@app.put("/api/agents/{agent_id}")
def update_agent(agent_id: int, req: AgentUpdateRequest, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    with session_scope() as session:
        agent = session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        auth = _auth_user(authorization)
        if auth and auth[1] != agent.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        # If setting as default, unset other defaults first
        if req.is_default and not agent.is_default:
            existing = session.exec(
                select(Agent).where(Agent.user_id == agent.user_id).where(Agent.is_default == True).where(Agent.id != agent_id)
            ).all()
            for a in existing:
                a.is_default = False

        if req.name is not None:
            agent.name = req.name.strip()
        if req.description is not None:
            agent.description = req.description.strip()
        if req.model is not None:
            agent.model = req.model
        if req.system_prompt is not None:
            agent.system_prompt = req.system_prompt
        if req.temperature is not None:
            agent.temperature = req.temperature
        if req.max_tokens is not None:
            agent.max_tokens = req.max_tokens
        if req.top_p is not None:
            agent.top_p = req.top_p
        if req.presence_penalty is not None:
            agent.presence_penalty = req.presence_penalty
        if req.frequency_penalty is not None:
            agent.frequency_penalty = req.frequency_penalty
        if req.is_default is not None:
            agent.is_default = req.is_default

        agent.updated_at = datetime.utcnow()
        session.add(agent)
        session.commit()
        session.refresh(agent)
        return {
            "agent": {
                "id": agent.id,
                "name": agent.name,
                "description": agent.description,
                "model": agent.model,
                "system_prompt": agent.system_prompt,
                "temperature": agent.temperature,
                "max_tokens": agent.max_tokens,
                "top_p": agent.top_p,
                "presence_penalty": agent.presence_penalty,
                "frequency_penalty": agent.frequency_penalty,
                "is_default": agent.is_default,
                "created_at": agent.created_at.isoformat(),
                "updated_at": agent.updated_at.isoformat()
            }
        }


@app.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: int, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    with session_scope() as session:
        agent = session.get(Agent, agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        auth = _auth_user(authorization)
        if auth and auth[1] != agent.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        session.delete(agent)
        session.commit()
        return {"deleted": True}

class RagCreateCorpusRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""


class RagAddTextRequest(BaseModel):
    corpus_id: str = Field(..., min_length=1)
    source_name: str = Field("text", min_length=1)
    text: str = Field(..., min_length=1)
    embedding_model: str = Field(..., min_length=1, description="Prefixed embedding model name, e.g. Cloud:text-embedding-3-small")


class RagQueryRequest(BaseModel):
    corpus_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1)
    embedding_model: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=20)

class SummarizeMemoryRequest(BaseModel):
    user_id: int
    conversation_id: int
    model: str = Field(..., min_length=1, description="Prefixed chat model")

class TtsRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice: str = Field("alloy")
    model: str = Field("gpt-4o-mini-tts")


@app.get("/api/memory")
def list_memory(user_id: int, limit: int = 10) -> Dict[str, Any]:
    limit = max(1, min(50, limit))
    with session_scope() as session:
        rows = session.exec(
            select(MemorySummary)
            .where(MemorySummary.user_id == user_id)
            .order_by(MemorySummary.created_at.desc())
            .limit(limit)
        ).all()
        return {"memories": [{"id": m.id, "summary": m.summary, "created_at": m.created_at.isoformat()} for m in rows]}


@app.post("/api/memory/summarize")
def summarize_memory(req: SummarizeMemoryRequest) -> Dict[str, Any]:
    with session_scope() as session:
        msgs = session.exec(
            select(Message).where(Message.conversation_id == req.conversation_id).order_by(Message.created_at.asc())
        ).all()
    transcript = "\n".join([f"{m.role}: {m.content}" for m in msgs])[:20000]

    provider = infer_provider_from_model(req.model)
    pure = extract_model_name(req.model)
    prompt = (
        "Summarize the following conversation into durable user memory. "
        "Focus on stable preferences, context, goals, and facts that will help future chats. "
        "Write in bullet points. Avoid sensitive data.\n\n"
        f"{transcript}"
    )
    messages = [{"role": "system", "content": "You are a memory summarizer."}, {"role": "user", "content": prompt}]
    summary = "".join(stream_chat(provider, pure, messages)).strip()

    with session_scope() as session:
        ms = MemorySummary(user_id=req.user_id, summary=summary)
        session.add(ms)
        session.commit()
        session.refresh(ms)
        return {"memory": {"id": ms.id, "summary": ms.summary}}

@app.post("/api/voice/stt")
async def voice_stt(audio: UploadFile = File(...)) -> Dict[str, Any]:
    if not openai_client:
        raise HTTPException(status_code=400, detail="OpenAI client not configured (OPENAI_API_KEY/OPENAI_BASE_URL).")
    content = await audio.read()
    try:
        # OpenAI-compatible Whisper endpoint
        # NOTE: SDK expects a file-like. Use bytes with filename.
        from io import BytesIO

        buf = BytesIO(content)
        buf.name = audio.filename or "audio.webm"
        result = openai_client.audio.transcriptions.create(model="whisper-1", file=buf)  # type: ignore
        text = getattr(result, "text", "") or ""
        with session_scope() as session:
            session.add(UsageLog(kind="stt", model="whisper-1", input_chars=len(content), output_chars=len(text), user_id=0))
            session.commit()
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/voice/tts")
def voice_tts(req: TtsRequest) -> Response:
    if not openai_client:
        raise HTTPException(status_code=400, detail="OpenAI client not configured (OPENAI_API_KEY/OPENAI_BASE_URL).")
    try:
        speech = openai_client.audio.speech.create(  # type: ignore
            model=req.model,
            voice=req.voice,
            input=req.text,
        )
        # SDK returns a binary response-like object
        audio_bytes = speech.read() if hasattr(speech, "read") else bytes(speech)  # type: ignore
        with session_scope() as session:
            session.add(UsageLog(kind="tts", model=req.model, input_chars=len(req.text), output_chars=len(audio_bytes), user_id=0))
            session.commit()
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/models")
def list_models() -> Dict[str, Any]:
    models = model_service.list_models()
    return {
        "models": [
            {"id": m.id, "provider": m.provider, "name": m.name}
            for m in models
        ]
    }

class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1)
    locale: str = Field("en")

class SignupRequest(BaseModel):
    tenant_id: str = Field(default="default")
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)
    locale: str = Field("en")


class LoginRequest(BaseModel):
    tenant_id: str = Field(default="default")
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=6)


def _auth_user(authorization: str | None) -> tuple[str, int] | None:
    if not authorization:
        return None
    if not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    claims = verify_token(token)
    if not claims:
        return None
    return (claims.tenant_id, claims.user_id)


@app.post("/api/auth/signup")
def auth_signup(req: SignupRequest) -> Dict[str, Any]:
    tenant_id = (req.tenant_id or "default").strip() or "default"
    username = req.username.strip()
    salt = new_salt()
    pw_hash = hash_password(req.password, salt)
    with session_scope() as session:
        user = User(tenant_id=tenant_id, username=username, locale=req.locale.strip() or "en", password_salt=salt, password_hash=pw_hash)
        session.add(user)
        session.commit()
        session.refresh(user)
        token = issue_token(tenant_id=tenant_id, user_id=int(user.id))
        return {"token": token, "user": {"id": user.id, "username": user.username, "locale": user.locale, "tenant_id": user.tenant_id}}


@app.post("/api/auth/login")
def auth_login(req: LoginRequest) -> Dict[str, Any]:
    tenant_id = (req.tenant_id or "default").strip() or "default"
    username = req.username.strip()
    with session_scope() as session:
        user = session.exec(select(User).where(User.tenant_id == tenant_id).where(User.username == username)).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if user.password_hash != hash_password(req.password, user.password_salt):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = issue_token(tenant_id=tenant_id, user_id=int(user.id))
        return {"token": token, "user": {"id": user.id, "username": user.username, "locale": user.locale, "tenant_id": user.tenant_id}}


@app.post("/api/users")
def create_user(req: CreateUserRequest) -> Dict[str, Any]:
    with session_scope() as session:
        user = User(username=req.username.strip(), locale=req.locale.strip() or "en")
        session.add(user)
        session.commit()
        session.refresh(user)
        return {"user": {"id": user.id, "username": user.username, "locale": user.locale}}


@app.get("/api/conversations")
def list_conversations(user_id: int, include_archived: bool = False, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    auth = _auth_user(authorization)
    if auth and auth[1] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    with session_scope() as session:
        query = select(Conversation).where(Conversation.user_id == user_id)
        if not include_archived:
            query = query.where(Conversation.is_archived == False)
        rows = session.exec(query.order_by(Conversation.updated_at.desc())).all()
        return {"conversations": [{"id": c.id, "title": c.title, "is_archived": c.is_archived, "updated_at": c.updated_at.isoformat()} for c in rows]}


class CreateConversationRequest(BaseModel):
    user_id: int
    title: str = Field(default="New chat")


@app.post("/api/conversations")
def create_conversation(req: CreateConversationRequest) -> Dict[str, Any]:
    with session_scope() as session:
        conv = Conversation(user_id=req.user_id, title=req.title.strip() or "New chat")
        session.add(conv)
        session.commit()
        session.refresh(conv)
        return {"conversation": {"id": conv.id, "title": conv.title}}


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: int) -> Dict[str, Any]:
    with session_scope() as session:
        conv = session.get(Conversation, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        msgs = session.exec(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
        ).all()
        return {
            "conversation": {"id": conv.id, "title": conv.title},
            "messages": [{"id": m.id, "role": m.role, "content": m.content, "model": m.model} for m in msgs],
        }

@app.get("/api/rag/corpora")
def rag_list_corpora() -> Dict[str, Any]:
    corpora = rag_service.list_corpora()
    return {"corpora": [c.__dict__ for c in corpora]}


@app.post("/api/rag/corpora")
def rag_create_corpus(req: RagCreateCorpusRequest) -> Dict[str, Any]:
    corpus = rag_service.create_corpus(req.name, req.description)
    return {"corpus": corpus.__dict__}


@app.post("/api/rag/add_text")
def rag_add_text(req: RagAddTextRequest) -> Dict[str, Any]:
    count = rag_service.add_document_text(
        corpus_id=req.corpus_id,
        source_name=req.source_name,
        text=req.text,
        embedding_model=req.embedding_model,
    )
    return {"chunks_added": count}


@app.post("/api/rag/query")
def rag_query(req: RagQueryRequest) -> Dict[str, Any]:
    results = rag_service.query(
        corpus_id=req.corpus_id,
        query_text=req.query,
        embedding_model=req.embedding_model,
        top_k=req.top_k,
    )
    return {
        "results": [
            {
                "score": score,
                "chunk": {
                    "chunk_id": ch.chunk_id,
                    "source_name": ch.source_name,
                    "text": ch.text,
                },
            }
            for score, ch in results
        ]
    }


# --- User Knowledge Base Endpoints ---

class KnowledgeBaseCreateRequest(BaseModel):
    user_id: int
    name: str = Field(..., min_length=1)
    description: str = ""
    embedding_model: str = ""


class KnowledgeBaseUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    embedding_model: Optional[str] = None


@app.get("/api/knowledge")
def list_knowledge_bases(user_id: int, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    auth = _auth_user(authorization)
    if auth and auth[1] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    with session_scope() as session:
        rows = session.exec(
            select(KnowledgeBase).where(KnowledgeBase.user_id == user_id).order_by(KnowledgeBase.updated_at.desc())
        ).all()
        return {
            "knowledge_bases": [
                {
                    "id": kb.id,
                    "name": kb.name,
                    "description": kb.description,
                    "embedding_model": kb.embedding_model,
                    "created_at": kb.created_at.isoformat(),
                    "updated_at": kb.updated_at.isoformat()
                }
                for kb in rows
            ]
        }


@app.post("/api/knowledge")
def create_knowledge_base(req: KnowledgeBaseCreateRequest) -> Dict[str, Any]:
    with session_scope() as session:
        kb = KnowledgeBase(
            user_id=req.user_id,
            name=req.name.strip(),
            description=req.description.strip(),
            embedding_model=req.embedding_model
        )
        session.add(kb)
        session.commit()
        session.refresh(kb)
        return {
            "knowledge_base": {
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "embedding_model": kb.embedding_model,
                "created_at": kb.created_at.isoformat(),
                "updated_at": kb.updated_at.isoformat()
            }
        }


@app.get("/api/knowledge/{kb_id}")
def get_knowledge_base(kb_id: int, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    with session_scope() as session:
        kb = session.get(KnowledgeBase, kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        auth = _auth_user(authorization)
        if auth and auth[1] != kb.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        # Get document count
        docs = session.exec(
            select(KnowledgeDocument).where(KnowledgeDocument.knowledge_base_id == kb_id)
        ).all()
        return {
            "knowledge_base": {
                "id": kb.id,
                "user_id": kb.user_id,
                "name": kb.name,
                "description": kb.description,
                "embedding_model": kb.embedding_model,
                "document_count": len(docs),
                "created_at": kb.created_at.isoformat(),
                "updated_at": kb.updated_at.isoformat()
            }
        }


@app.put("/api/knowledge/{kb_id}")
def update_knowledge_base(kb_id: int, req: KnowledgeBaseUpdateRequest, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    with session_scope() as session:
        kb = session.get(KnowledgeBase, kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        auth = _auth_user(authorization)
        if auth and auth[1] != kb.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        if req.name is not None:
            kb.name = req.name.strip()
        if req.description is not None:
            kb.description = req.description.strip()
        if req.embedding_model is not None:
            kb.embedding_model = req.embedding_model

        kb.updated_at = datetime.utcnow()
        session.add(kb)
        session.commit()
        session.refresh(kb)
        return {
            "knowledge_base": {
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "embedding_model": kb.embedding_model,
                "created_at": kb.created_at.isoformat(),
                "updated_at": kb.updated_at.isoformat()
            }
        }


@app.delete("/api/knowledge/{kb_id}")
def delete_knowledge_base(kb_id: int, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    with session_scope() as session:
        kb = session.get(KnowledgeBase, kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        auth = _auth_user(authorization)
        if auth and auth[1] != kb.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        # Delete associated documents
        docs = session.exec(
            select(KnowledgeDocument).where(KnowledgeDocument.knowledge_base_id == kb_id)
        ).all()
        for doc in docs:
            session.delete(doc)

        session.delete(kb)
        session.commit()
        return {"deleted": True}


class KnowledgeDocAddRequest(BaseModel):
    source_name: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    embedding_model: str = Field(..., min_length=1)


@app.post("/api/knowledge/{kb_id}/documents")
def add_knowledge_document(kb_id: int, req: KnowledgeDocAddRequest, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    with session_scope() as session:
        kb = session.get(KnowledgeBase, kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        auth = _auth_user(authorization)
        if auth and auth[1] != kb.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        # Add to RAG service
        chunk_count = rag_service.add_document_text(
            corpus_id=str(kb_id),
            source_name=req.source_name,
            text=req.text,
            embedding_model=req.embedding_model,
        )

        # Create document record
        doc = KnowledgeDocument(
            user_id=kb.user_id,
            knowledge_base_id=kb_id,
            source_name=req.source_name,
            file_type="text",
            chunk_count=chunk_count
        )
        session.add(doc)
        session.commit()
        session.refresh(doc)

        return {
            "document": {
                "id": doc.id,
                "source_name": doc.source_name,
                "chunk_count": doc.chunk_count,
                "created_at": doc.created_at.isoformat()
            }
        }


@app.get("/api/knowledge/{kb_id}/documents")
def list_knowledge_documents(kb_id: int, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    with session_scope() as session:
        kb = session.get(KnowledgeBase, kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        auth = _auth_user(authorization)
        if auth and auth[1] != kb.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        docs = session.exec(
            select(KnowledgeDocument).where(KnowledgeDocument.knowledge_base_id == kb_id).order_by(KnowledgeDocument.created_at.desc())
        ).all()

        return {
            "documents": [
                {
                    "id": doc.id,
                    "source_name": doc.source_name,
                    "file_type": doc.file_type,
                    "chunk_count": doc.chunk_count,
                    "created_at": doc.created_at.isoformat()
                }
                for doc in docs
            ]
        }


# --- Conversation Update Endpoints ---

class UpdateConversationTitleRequest(BaseModel):
    title: str


@app.put("/api/conversations/{conversation_id}/title")
def update_conversation_title(conversation_id: int, req: UpdateConversationTitleRequest, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    with session_scope() as session:
        conv = session.get(Conversation, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        auth = _auth_user(authorization)
        if auth and auth[1] != conv.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        conv.title = req.title.strip() or "New Chat"
        conv.updated_at = datetime.utcnow()
        session.add(conv)
        session.commit()
        session.refresh(conv)
        return {"conversation": {"id": conv.id, "title": conv.title}}


class ArchiveConversationRequest(BaseModel):
    archived: bool


@app.put("/api/conversations/{conversation_id}/archive")
def archive_conversation(conversation_id: int, req: ArchiveConversationRequest, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    with session_scope() as session:
        conv = session.get(Conversation, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        auth = _auth_user(authorization)
        if auth and auth[1] != conv.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        conv.is_archived = req.archived
        conv.updated_at = datetime.utcnow()
        session.add(conv)
        session.commit()
        session.refresh(conv)
        return {"conversation": {"id": conv.id, "title": conv.title, "is_archived": conv.is_archived}}


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, authorization: str | None = Header(default=None)) -> Dict[str, Any]:
    with session_scope() as session:
        conv = session.get(Conversation, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        auth = _auth_user(authorization)
        if auth and auth[1] != conv.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

        # Delete associated messages
        msgs = session.exec(
            select(Message).where(Message.conversation_id == conversation_id)
        ).all()
        for msg in msgs:
            session.delete(msg)

        session.delete(conv)
        session.commit()
        return {"deleted": True}


@app.post("/api/zflow/execute")
def execute_zflow(req: ZflowRequest) -> StreamingResponse:
    def gen() -> Generator[str, None, None]:
        yield _sse_event({"type": "start"}, event="meta")
        try:
            for chunk in zflow_service.execute(req.script):
                yield _sse_event({"type": "delta", "text": chunk})
            yield _sse_event({"type": "done"}, event="meta")
        except Exception as e:
            yield _sse_event({"type": "error", "message": str(e)}, event="meta")

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    # Resolve user & conversation (optional for now)
    user_id: Optional[int] = None
    if isinstance(req.user, dict) and req.user.get("id") is not None:
        user_id = int(req.user["id"])

    conversation_id = req.conversation_id

    history_pairs: List[Tuple[str, str]] = [(t.user, t.assistant) for t in req.history]
    if conversation_id and not history_pairs:
        with session_scope() as session:
            msgs = session.exec(
                select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
            ).all()
            # convert to user/assistant turns
            turns: List[Tuple[str, str]] = []
            pending_user = ""
            for m in msgs:
                if m.role == "user":
                    pending_user = m.content
                elif m.role == "assistant":
                    turns.append((pending_user, m.content))
                    pending_user = ""
            history_pairs = turns

    routing_cfg: Optional[RoutingConfig] = None
    final_model = req.model or ""
    if req.mode == "auto":
        if not isinstance(req.routing, dict):
            raise ValueError("routing is required for auto mode")
        routing_cfg = RoutingConfig(
            classifier_model=str(req.routing.get("classifier_model", "")),
            labels=list(req.routing.get("labels", [])),
            output_models=list(req.routing.get("output_models", [])),
            custom_classifier_prompt=str(req.routing.get("custom_classifier_prompt", "") or ""),
        )

    # Helper to get the actual model after routing
    def get_final_model() -> str:
        if req.mode == "chat":
            return req.model or ""
        # For auto mode, we need to determine which model will be used
        if routing_cfg and routing_cfg.output_models:
            return routing_cfg.output_models[0]  # Return first as default
        return req.model or ""

    def gen() -> Generator[str, None, None]:
        current_model = get_final_model()
        yield _sse_event({"type": "model_info", "model": current_model}, event="meta")
        yield _sse_event({"type": "start"}, event="meta")
        try:
            system_prompt = req.system_prompt
            if user_id:
                with session_scope() as session:
                    mems = session.exec(
                        select(MemorySummary)
                        .where(MemorySummary.user_id == user_id)
                        .order_by(MemorySummary.created_at.desc())
                        .limit(5)
                    ).all()
                if mems:
                    mem_text = "\n".join([f"- {m.summary}" for m in mems]).strip()
                    system_prompt = (system_prompt or "") + (
                        ("\n\n" if system_prompt else "")
                        + "User memory (use only if relevant):\n"
                        + mem_text
                    )
            if isinstance(req.rag, dict) and req.rag.get("enabled") and req.rag.get("corpus_id"):
                corpus_id = str(req.rag.get("corpus_id"))
                embedding_model = str(req.rag.get("embedding_model") or "")
                top_k = int(req.rag.get("top_k") or 5)
                if embedding_model:
                    hits = rag_service.query(
                        corpus_id=corpus_id,
                        query_text=req.message,
                        embedding_model=embedding_model,
                        top_k=top_k,
                    )
                    context_lines = []
                    for score, ch in hits:
                        context_lines.append(f"[{ch.source_name} score={score:.4f}]\n{ch.text}")
                    context = "\n\n---\n\n".join(context_lines).strip()
                    if context:
                        rag_prompt = (
                            "Use the following retrieved context to answer the user. "
                            "If the context is insufficient, say so and ask a clarifying question.\n\n"
                            f"{context}"
                        )
                        system_prompt = (system_prompt or "") + ("\n\n" if system_prompt else "") + rag_prompt

            # Persist the user message early
            if conversation_id and user_id:
                with session_scope() as session:
                    conv = session.get(Conversation, conversation_id)
                    if conv:
                        session.add(
                            Message(
                                conversation_id=conversation_id,
                                role="user",
                                content=req.message,
                                model=req.model or "",
                            )
                        )
                        conv.updated_at = datetime.utcnow()
                        session.add(conv)
                        session.commit()

            assistant_full = ""

            for delta in chat_service.stream_chat_completion(
                user_message=req.message,
                history=history_pairs,
                mode=req.mode,
                model=req.model,
                system_prompt=system_prompt,
                routing=routing_cfg,
            ):
                assistant_full += delta
                yield _sse_event({"type": "delta", "text": delta})

            if conversation_id and user_id:
                with session_scope() as session:
                    conv = session.get(Conversation, conversation_id)
                    if conv:
                        session.add(
                            Message(
                                conversation_id=conversation_id,
                                role="assistant",
                                content=assistant_full,
                                model=req.model or "",
                            )
                        )

                        # Auto-generate title if it's the first message and title is still default
                        if conv.title == "New chat" or conv.title == "New Chat":
                            try:
                                # Get all messages for title generation
                                all_msgs = session.exec(
                                    select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
                                ).all()
                                msg_dicts = [{"role": m.role, "content": m.content} for m in all_msgs]
                                generated_title = chat_service.generate_title(msg_dicts)
                                conv.title = generated_title
                            except Exception:
                                pass  # Keep default title if generation fails

                        conv.updated_at = datetime.utcnow()
                        session.add(conv)
                        session.add(
                            UsageLog(
                                tenant_id=conv.tenant_id,
                                user_id=user_id,
                                conversation_id=conversation_id,
                                model=req.model or "",
                                kind="chat",
                                input_chars=len(req.message),
                                output_chars=len(assistant_full),
                            )
                        )
                        session.commit()
            yield _sse_event({"type": "done"}, event="meta")
        except Exception as e:
            yield _sse_event({"type": "error", "message": str(e)}, event="meta")

    return StreamingResponse(gen(), media_type="text/event-stream")

