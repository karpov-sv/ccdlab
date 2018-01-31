from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
from django.db.models import Avg, Min, Max, StdDev
from django.core.urlresolvers import reverse

import datetime, re
import numpy as np
import markdown

from archive import settings

register = template.Library()

@register.filter
def subtract(value, arg):
    return value - arg

@register.filter
def GET_remove(value, key):
    value = value.copy()

    if key in value:
        value.pop(key)

    return value

@register.filter
def GET_append(value, key, new=1):
    value = value.copy()

    if key in value:
        value.pop(key)

    if '=' in key:
        s = key.split('=')
        value.appendlist(s[0], s[1])
    else:
        value.appendlist(key, new)

    return value

@register.filter
def GET_urlencode(value):
    return value.urlencode()

@register.filter
def fromtimestamp(value):
    return datetime.datetime.fromtimestamp(float(value))

@register.filter
def make_label(text, type="primary"):
    return mark_safe("<span class='label label-" + type + "'>" + text + "</span>");

@register.filter
def urlify_news(string):
    string = re.sub(r'\b(\d\d\d\d_\d\d_\d\d)\b', night_url, string)

    return mark_safe(string)

@register.filter
def night_date(night):
    return datetime.datetime.strptime(night.night, '%Y_%m_%d')

@register.filter
def linecount(text):
    return 0

@register.filter
def to_sexadecimal(value, plus=False):
    avalue = np.abs(value)
    deg = int(np.floor(avalue))
    min = int(np.floor(60.0*(avalue - deg)))
    sec = 3600.0*(avalue - deg - 1.0*min/60)

    string = '%02d %02d %04.1f' % (deg, min, sec)

    if value < 0:
        string = '-' + string
    elif plus:
        string = '+' + string

    return string

@register.filter
def to_sexadecimal_plus(value):
    return to_sexadecimal(value, plus=True)

@register.filter
def to_sexadecimal_hours(value):
    return to_sexadecimal(value*1.0/15)

@register.filter
def split(value, arg):
    return value.split(arg)

@register.filter
def markdownify(text):
    # safe_mode governs how the function handles raw HTML
    return markdown.markdown(text, safe_mode='escape')

@register.filter
def get(d, key):
    return d.get(key, '')

@register.filter
def seconds_since(t, t0):
    return (t - t0).total_seconds()
