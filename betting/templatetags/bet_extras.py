from django import template

register = template.Library()

@register.filter
def mul(value, arg):
    """Multiply the arg by the value."""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def div(value, arg):
    """Divide the arg by the value."""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return ''

@register.filter
def sub(value, arg):
    """Subtract the arg from the value."""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def add(value, arg):
    """Add the arg to the value."""
    try:
        return float(value) + float(arg)
    except (ValueError, TypeError):
        return ''

@register.filter
def percentage(value):
    """Convert a value to percentage."""
    try:
        return float(value) * 100.0
    except (ValueError, TypeError):
        return ''

@register.filter
def divisibleby(value, arg):
    """Returns percentage value / arg."""
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg) * 100
    except (ValueError, TypeError, ZeroDivisionError):
        return 0 