# ИМПОРТЫ ИЗ КОРОБКИ ДЛЯ APSCHEDULER
import logging

from django.conf import settings

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.core.management.base import BaseCommand
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution

logger = logging.getLogger(__name__)
#_________________________________
#--------- ДОП ИМПОРТЫ ---------------
from news_portal.models import Post, Category
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
import datetime
#____ КОНЕЦ ИМПОРТА _____________

# наша задача по выводу текста на экран
def my_job():
    #  Your job processing logic here...
    delta=datetime.datetime.now (datetime.timezone.utc)-datetime.timedelta(days=7)
    posts=Post.objects.filter(create_time__gte=delta)
    post_pk=Post.objects.filter(create_time__gte=delta).values_list('pk',flat=True)
    categories=set(Category.objects.filter(post__in=posts))
    user_pk=set(User.objects.filter(category__in=categories).values_list('pk',flat=True))

    for user in User.objects.filter(pk__in=user_pk):
        post_list = []  # список постов для еженедльной рассылки полдписчикам
        current_post_list = []  # список для отслеживания добавляемых постов в post_list во избежание
        # дублирования во время рассылки одному и тому же подписчику
        for post in Post.objects.filter(pk__in=post_pk, category__in=categories, category__usersubcribes__subcribe=user):
            if post not in current_post_list:
                current_post_list.append(post)
                post_list.append(post)

        html=render_to_string('flatpages/mail/scheduler_message.html',
                              {'username':user.username,'post':post_list})
        msg=EmailMultiAlternatives(subject='Список публикаций за неделю подписчикам ',
                                   body='',
                                   from_email=settings.DEFAULT_FROM_EMAIL,
                                   to=[f'{user.email}'])
        msg.attach_alternative(html,'text/html')
        msg.send()



# функция, которая будет удалять неактуальные задачи
def delete_old_job_executions(max_age=604_800):
    """This job deletes all apscheduler job executions older than `max_age` from the database."""
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


class Command(BaseCommand):
    help = "Runs apscheduler."

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        # добавляем работу нашему задачнику
        scheduler.add_job(
            my_job,
            # day_of_week="sun" - это значит каждое воскресенье будет выполняться расписание
            trigger=CronTrigger(day_of_week="sun", hour="9", minute="00"),
            # То же, что и интервал, но задача тригера таким образом более понятна django
            id="my_job",  # уникальный айди
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added job 'my_job'.")

        scheduler.add_job(
            delete_old_job_executions,
            trigger=CronTrigger(
                day_of_week="wed", hour="9", minute="10"
            ),
            # Каждую неделю будут удаляться старые задачи, которые либо не удалось выполнить, либо уже выполнять не надо.
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
        )
        logger.info(
            "Added weekly job: 'delete_old_job_executions'."
        )

        try:
            logger.info("Starting scheduler...")
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Stopping scheduler...")
            scheduler.shutdown()
            logger.info("Scheduler shut down successfully!")