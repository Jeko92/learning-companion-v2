"""Project-wide form rendering with daisyUI.

Every form outside the admin uses StyledFormMixin, so {{ form }} renders
through templates/forms/div.html and forms/field.html, and each widget gets
its daisyUI class. The admin keeps its own forms, and no django/forms/*
template is overridden, so it renders exactly as before.
"""

from django import forms
from django.forms.widgets import Input

# (widget type, classes, extra classes when the field has errors). First match
# wins: CheckboxInput is an Input, so it comes before Input. The class names
# are spelled out so Tailwind's source scan finds them.
WIDGET_CLASSES = (
    (forms.CheckboxInput, "checkbox", "checkbox-error"),
    (forms.CheckboxSelectMultiple, "checkbox", "checkbox-error"),
    (forms.RadioSelect, "radio", "radio-error"),
    (forms.Select, "select w-full", "select-error"),
    (forms.Textarea, "textarea w-full", "textarea-error"),
    (Input, "input w-full", "input-error"),
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
        css, error_css = next(
            ((c, e) for kind, c, e in WIDGET_CLASSES if isinstance(widget, kind)),
            ("", ""),
        )
        # Attrs returned here replace the widget's own class, so keep it.
        attrs["class"] = merge_classes(
            widget.attrs.get("class"),
            attrs.get("class"),
            css,
            error_css if self.errors else "",
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
