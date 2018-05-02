from django.template.response import TemplateResponse
from django.db.models import Avg, Min, Max, StdDev

from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.dates import DateFormatter
from matplotlib.patches import Ellipse

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

def status_plot(request, param='hw_camera_temperature', title='', width=1000, height=500, hours=24, delay=0, path=''):
    hours = int(hours) if hours else 24
    delay = int(delay) if delay else 0

    # Strip all but good characters
    spath = re.sub('[^0-9a-zA-Z_]+', '', path)
    spath = '\'' + path + '\''

    query = "SELECT id, time, status #> '{%s}' FROM beholder_status WHERE time > %s AND time < %s ORDER BY time DESC"
    db = DB()
    bs = db.query(query, (spath, datetime.datetime.utcnow() - datetime.timedelta(hours=hours) - datetime.timedelta(hours=delay), datetime.datetime.utcnow() - datetime.timedelta(hours=delay)))

    if not title:
        title = path

    values = [[] for i in xrange(N)]
    time = []

    for status in bs:
        for i in xrange(N):
            values[i].append(status[2+i])

        time.append(status[1])

    fig = Figure(facecolor='white', dpi=72, figsize=(width/72, height/72), tight_layout=True)
    ax = fig.add_subplot(111)
    ax.autoscale()
    ax.set_color_cycle([cm.spectral(k) for k in np.linspace(0, 1, 9)])

    for i in xrange(N):
        if mode == 'can':
            ax.plot(time, values[i], '-', label="Chiller %d" % (i+1))
        else:
            ax.plot(time, values[i], '-', label="Channel %d" % (i+1))

    if time: # It is failing if no data are plotted
        ax.xaxis.set_major_formatter(DateFormatter('%Y.%m.%d %H:%M:%S'))

    ax.set_xlabel("Time, UT")
    ax.set_ylabel(title)

    fig.autofmt_xdate()

    # 10% margins on both axes
    ax.margins(0.1, 0.1)

    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc=2)

    canvas = FigureCanvas(fig)
    response = HttpResponse(content_type='image/png')
    canvas.print_png(response)

    return response
