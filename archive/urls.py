from django.http import HttpResponse
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf.urls import include, url

import settings

import views
import views_status

urlpatterns = [
    # Index
    url(r'index^$', views.index, name="index"),
    url(r'^$', views.current, name="current"),

    # Log view
    url(r'^logs(/(?P<source>[a-zA-Z0-9_\-/.,]+)?)?$', views.logs_list, name='logs'),

    # Status
    url(r'^status/?$', views_status.status, name='status'),
    url(r'^status/plots/(?P<params>[a-zA-Z0-9_\-/.,]+)/?$', views_status.status_plot, name='status_plot'),

    # Robots
    url(r'^robots.txt$', lambda r: HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")),

    # Markdown
    #url(r'^about/(?P<path>.*)$', views_markdown.markdown_page, {'base':'about'}, name="markdown"),

    # MONITOR proxy
    url(r'^monitor/?$', views.monitor, name="monitor"),
]

urlpatterns += staticfiles_urlpatterns()

# if settings.DEBUG:
#     import debug_toolbar
#     urlpatterns = [
#         url(r'^__debug__/', include(debug_toolbar.urls)),
#     ] + urlpatterns
