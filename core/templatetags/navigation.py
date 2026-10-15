from django import template
from core.navigation import canonical_url

register = template.Library()
register.simple_tag(canonical_url, name='page_url')
