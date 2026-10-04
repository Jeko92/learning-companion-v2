"""Project-wide form rendering with daisyUI.

Every form outside the admin uses StyledFormMixin, so {{ form }} renders
through templates/forms/div.html and forms/field.html, and each widget gets
its daisyUI class. The admin keeps its own forms, and no django/forms/*
template is overridden, so it renders exactly as before.
"""

from django import forms
from django.forms.widgets import Input

# First match wins: CheckboxInput is an Input, so it comes before Input.
WIDGET_CLASSES = (
    (forms.CheckboxInput, "checkbox"),
    (forms.CheckboxSelectMultiple, "checkbox"),
    (forms.RadioSelect, "radio"),
    (forms.Select, "select w-full"),
    (forms.Textarea, "textarea w-full"),
    (Input, "input w-full"),
)


def merge_classes(*values):
    return " ".join(" ".join(value for value in values if value).split())


class StyledBoundField(forms.BoundField):
    template_name = "forms/field.html"

    def build_widget_attrs(self, attrs, widget=None):
        attrs = super().build_widget_attrs(attrs, widget)
        widget = widget or self.field.widget
        if widget.is_hidden:
            return attrs
        css = next((c for kind, c in WIDGET_CLASSES if isinstance(widget, kind)), "")
        # Attrs returned here replace the widget's own class, so keep it.
        attrs["class"] = merge_classes(
            widget.attrs.get("class"), attrs.get("class"), css
        )
        return attrs

    def label_tag(self, contents=None, attrs=None, label_suffix=None, tag=None):
        attrs = {**(attrs or {})}
        attrs["class"] = merge_classes(attrs.get("class"), "fieldset-legend")
        return super().label_tag(contents, attrs, label_suffix, tag)


class StyledFormMixin:
    """Put first in a form's bases, before Form or ModelForm (its attributes
    must win over BaseForm's): class GoalForm(StyledFormMixin, forms.ModelForm)."""

    template_name = "forms/div.html"
    bound_field_class = StyledBoundField
