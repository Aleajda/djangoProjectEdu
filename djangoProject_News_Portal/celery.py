import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE',
                      'djangoProject_News_Portal.settings')

app = Celery('djangoProject_News_Portal')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.conf.timezone = 'Europe/Moscow' # установка часового пояса
app.autodiscover_tasks()
app.conf.broker_connection_retry_on_startup = True

app.conf.beat_schedule = {'send_weekly_messages':
                          {'task':
                           'news_portal.tasks.weekly_mailing',
                           'schedule': crontab(day_of_week='monday', hour='8', minute='00')}}

# app.conf.beat_schedule = {'hello_world_every_5_sec':
#                               {'task': 'news_portal.tasks.hello_world',
#                               'schedule': 5,
#                               'args':()}}
