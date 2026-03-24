"""Session management endpoints.

GET    /api/v1/sessions/{session_id} -- retrieve session info + message history
DELETE /api/v1/sessions/{session_id} -- GDPR erasure of all session data
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import SessionResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, request: Request) -> SessionResponse:
    """Retrieve session metadata and full message history.

    Args:
        session_id: UUID of the conversation session.

    Returns:
        SessionResponse including ordered messages.

    Raises:
        HTTPException 404: If session is not found.
    """
    conversation_manager = request.app.state.conversation_manager
    session = await conversation_manager.get_session(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str, request: Request) -> None:
    """GDPR erasure: delete session, all messages, and all feedback.

    Args:
        session_id: UUID of the session to permanently erase.

    Raises:
        HTTPException 404: If session is not found.
    """
    conversation_manager = request.app.state.conversation_manager
    deleted = await conversation_manager.delete_session(session_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info("Session %s erased (GDPR)", session_id)
