# tienda/custom_filters.py
from django import template

register = template.Library()

@register.filter
def restar(value, arg):
    return value - arg
