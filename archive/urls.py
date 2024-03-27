from django.http import HttpResponse
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, re_path

try:
    import settings
    import views
    import views_status
except:
    from . import settings,views,views_status

urlpatterns = [
    # Index
    re_path(r'index^$', views.index, name="index"),
    re_path(r'^$', views.current, name="current"),

    # Log view
    re_path(r'^logs(/(?P<source>[a-zA-Z0-9_\-/.,]+)?)?$', views.logs_list, name='logs'),

    # Status
    re_path(r'^status/?$', views_status.status, name='status'),
    re_path(r'^status/plots/(?P<params>[a-zA-Z0-9_\-/.,]+)/?$', views_status.status_plot, name='status_plot'),

    # Robots
    re_path(r'^robots.txt$', lambda r: HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")),

    # Markdown
    #url(r'^about/(?P<path>.*)$', views_markdown.markdown_page, {'base':'about'}, name="markdown"),

    # MONITOR proxy
    re_path(r'^monitor/?$', views.monitor, name="monitor"),
]

urlpatterns += staticfiles_urlpatterns()

# if settings.DEBUG:
#     import debug_toolbar
#     urlpatterns = [
#         url(r'^__debug__/', include(debug_toolbar.urls)),
#     ] + urlpatterns
