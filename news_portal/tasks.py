from celery import shared_task
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from .models import Post, Category, PostCategory, User, UserSubcribes, Mail, Comment
import time
from django.http import HttpResponse
from datetime import datetime
from datetime import timezone
from datetime import timedelta

import logging
logger = logging.getLogger(__name__)

@shared_task
def test_sleep():
    time.sleep(10)
    HttpResponse('Sleep task')


@shared_task
def hello_world():
    print("Hello world async")


@shared_task
def test_comments(post_id, user_id):
    time.sleep(10)
    post_date = Post.objects.get(id=post_id).create_time
    Comment.objects.create(user_id=user_id, comment_text=f'This is a comment created later than'
                                                         f'{datetime.now(tz=timezone.utc)-post_date}',
                           post_id=post_id)


# Функция отправки уведомлений о выходе новой статьи подписчикам категорий
@shared_task
def send_notify_to_subscribers(instance_id):

    # Извлечение данных пользователей, подписанных на категории, к которым относится созданная публикация
    post = (Post.objects.filter(pk=instance_id).prefetch_related('category').values(
        'title', 'content', 'category__subscribers__id',
        'category__subscribers__email', 'category__subscribers__username'))

    # Формировние списка подисчиков через set во избежание дублирования
    subcriber_list = set ([(item['category__subscribers__id'],
                            item['category__subscribers__email'],
                            item['category__subscribers__username'])
                           for item in post])
    logger.info(f'Subscribers: {subcriber_list}')
    logger.info(f'post: {post}')
    title, content = post[0]['title'], post[0]['content']
    logger.info(f'title: {title}; content: {content}')

    # Рассылка уведомления о выходе новой статьи подписчикам
    for user_id, email, username in subcriber_list:
        html = render_to_string('flatpages/mail/send_html_mail.html',
                                {'post_title': title, 'username': username,
                                 'post_content': content, 'post_pk': instance_id})
        subject = f'Выход статьи с названием "{title}"'
        msg = EmailMultiAlternatives(subject=subject,
                                     body=html,
                                     from_email=settings.DEFAULT_FROM_EMAIL,
                                     to=[f'{email}'])
        msg.attach_alternative(html, 'text/html')
        msg.send()
        Mail.objects.create(message=html, recepients_id=user_id, subject=subject)


# Еженедельная рассылка уведомлений о последних публикациях за неделю
@shared_task
def weekly_mailing():
    delta=datetime.now (timezone.utc)-timedelta(days=7)
    posts=(Post.objects.filter(create_time__gte=delta).prefetch_related('category').
           values('pk', 'title', 'category__subscribers__email',
                  'category__subscribers__username'))
    for i in posts:
        logger.info(i)

    kwg=dict()
    for post in posts:
        email, username = post['category__subscribers__email'], post['category__subscribers__username']

        # Ключ словаря представляет собой формат 'email/username'
        key = f'{email}/{username}'
        if key not in kwg:
            kwg[key]=set()
        kwg[key].add((post['pk'], post['title']))

    for k, v in kwg.items():
        logger.info(f'kwg[{k}]={v}')

        # Присвоение данных пользователя из названия ключа словаря
        email, username = k.split('/')
        logger.info(f'{email}/{username}')

        html=render_to_string('flatpages/mail/scheduler_message.html',
                              {'username':username,'post':v})
        msg=EmailMultiAlternatives(subject='Список публикаций за неделю для подписчиков ',
                                   body='',
                                   from_email=settings.DEFAULT_FROM_EMAIL,
                                   to=[f'{email}'])
        msg.attach_alternative(html,'text/html')
        msg.send()
    return 0
