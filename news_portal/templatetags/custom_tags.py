from datetime import datetime
import django.template
from pprint import pprint


register=django.template.Library()

@register.simple_tag()
def current_date(value):
    return datetime.strptime(value, "%d.%M.%Y")

@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
   pprint(f'tag_context={context}\nkwargs={kwargs}')
   d = context['request'].GET.copy()
   for k, v in kwargs.items():
       d[k] = v
   return d.urlencode()

@register.simple_tag
def pow(val, x):
    return val+10*x

@register.simple_tag
def dict(x: int, key: str) -> str:
    return f'{key}: {x} on {datetime.now()}'
