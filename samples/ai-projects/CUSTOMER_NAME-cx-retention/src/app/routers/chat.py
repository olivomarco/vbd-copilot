"""Chat endpoints -- streaming responses and feedback.

POST /api/v1/chat          -- SSE-streamed chat completion
POST /api/v1/chat/feedback -- thumbs-up / thumbs-down rating
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import ChatRequest, ChatStreamEvent, FeedbackRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("")
async def chat(body: ChatRequest, request: Request) -> EventSourceResponse:
    """Handle a user chat message and stream the assistant response via SSE.

    Each SSE event carries a JSON payload:
      ``data: {"token": "...", "done": false}``
    The final event includes session_id and message_id:
      ``data: {"token": "", "done": true, "session_id": "...", "message_id": "..."}``

    Args:
        body: ChatRequest with the user message (and optional session_id / bill_ref).

    Returns:
        EventSourceResponse streaming tokens as Server-Sent Events.
    """
    conversation_manager = request.app.state.conversation_manager
    rag_pipeline = request.app.state.rag_pipeline

    # 1. Get or create session
    session = await conversation_manager.get_or_create_session(
        session_id=body.session_id,
        bill_ref=body.bill_ref,
    )
    session_id: str = session["sessionId"]

    # 2. Load conversation history (before saving current message to avoid duplication)
    history = await conversation_manager.get_conversation_history(
        session_id=session_id,
        limit=10,
    )
    conversation_turn = len([m for m in history if m.get("role") == "user"]) + 1

    # 3. Save user message
    await conversation_manager.save_message(
        session_id=session_id,
        role="user",
        content=body.message,
    )

    # 4. Stream response (history does not include current message; rag_pipeline appends it)
    async def event_generator() -> AsyncGenerator[str, None]:
        """Yield SSE data lines with incremental tokens."""
        collected_tokens: list[str] = []
        classification = None

        try:
            async for token, cls in rag_pipeline.process_query(
                session_id=session_id,
                message=body.message,
                conversation_history=history,
                bill_ref=body.bill_ref,
                conversation_turn=conversation_turn,
            ):
                classification = cls
                collected_tokens.append(token)
                event = ChatStreamEvent(token=token, done=False)
                yield json.dumps(event.model_dump())

        except Exception:
            logger.exception("Error during RAG pipeline streaming")
            error_event = ChatStreamEvent(
                token="Mi scuso, si e' verificato un errore. Riprova tra qualche istante.",
                done=True,
            )
            yield json.dumps(error_event.model_dump())
            return

        # 5. Save assistant message with metadata
        full_response = "".join(collected_tokens)
        metadata = {}
        if classification:
            metadata["model_used"] = classification.model

        message_id = await conversation_manager.save_message(
            session_id=session_id,
            role="assistant",
            content=full_response,
            metadata=metadata,
        )

        # 6. Send final event
        final_event = ChatStreamEvent(
            token="",
            done=True,
            session_id=session_id,
            message_id=message_id,
        )
        yield json.dumps(final_event.model_dump())

    return EventSourceResponse(event_generator(), media_type="text/event-stream")


@router.post("/feedback", status_code=200)
async def submit_feedback(body: FeedbackRequest, request: Request) -> dict:
    """Record user feedback (thumbs up/down) for an assistant message.

    Args:
        body: FeedbackRequest with session_id, message_id, rating, and optional comment.

    Returns:
        Confirmation dict with the feedback record ID.
    """
    feedback_service = request.app.state.feedback_service

    try:
        feedback_id = await feedback_service.save_feedback(
            session_id=body.session_id,
            message_id=body.message_id,
            rating=body.rating,
            comment=body.comment,
        )
    except Exception:
        logger.exception("Failed to save feedback")
        raise HTTPException(status_code=500, detail="Failed to save feedback")

    return {"feedback_id": feedback_id, "status": "recorded"}
