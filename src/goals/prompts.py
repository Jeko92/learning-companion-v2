"""Prompts for the goal pages' AI features. Pure functions: the views gather
the data (through owned_by) and pass it in."""

from learning_sessions.templatetags.session_format import duration

SUMMARY_SYSTEM = (
    "You are a learning coach. From the learner's goal, sessions and resources, "
    "write a short progress summary in two to four sentences: the time spent, "
    "what has been covered, and the next focus. Address the learner as 'you'."
)


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
    return SUMMARY_SYSTEM, "\n".join(lines)
