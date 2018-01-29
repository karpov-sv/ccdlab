from django.http import HttpResponse
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf.urls import include, url

import settings

import views

urlpatterns = [
    # Index
    url(r'^$', views.index, name="index"),

    # Log view
    url(r'^logs(/(?P<source>\w+)?)?$', views.logs_list, name='logs'),

    # Status
    url(r'^status/?$', views.status, name='status'),

    # Robots
    url(r'^robots.txt$', lambda r: HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")),

    # Markdown
    #url(r'^about/(?P<path>.*)$', views_markdown.markdown_page, {'base':'about'}, name="markdown"),
]

urlpatterns += staticfiles_urlpatterns()
