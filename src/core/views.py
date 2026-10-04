from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.http import FileResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_safe


@login_not_required
def home(request):
    return render(request, "home.html")


@require_safe
@cache_control(public=True, max_age=86400)
def favicon(request):
    """The committed favicon.ico at /favicon.ico, where browsers and tools look
    for it without reading the page's <link rel="icon">. Public, like the
    static files it comes from."""
    path = Path(settings.STATICFILES_DIRS[0]) / "favicon.ico"
    return FileResponse(path.open("rb"), content_type="image/x-icon")
