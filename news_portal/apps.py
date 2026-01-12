from django.apps import AppConfig
from datetime import datetime

# здесь формируеся конфигурация приложения. Например, под обработчики событий
class NewsPortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'news_portal'
    verbose_name = 'djangoProject_News_Portal'
    def ready(self): # это переопределенный метод
        import news_portal.signals
        from .scheduler import scheduler
        from .tasks import hello_world
        print('begin')
        begin=datetime.now()

