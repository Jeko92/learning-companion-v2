"""django-axes hooks (see the AXES_* settings)."""

from axes.conf import settings


def lockout_username(request, credentials=None):
    """The username a failed log-in is counted under, casefolded, so "Alice"
    and "ALICE" share one counter even where the database matches usernames
    regardless of case (sign-up already rejects case-only duplicates)."""
    field = settings.AXES_USERNAME_FORM_FIELD
    if credentials:
        username = credentials.get(field)
    else:
        username = getattr(request, "data", request.POST).get(field)
    return username.casefold() if isinstance(username, str) else username
