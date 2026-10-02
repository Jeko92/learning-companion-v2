from django.contrib import admin

from learning_sessions.models import LearningSession


@admin.register(LearningSession)
class LearningSessionAdmin(admin.ModelAdmin):
    list_display = ("goal", "date", "duration_minutes")
    list_filter = ("date",)
    # Both search through GoalAdmin and TagAdmin's search_fields.
    autocomplete_fields = ("goal", "tags")
