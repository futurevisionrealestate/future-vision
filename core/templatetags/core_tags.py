from decimal import Decimal, InvalidOperation

from django import template
from django.utils.html import format_html
from django.utils.translation import get_language

from core.i18n import translate_label, translations

register = template.Library()


@register.simple_tag(takes_context=True)
def t(context, key):
    lang = context.get("current_language") or get_language()
    return translations(lang).get(key, key)


@register.filter
def tr(value):
    return translate_label(str(value))


@register.filter
def money(value):
    if value in (None, ""):
        return "—"
    try:
        return f"PKR {Decimal(value):,.0f}"
    except (InvalidOperation, TypeError, ValueError):
        return value


@register.filter
def number(value):
    if value in (None, ""):
        return "0"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return value


@register.filter
def pct(value):
    try:
        return f"{int(value)}%"
    except (TypeError, ValueError):
        return "0%"


@register.filter
def initials(value):
    words = str(value or "").strip().split()
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[-1][0]).upper()


@register.filter
def status_tone(value):
    return {
        "PENDING": "warning",
        "UNDER_REVIEW": "info",
        "APPROVED": "success",
        "REJECTED": "danger",
        "DRAFT": "muted",
        "SOLD": "success",
        "RENTED": "success",
        "INACTIVE": "muted",
        "ACTIVE": "success",
        "CONVERTED": "success",
        "OPEN": "info",
        "NEGOTIATION": "warning",
        "CLOSED_WON": "success",
        "CLOSED_LOST": "danger",
        "CANCELLED": "muted",
    }.get(str(value).upper(), "muted")


@register.filter
def role_tone(value):
    return {
        "CEO": "gold",
        "ADMIN": "gold",
        "HEAD_OFFICE": "info",
        "BRANCH_MANAGER": "navy",
        "FO": "success",
        "DEALER": "warning",
    }.get(str(value).upper(), "muted")


@register.filter
def field_class(field):
    widget = field.field.widget
    name = widget.__class__.__name__.lower()
    if name in {"checkboxinput"}:
        return "checkbox"
    if name in {"select", "selectmultiple"}:
        return "form-select"
    if name in {"textarea"}:
        return "form-textarea"
    return "form-input"


@register.simple_tag(takes_context=True)
def query_replace(context, **kwargs):
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()


@register.filter
def attr(obj, name):
    return getattr(obj, name, "")


@register.filter
def badge(text, tone="muted"):
    return format_html('<span class="badge badge--{}">{}</span>', tone, text)


@register.filter
def progress_width(value):
    try:
        return f"{min(100, max(0, int(float(value))))}%"
    except (TypeError, ValueError):
        return "0%"
