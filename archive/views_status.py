from django.http import HttpResponse
from django.template.response import TemplateResponse

from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.dates import DateFormatter
from matplotlib.patches import Ellipse
from matplotlib.ticker import ScalarFormatter, LogLocator, LinearLocator

import numpy as np

from StringIO import StringIO

import datetime, re

from models import MonitorStatus

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

def status_plot(request, client, param, width=1000.0, height=500.0, hours=24.0, title=None, xlabel="Time, UT", ylabel=None, ylog=False):
    hours = float(hours) if hours else 24.0
    # delay = int(delay) if delay else 0

    # # Strip all but good characters
    # spath = re.sub('[^0-9a-zA-Z_]+', '', path)
    # spath = '\'' + path + '\''

    if request.GET:
        width = float(request.GET.get('width', width))
        height = float(request.GET.get('height', height))
        hours = float(request.GET.get('hours', hours))
        if request.GET.has_key('ylog'):
            # FIXME: make it possible to pass False somehow
            ylog = True

        title = request.GET.get('title', title)
        xlabel = request.GET.get('xlabel', xlabel)
        ylabel = request.GET.get('ylabel', ylabel)

    if not ylabel:
        ylabel = param

    if not title:
        title = client + '.' + param

    ms = MonitorStatus.objects.extra(select={"value":"(status #> '{%s}' #>> '{%s}')::float" % (client, param)}).defer('status').order_by('time')
    ms = ms.filter(time__gt = datetime.datetime.utcnow() - datetime.timedelta(hours=hours))

    print ms.count()
    print datetime.datetime.utcnow() - datetime.timedelta(hours=hours)

    values = [_.value for _ in ms]
    time = [_.time for _ in ms]

    fig = Figure(facecolor='white', dpi=72, figsize=(width*1.0/72, height*1.0/72), tight_layout=True)
    ax = fig.add_subplot(111)
    ax.autoscale()
    ax.plot()

    ax.plot(time, values, '-', label=title)

    if time: # It is failing if no data are plotted
        if (time[-1] - time[0]).total_seconds() < 2*24*3600:
            ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
        elif (time[-1] - time[0]).total_seconds() > 3*24*3600:
            ax.xaxis.set_major_formatter(DateFormatter('%Y.%m.%d'))
        else:
            ax.xaxis.set_major_formatter(DateFormatter('%Y.%m.%d %H:%M:%S'))

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)

    if ylog:
        ax.set_yscale('log', nonposy='clip')

        # Try to fix the ticks if the data span is too small
        axis = ax.get_yaxis()
        if np.ptp(np.log10(axis.get_data_interval())) < 1:
            axis.set_major_locator(LinearLocator(numticks=6))

    fig.autofmt_xdate()

    # 10% margins on both axes
    ax.margins(0.03, 0.03)

    # handles, labels = ax.get_legend_handles_labels()
    # ax.legend(handles, labels, loc=2)

    canvas = FigureCanvas(fig)
    s = StringIO()
    canvas.print_png(s)
    response = HttpResponse(s.getvalue(), content_type='image/png')

    return response
