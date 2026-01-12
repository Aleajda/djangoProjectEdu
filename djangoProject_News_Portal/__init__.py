default_app_config = 'news_portal.apps.NewsPortalConfig'
from .celery import app as celery_app

__all__ = ('celery_app',)