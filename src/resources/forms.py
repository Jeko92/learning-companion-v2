from django import forms

from resources.models import Resource


class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        # An explicit allow-list: the goal comes from the URL, never the form.
        fields = ("url", "title", "type")
