from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.db.models import Avg, Min, Max, StdDev

from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.dates import DateFormatter
from matplotlib.patches import Ellipse

from StringIO import StringIO

from models import Log, MonitorStatus
from utils import permission_required_or_403

import datetime, re
from db import DB

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

def status_plot(request, client, param, width=1000, height=500, hours=24.0, title=None):
    hours = float(hours) if hours else 24.0
    # delay = int(delay) if delay else 0

    # # Strip all but good characters
    # spath = re.sub('[^0-9a-zA-Z_]+', '', path)
    # spath = '\'' + path + '\''

    if request.GET:
        width = float(request.GET.get('width', width))
        height = float(request.GET.get('height', height))
        hours = float(request.GET.get('hours', hours))

    ms = MonitorStatus.objects.extra(select={"value":"(status #> '{%s}' #>> '{%s}')::float" % (client, param)}).defer('status').order_by('time')
    ms.filter(time__gt = datetime.datetime.utcnow() - datetime.timedelta(hours=hours))
    # query = "SELECT id, time, status #> '{%s}' FROM beholder_status WHERE time > %s AND time < %s ORDER BY time DESC"
    # db = DB()
    # bs = db.query(query, (spath, datetime.datetime.utcnow() - datetime.timedelta(hours=hours) - datetime.timedelta(hours=delay), datetime.datetime.utcnow() - datetime.timedelta(hours=delay)))

    if not title:
        title = client + '.' + param

    values = [_.value for _ in ms]
    time = [_.time for _ in ms]

    fig = Figure(facecolor='white', dpi=72, figsize=(width/72, height/72), tight_layout=True)
    ax = fig.add_subplot(111)
    ax.autoscale()
    ax.plot()

    ax.plot(time, values, '-', label=title)

    if time: # It is failing if no data are plotted
        ax.xaxis.set_major_formatter(DateFormatter('%Y.%m.%d %H:%M:%S'))

    ax.set_xlabel("Time, UT")
    ax.set_ylabel(param)
    ax.set_title(title)

    fig.autofmt_xdate()

    # 10% margins on both axes
    ax.margins(0.1, 0.1)

    # handles, labels = ax.get_legend_handles_labels()
    # ax.legend(handles, labels, loc=2)

    canvas = FigureCanvas(fig)
    s = StringIO()
    canvas.print_png(s)
    response = HttpResponse(s.getvalue(), content_type='image/png')

    return response
