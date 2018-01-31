from django.template.response import TemplateResponse
from django.db.models import Avg, Min, Max, StdDev

from models import Log, MonitorStatus
from utils import permission_required_or_403

import datetime

def index(request):
    context = {}

    return TemplateResponse(request, 'index.html', context=context)

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

def parse_time(string):
    # FIXME: parse more time formats!
    return datetime.datetime.strptime(string, "%Y.%m.%d %H:%M:%S")

def status(request):
    context = {}

    timestamp = None

    if request.method == 'POST':
        time_string = request.POST.get('time')
        timestamp = parse_time(time_string)
    elif request.method == 'GET':
        if request.GET.has_key('time'):
            time_string = request.GET.get('time')
            timestamp = parse_time(time_string)

    if timestamp:
        status = MonitorStatus.objects.filter(time__lte=timestamp).order_by('-time').first()

        if status:
            context['status'] = status.status
            context['time'] = status.time

        context['timestamp'] = timestamp

    return TemplateResponse(request, 'status.html', context=context)
