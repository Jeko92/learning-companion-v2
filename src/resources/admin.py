from django.contrib import admin

from resources.models import Resource


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "type", "goal", "created_at")
    list_filter = ("type",)
    search_fields = ("title", "url")
    # Relies on GoalAdmin.search_fields.
    autocomplete_fields = ("goal",)
