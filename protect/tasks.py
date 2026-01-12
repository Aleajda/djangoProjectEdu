from celery import shared_task
import time
@shared_task
def protect_task():
    time.sleep(5)
    print('protect_task')