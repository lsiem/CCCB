"""LLM-as-Judge for evaluating task execution results."""
from __future__ import annotations

import json
from typing import Optional

from .models import TaskDefinition

# Try to import SDK components; if unavailable, use stubs
try:
    from claude_agent_sdk import query, ClaudeAgentOptions
    from claude_agent_sdk.models import TextBlock
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    query = None
    ClaudeAgentOptions = None
    TextBlock = None


def build_judge_prompt(task: TaskDefinition, git_diff: str) -> str:
    """
    Build a German-language judge prompt for evaluating task completion.

    Args:
        task: The task definition with description and criteria
        git_diff: The git diff showing changes (or empty string if none)

    Returns:
        A formatted prompt for the judge LLM
    """
    # Handle empty diff
    if not git_diff or not git_diff.strip():
        diff_section = "Kein Code generiert"
    else:
        # Truncate if too large
        if len(git_diff) > 50000:
            diff_section = git_diff[:50000] + "\n... (gekürzt)"
        else:
            diff_section = git_diff

    # Build criteria section from judge criteria
    criteria_text = ""
    if task.judge and task.judge.criteria:
        criteria_text = "\n".join(f"- {c}" for c in task.judge.criteria)
    else:
        criteria_text = "- Keine spezifischen Kriterien definiert"

    # Build scoring anchors
    scoring_anchors = """
Bewertungsskala:
- 1-2: Unzureichend - Aufgabe nicht verstanden oder nicht gelöst
- 3-4: Schwach - Grundlegende Fehler oder unvollständige Lösung
- 5-6: Befriedigend - Funktioniert mit kleineren Mängeln
- 7-8: Gut - Löst die Aufgabe effektiv und korrekt
- 9-10: Ausgezeichnet - Perfekte oder nahezu perfekte Lösung
"""

    prompt = f"""Du bist ein Bewerter für ein Benchmark-Test System für Claude Code.

Aufgabe: {task.name}
Beschreibung: {task.description}
Originalanfrage: {task.prompt}

Kriterien für die Bewertung:
{criteria_text}

{scoring_anchors}

Code-Änderungen:
```
{diff_section}
```

Bitte bewerte die Lösung basierend auf den Kriterien.

Antworte in folgendem JSON-Format (nur JSON, nichts anderes):
{{
  "scores": {{"criterion_1": 8.0, "criterion_2": 7.5}},
  "reasoning": "Deine detaillierte Bewertung hier"
}}

Stelle sicher, dass alle Werte zwischen 1.0 und 10.0 liegen."""

    return prompt


def parse_judge_response(response_text: str) -> tuple[dict[str, float], str]:
    """
    Parse the judge LLM response.

    Args:
        response_text: The raw response from the judge LLM

    Returns:
        Tuple of (scores dict, reasoning string)

    Raises:
        ValueError: If JSON is invalid or required fields are missing
    """
    # Try to extract JSON from response
    try:
        # First, try direct JSON parsing
        data = json.loads(response_text)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        if start_idx == -1 or end_idx == 0:
            raise ValueError("Could not find JSON in response")
        
        try:
            data = json.loads(response_text[start_idx:end_idx])
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in response: {str(e)}")

    # Validate required fields
    if 'scores' not in data:
        raise ValueError("Missing 'scores' field in response")

    scores = data['scores']
    if not isinstance(scores, dict):
        raise ValueError("'scores' must be a dictionary")

    # Clamp scores to 1.0-10.0 range
    clamped_scores = {}
    for key, value in scores.items():
        try:
            val = float(value)
            clamped_scores[key] = max(1.0, min(10.0, val))
        except (TypeError, ValueError):
            clamped_scores[key] = 5.0  # Default to middle score if invalid

    reasoning = data.get('reasoning', 'Keine Begründung vorhanden')

    return clamped_scores, reasoning


async def evaluate_run(
    task: TaskDefinition,
    git_diff: str,
    working_dir: str = ".",
) -> tuple[dict[str, float], str]:
    """
    Evaluate a task execution using the judge LLM.

    Args:
        task: The task definition
        git_diff: The git diff output
        working_dir: Working directory (for SDK options)

    Returns:
        Tuple of (scores dict, reasoning string)
    """
    if not SDK_AVAILABLE:
        raise RuntimeError(
            "claude-agent-sdk not installed. "
            "Cannot evaluate runs without the SDK."
        )

    # Build judge prompt
    prompt = build_judge_prompt(task, git_diff)

    # Create options with no tools and max 1 turn
    options = ClaudeAgentOptions(
        cwd=working_dir,
        allowed_tools=[],
        permission_mode="dangerouslySkipPermissions",
        max_turns=1,
    )

    # Query the judge
    full_response = ""
    async for message in query(prompt=prompt, options=options):
        if TextBlock and hasattr(message, 'content'):
            for block in message.content:
                if TextBlock and isinstance(block, TextBlock):
                    full_response += block.text

    # Parse response
    scores, reasoning = parse_judge_response(full_response)

    return scores, reasoning
