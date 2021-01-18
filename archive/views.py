from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.db.models import Avg, Min, Max, StdDev

try:
    from models import Log, MonitorStatus
    from utils import permission_required_or_403
except:
    from . models import Log, MonitorStatus
    from . utils import permission_required_or_403

import datetime, re
from db import DB

def index(request):
    context = {}

    return TemplateResponse(request, 'index.html', context=context)

def current(request):
    context = {}

    return TemplateResponse(request, 'current.html', context=context)

def monitor(request):
    return TemplateResponse(request, 'monitor.html', context={})

def logs_list(request, source='all'):
    if not source or source == 'all':
        logs = Log.objects.order_by('-time')
        source = 'all'
    else:
        logs = Log.objects.order_by('-time').filter(source=source)

    sources = [l['source'] for l in Log.objects.values('source').distinct()]
    sources.append('all')

    context = {'logs':logs, 'source':source, 'sources':sources}

    return TemplateResponse(request, 'logs.html', context=context)
