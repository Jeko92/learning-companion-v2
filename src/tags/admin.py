from django.contrib import admin

from tags.models import Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    # The search also backs autocomplete widgets that pick tags.
    search_fields = ("name",)
