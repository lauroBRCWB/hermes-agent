from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from gateway.config import Platform
from gateway.platforms.event import MessageEvent
from gateway.plugin_command_context import GatewayPluginCommandContext
from gateway.session import SessionSource


def _source(user_id: str = "client-a") -> SessionSource:
    return SessionSource(
        platform=Platform.TELEGRAM,
        user_id=user_id,
        chat_id=f"chat-{user_id}",
        chat_type="dm",
    )


@pytest.mark.asyncio
async def test_archive_and_reset_titles_current_session_then_uses_gateway_boundary():
    source = _source()
    event = MessageEvent(text="/nova A estrela", source=source, message_id="m1")
    entry = SimpleNamespace(session_id="session-current")
    session_db = SimpleNamespace(set_session_title=AsyncMock(return_value=True))
    runner = SimpleNamespace(
        async_session_store=SimpleNamespace(get_or_create_session=AsyncMock(return_value=entry)),
        _session_db=session_db,
        _handle_reset_command=AsyncMock(),
    )

    context = GatewayPluginCommandContext(runner, event, source)
    await context.archive_and_reset("A estrela")

    session_db.set_session_title.assert_awaited_once_with("session-current", "A estrela")
    reset_event = runner._handle_reset_command.await_args.args[0]
    assert reset_event.text == "/new"
    assert event.text == "/nova A estrela"


@pytest.mark.asyncio
async def test_resume_uses_gateway_owner_checked_handler_and_preserves_original_event():
    source = _source()
    event = MessageEvent(text="/antiga 2", source=source, message_id="m1")
    runner = SimpleNamespace(_handle_resume_command=AsyncMock(return_value="resumed"))

    context = GatewayPluginCommandContext(runner, event, source)
    result = await context.resume_own_session("2")

    assert result == "resumed"
    resume_event = runner._handle_resume_command.await_args.args[0]
    assert resume_event.text == "/resume 2"
    assert event.text == "/antiga 2"
