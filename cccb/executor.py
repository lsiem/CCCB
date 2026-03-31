"""Claude Code executor via claude-agent-sdk."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .models import TaskDefinition

# Try to import SDK components; if unavailable, use stubs
try:
    from claude_agent_sdk import query, ClaudeAgentOptions
    from claude_agent_sdk.models import AssistantMessage, ToolUseBlock, TextBlock
    from claude_agent_sdk.errors import (
        CLINotFoundError,
        ProcessError,
        CLIJSONDecodeError,
    )
    SDK_AVAILABLE = True
except ImportError:
    # SDK not installed; create stubs
    SDK_AVAILABLE = False
    query = None
    ClaudeAgentOptions = None
    AssistantMessage = None
    ToolUseBlock = None
    TextBlock = None
    CLINotFoundError = None
    ProcessError = None
    CLIJSONDecodeError = None


@dataclass
class ExecutionEvent:
    """Event emitted during task execution (for TUI streaming)."""
    type: str  # e.g., "start", "message", "tool_use", "complete"
    detail: str


@dataclass
class ExecutionResult:
    """Result of executing a task."""
    duration_ms: int
    duration_api_ms: int
    total_cost_usd: float
    num_turns: int
    session_id: str
    is_error: bool = False
    timed_out: bool = False
    tool_uses: list[str] = field(default_factory=list)


async def execute_task(
    task: TaskDefinition,
    working_dir: Path,
    on_event: Optional[Callable[[ExecutionEvent], None]] = None,
) -> ExecutionResult:
    """
    Execute a task using claude-agent-sdk.

    Args:
        task: Task definition with prompt and settings
        working_dir: Working directory where the agent runs
        on_event: Optional callback for execution events (for TUI streaming)

    Returns:
        ExecutionResult with metrics and status
    """
    if not SDK_AVAILABLE:
        raise RuntimeError(
            "claude-agent-sdk not installed. "
            "Cannot execute tasks without the SDK."
        )

    start_time = time.time()
    session_id = f"exec-{int(start_time * 1000)}"
    tool_uses = []
    num_turns = 0
    duration_api_ms = 0
    total_cost_usd = 0.0
    is_error = False
    timed_out = False

    # Get settings from task or use defaults
    settings = task.claude_settings or type('obj', (object,), {
        'max_turns': 5,
        'allowed_tools': None,
        'timeout': 300,
    })()

    try:
        # Build ClaudeAgentOptions
        options = ClaudeAgentOptions(
            cwd=str(working_dir),
            allowed_tools=settings.allowed_tools,
            permission_mode="dangerouslySkipPermissions",
            max_turns=settings.max_turns,
        )

        # Execute with timeout
        timeout_seconds = settings.timeout
        try:
            # Create a task for the query iteration
            async def run_iteration():
                nonlocal num_turns, duration_api_ms, total_cost_usd, tool_uses
                
                async for message in query(prompt=task.prompt, options=options):
                    num_turns += 1

                    # Emit event for TUI
                    if on_event:
                        on_event(ExecutionEvent(
                            type="message",
                            detail=f"Turn {num_turns}",
                        ))

                    # Extract metrics from message if available
                    if hasattr(message, 'duration_ms') and message.duration_ms:
                        duration_api_ms = message.duration_ms
                    if hasattr(message, 'cost_usd') and message.cost_usd:
                        total_cost_usd += message.cost_usd

                    # Track tool uses from AssistantMessage
                    if AssistantMessage and isinstance(message, AssistantMessage):
                        if hasattr(message, 'content'):
                            for block in message.content:
                                if ToolUseBlock and isinstance(block, ToolUseBlock):
                                    tool_uses.append(block.type if hasattr(block, 'type') else 'unknown')

            # Run with timeout using wait_for (Python 3.10 compatible)
            await asyncio.wait_for(run_iteration(), timeout=timeout_seconds)

        except asyncio.TimeoutError:
            timed_out = True
            if on_event:
                on_event(ExecutionEvent(
                    type="timeout",
                    detail=f"Execution timed out after {timeout_seconds}s",
                ))

    except Exception as e:
        # Check if it's a known SDK error type
        if CLINotFoundError and isinstance(e, CLINotFoundError):
            is_error = True
            if on_event:
                on_event(ExecutionEvent(
                    type="error",
                    detail=f"CLI not found: {str(e)}",
                ))
            raise RuntimeError(f"Claude CLI not found: {str(e)}") from e
        
        elif ProcessError and isinstance(e, ProcessError):
            is_error = True
            if on_event:
                on_event(ExecutionEvent(
                    type="error",
                    detail=f"Process error: {str(e)}",
                ))
        
        elif CLIJSONDecodeError and isinstance(e, CLIJSONDecodeError):
            is_error = True
            if on_event:
                on_event(ExecutionEvent(
                    type="error",
                    detail=f"JSON decode error: {str(e)}",
                ))
        
        elif isinstance(e, asyncio.TimeoutError):
            # Already handled above
            pass
        
        else:
            # Unexpected error
            is_error = True
            if on_event:
                on_event(ExecutionEvent(
                    type="error",
                    detail=f"Unexpected error: {str(e)}",
                ))

    # Calculate total duration
    end_time = time.time()
    duration_ms = int((end_time - start_time) * 1000)

    result = ExecutionResult(
        duration_ms=duration_ms,
        duration_api_ms=duration_api_ms,
        total_cost_usd=total_cost_usd,
        num_turns=num_turns,
        session_id=session_id,
        is_error=is_error,
        timed_out=timed_out,
        tool_uses=tool_uses,
    )

    if on_event:
        on_event(ExecutionEvent(
            type="complete",
            detail=f"Execution completed in {duration_ms}ms",
        ))

    return result
