from __future__ import unicode_literals

from django.db import models
from django.contrib.postgres.fields import JSONField

class Log(models.Model):
    time = models.DateTimeField(blank=True, null=True)
    source = models.TextField(blank=True, null=True)
    type = models.TextField(blank=True, null=True)
    message = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'log'
        app_label = 'ccdlab'

class MonitorStatus(models.Model):
    time = models.DateTimeField(blank=True, null=True)
    status = JSONField(blank=True, null=True)  # This field type is a guess.

    class Meta:
        managed = False
        db_table = 'monitor_status'
        app_label = 'ccdlab'
