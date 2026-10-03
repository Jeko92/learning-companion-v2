"""Prompts for the goal pages' AI features. Pure functions: the views gather
the data (through owned_by) and pass it in."""

from ai.services import AIServiceError
from learning_sessions.templatetags.session_format import duration

SUMMARY_SYSTEM = (
    "You are a learning coach. From the learner's goal, sessions and resources, "
    "write a short progress summary in two to four sentences: the time spent, "
    "what has been covered, and the next focus. Address the learner as 'you'."
)

NEXT_STEPS_SYSTEM = (
    "You are a learning coach. From the learner's goal, sessions and resources, "
    "suggest 2 to 3 concrete, actionable next learning steps that build on what "
    "has been done; don't repeat the resources already attached. If there are no "
    "sessions yet, suggest how to start. Each step is one short sentence "
    "addressed to the learner as 'you'. Reply with a JSON object whose `steps` "
    "list holds the steps in the order to do them."
)

# The Structured Outputs schema for the reply. No minItems/maxItems: strict
# mode's support for them is unconfirmed, and an unsupported keyword would make
# every request fail; parse_next_steps() enforces the count instead.
NEXT_STEPS_SCHEMA = {
    "type": "object",
    "properties": {"steps": {"type": "array", "items": {"type": "string"}}},
    "required": ["steps"],
    "additionalProperties": False,
}


def parse_next_steps(reply):
    """The steps from a complete_json() reply, trimmed, blank ones dropped.
    Anything else than 2-3 strings is the AI service's unexpected reply."""
    steps = reply.get("steps")
    if not isinstance(steps, list) or not all(isinstance(s, str) for s in steps):
        steps = []
    steps = [step.strip() for step in steps if step.strip()]
    if not 2 <= len(steps) <= 3:
        raise AIServiceError("The AI service returned an unexpected reply.")
    return steps


def one_line(text):
    """Free text on one line, so it can't break the prompt's structure."""
    return " ".join(text.split())


def session_line(session):
    line = f"- {session.date:%Y-%m-%d}, {duration(session.duration_minutes)}"
    tags = [tag.name for tag in session.tags.all()]
    if tags:
        line += f", tags: {', '.join(tags)}."
    if session.notes.strip():
        line += f" Notes: {one_line(session.notes)}"
    return line


def resource_line(resource):
    title, kind = one_line(resource.title), resource.get_type_display()
    return f"- {title} ({kind}): {resource.url}"


def summary_messages(goal, sessions, total_minutes, resources):
    """(system, user) for the progress summary of `goal`: `sessions` newest
    first (tags prefetched), the total time over all its sessions, and
    `resources`."""
    return SUMMARY_SYSTEM, goal_message(goal, sessions, total_minutes, resources)


def next_steps_messages(goal, sessions, total_minutes, resources):
    """(system, user) for 2-3 next learning steps; the same goal description
    as the summary's."""
    return NEXT_STEPS_SYSTEM, goal_message(goal, sessions, total_minutes, resources)


def goal_message(goal, sessions, total_minutes, resources):
    """The user message both features send: the goal, `sessions` newest first
    (tags prefetched), the total time over all its sessions, and
    `resources`."""
    description = one_line(goal.description) or "No description."
    lines = [
        f"Goal: {one_line(goal.title)}",
        f"Status: {goal.get_status_display()}",
        f"Description: {description}",
        f"Total time: {duration(total_minutes)}",
        "",
        "Recent sessions, newest first:",
        *([session_line(s) for s in sessions] or ["No sessions."]),
        "",
        "Resources:",
        *([resource_line(r) for r in resources] or ["No resources."]),
    ]
    return "\n".join(lines)
