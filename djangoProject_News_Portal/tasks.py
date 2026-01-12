from celery import shared_task
import time

@shared_task
def test_sleep():
    time.sleep(10)
    print('Sleep task')

# ну чтож, это первый тестовый коммит
# коммит 2