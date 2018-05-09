from django.http import HttpResponse
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf.urls import include, url

import settings

import views

urlpatterns = [
    # Index
    url(r'index^$', views.index, name="index"),
    url(r'^$', views.current, name="current"),

    # Log view
    url(r'^logs(/(?P<source>\w+)?)?$', views.logs_list, name='logs'),

    # Status
    url(r'^status/?$', views.status, name='status'),
    url(r'^status/plots/(?P<client>[a-zA-Z0-9_]+)/(?P<param>[a-zA-Z0-9_]+)/?$', views.status_plot, name='status_plot'),

    # Robots
    url(r'^robots.txt$', lambda r: HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")),

    # Markdown
    #url(r'^about/(?P<path>.*)$', views_markdown.markdown_page, {'base':'about'}, name="markdown"),
]

urlpatterns += staticfiles_urlpatterns()
