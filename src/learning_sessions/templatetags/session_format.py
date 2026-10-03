from django import template

register = template.Library()


@register.filter
def duration(minutes):
    """Whole minutes as hours and minutes: "45 min", "2 h", "1 h 30 min".
    No minutes at all (an empty Sum() is None) read as "0 min"."""
    hours, minutes = divmod(minutes or 0, 60)
    if not hours:
        return f"{minutes} min"
    if not minutes:
        return f"{hours} h"
    return f"{hours} h {minutes} min"
