#___________ НАЧАЛО ИМПОРТА КОМПОНЕНТОВ ______________
from django.conf import settings
import time
from datetime import datetime
import datetime as dt

# для работы с авторизайций пользователей #
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin # специальный миксин для представлений,
from django.contrib.auth.models import User
# работающих тольбко после авторизации. Альтернатива комбинации login_required (method_decorator)

# для работы с почтовой рассылкой
from django.core.mail import EmailMultiAlternatives, mail_managers, send_mail # почтовая рассылка
# c применением шаблона HTML (EmailMultiAlternatives) и функция с обработкой сигналов
from django.template.loader import render_to_string # рендера HTML в строку
from django.db.models.signals import post_init
from django.dispatch import receiver
import django.dispatch as dj_ds

# модели и представления
from django.views import View
from django.views.generic import ListView, DetailView
from .models import Post, Author, Comment, Category, Mail, PostCategory, UserSubcribes

# фильтры и формы
from .filters import PostFilter
from .forms import PostForm, PostCreateForm, SubsribeForm

# загрузка страниц и исключения
from django.shortcuts import reverse, render, redirect
from django.core.exceptions import ObjectDoesNotExist

# импорты для удаления тестовых пользователей (для отработки при создании проекта)
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.models import EmailAddress


from pprint import pprint
from django.db import models
from .tasks import test_sleep, hello_world, test_comments
from django.http import HttpResponse, HttpResponseRedirect

# ------- КЭШ -------------
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from redis import Redis
import json
from django.core.serializers.json import DjangoJSONEncoder

#-------- ЛОГГИРОВАНИЕ --------
import logging
# logger = logging.getLogger(__name__)
logger = logging.getLogger('django.server')
#___________ КОНЕЦ ИМПОРТА КОМПОНЕНТОВ ______________#


class PostsList(LoginRequiredMixin, ListView): #класс для показа общего списка всех публикаций
    model = Post
    template_name = 'flatpages/news.html'
    context_object_name = 'post'
    paginate_by = 10
    edit_subscribe=None

    def get_queryset(self):
        return Post.objects.select_related('author', 'author__user').prefetch_related('category').order_by('-create_time')

    def form(self):
        user_subscriptions = UserSubcribes.objects.filter(subcribe=self.request.user).select_related('category')
        subscribed_categories = [us.category for us in user_subscriptions]
        form = SubsribeForm(initial={'category': subscribed_categories})
        if self.request.path == '/news/edit_subscribe/':
            form.fields['category'].disabled = False
        return form

    def get_context_data(self,**kwargs):
        context=super().get_context_data(**kwargs)
        context['form'] = self.form
        context['is_not_author']= not self.request.user.groups.filter(name='authors').exists()

        if self.request.path==reverse('edit_subscribe'):
            self.edit_subscribe=True
            context['edit_subscribe'] = self.edit_subscribe
        return context

    def post(self, request, *args, **kwargs):
        subscriptions =[] # список, которая принимает от формы категории,
    # на которые пользователь хочет подписаться
        del_subscriptions=[] # переменная, которая принимает список категорий
                        # на удаление если с них пользователь убирает галочку
        user=request.user
        if request.method=='POST':
            if request.POST ['subscribe']=='Редактировать подписку':
                # здесь требуется код, который бы делал доступной форму для редактирования
                # подписок пользователя
                return redirect('edit_subscribe')
            else:
                form = SubsribeForm(request.POST)
                form.fields['category'].disabled = False
                if form.is_valid():
                    selected_categories = set(form.cleaned_data['category'])
                    existing_subscriptions = UserSubcribes.objects.filter(subcribe=user).select_related('category')
                    existing_categories = {us.category for us in existing_subscriptions}
                    
                    subscriptions = [cat for cat in selected_categories if cat not in existing_categories]
                    del_subscriptions = [cat for cat in existing_categories if cat not in selected_categories]
                else:
                    existing_subscriptions = UserSubcribes.objects.filter(subcribe=user).select_related('category')
                    del_subscriptions = [us.category for us in existing_subscriptions]

                if del_subscriptions:
                    UserSubcribes.objects.filter(subcribe=user, category__in=del_subscriptions).delete()
                if subscriptions:
                    UserSubcribes.objects.bulk_create([
                        UserSubcribes(subcribe=user, category=category) for category in subscriptions
                    ])
                return redirect('main_page')

class PostDetail(LoginRequiredMixin,DetailView):
    model = Post
    template_name = 'flatpages/post.html'
    context_object_name = 'post'
    queryset = Post.objects.select_related('author', 'author__user').prefetch_related('category')

    def get_context_data(self, **kwargs):
        context=super().get_context_data(**kwargs)
        # Категории уже загружены через prefetch_related, поэтому используем их напрямую
        context['comm'] = Comment.objects.filter(post_id=self.kwargs['pk']).select_related('user')
        
        # Используем уже загруженные категории (prefetch_related)
        post_categories = list(self.object.category.all())
        form=PostForm(initial={'title': self.object.title,
                               'content': self.object.content,
                               'create_time': self.object.create_time,
                               'author': self.object.author,
                               'postType': self.object.postType,
                               'category': post_categories})
        form.fields['author'].disabled = True
        form.fields['title'].disabled = True
        form.fields['content'].disabled = True
        form.fields['postType'].disabled = True
        form.fields['category'].disabled = True
        context['form'] = form
        context['id']=self.object.pk
        # Оптимизация проверки группы авторов
        context['is_author']=self.request.user.groups.filter(name='authors').exists()
        return context

    def get_object(self, queryset=None):
        post=cache.get(f'post-{self.kwargs['pk']}', None)
        if post is None:
            if queryset is None:
                queryset = self.get_queryset()
            post = queryset.get(pk=self.kwargs['pk'])
            cache.set(f'post-{self.kwargs['pk']}', post, 300)
        return post

class PostFilterView(LoginRequiredMixin, ListView): # класс для отображения фильтра поста на отдельной HTML странице 'search.html'
    model = Post
    template_name = 'flatpages/search.html'
    context_object_name = 'post'
    paginate_by =3

    def get_queryset(self):
        queryset=super().get_queryset()
        self.filter = PostFilter(self.request.GET,queryset)
        return self.filter.qs

    def get_context_data(self,  **kwargs): #добавление в контекст фильтра
        context=super().get_context_data(**kwargs)
        context['filter']=self.filter
        return context

@login_required
@permission_required('news_portal.add_post', raise_exception=True)
def create_post(request): # функция для создания и добавления новой публикации
    delta=datetime.now(dt.timezone.utc)-dt.timedelta(days=1)
    if Post.objects.filter(create_time__gte=delta, author__user=request.user).count()>3:
        return render(request,'posts_limit.html')

    form=PostCreateForm()
    form.fields['author'].queryset=Author.objects.filter(user=request.user)
    # принимающая значение True, если пользователь относится к группе авторов

    if request.method=='POST':
        form=PostCreateForm(request.POST)
        if form.is_valid():
            form.save()
            # post=form.save()
            # post_id, user_id = post.pk, request.user.id
            return render(request, 'flatpages/messages.html', {'state':'Новая публикация добавлена успешно!'})
    return render(request, 'flatpages/edit.html', {'form':form, 'button':'Опубликовать'})

@login_required
@permission_required('news_portal.change_post', raise_exception=True)
def edit_post(request, pk):
    try:
        # Оптимизация: используем select_related и prefetch_related для уменьшения запросов
        post = Post.objects.select_related('author', 'author__user').prefetch_related('category').get(pk=pk)
        if post.author.user==request.user:
            # Оптимизация проверки группы авторов (одна проверка для всех случаев)
            is_author= request.user.groups.filter(name='authors').exists()
            
            # Категории уже загружены через prefetch_related
            post_categories = list(post.category.all())
            # Загружаем все категории один раз
            all_categories = Category.objects.all()
            
            form=PostForm(initial={'create_time':post.create_time,
                                   'author':post.author,
                                   'postType':post.postType,
                                   'title': post.title,
                                   'content': post.content,
                                   'category': post_categories})
            form.fields['postType'].disabled = True
            form.fields['author'].disabled = True
            form.fields['category'].queryset = all_categories
            form.fields['category'].disabled = True
            form.fields['category'].required = False
            
            if request.method=='POST':
                form=PostForm(request.POST, post)
                form.fields['postType'].required = False
                form.fields['author'].required = False
                form.fields['create_time'].required = False
                form.fields['category'].required = False
                try:
                    state = None
                    if form.is_valid():
                        Post.objects.filter(pk=pk).update(**{'author':post.author,
                                                             'postType':post.postType,
                                                             'create_time':post.create_time,
                                                             'title':form.cleaned_data['title'],
                                                             'content':form.cleaned_data['content']})
                        cache.delete(f'post-{pk}')
                        state='Изменения успешно сохранены.'
                except TypeError:
                    state = 'Возникла ошибка! Возможно причина в превышении лимита названия поста, попавшего в БД не через форму'
                return render(request, 'flatpages/messages.html', {'state':state})
            return render(request, 'flatpages/edit.html', {'form':form, 'button':'Сохранить изменения', 'is_author':is_author})
        return render(request,'403.html',{'not_your_publication':True})
    except Exception as e:
        logger.error(f'main_ERROR = {e}')

@login_required
@permission_required('news_portal.delete_post', raise_exception=True)
def delete_post(request, pk):
    post = Post.objects.get(pk=pk)
    if post.author.user == request.user:
        if request.method=='POST':
            post.delete()
            return render(request, 'flatpages/messages.html', {'state': 'Пост успешно удален'})
        return render(request, 'flatpages/del_post.html',{'post':post})
    return render(request, '403.html', {'not_your_publication': True})

class MailView(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'flatpages/mail/mail.html', {})

    def post(self, request, *args, **kwargs):
        user_2=User.objects.get(pk=62)
        post=Post.objects.get(pk=request.POST.get('post'))
        message=(f'Здравствуй, { request.user.username }!\n'
        f'Рады сообщить, о выходе новой публикации с названием "{ post.title }".\n'
        f'Новая публикация в твоём любимом разделе!\n'
        f'Краткая выдержка:\n'
        f'{ post.content[:151] }...') # шаблон сообщения, сохраняемый в БД модели Mail после отправки
        mail = Mail(subscriber=request.user,
                    message=message,
                    date=request.POST.get('date'))
        html_message = render_to_string('flatpages/mail/send_html_mail.html', {'post':post, 'username':request.user.username})
        email_message = EmailMultiAlternatives(subject=f'{post.title}',body=message,
                                               to=['said-bah@yandex.ru','rfa-kstu@yandex.ru','movchanahsmk@gmail.com']
                                               )
        email_message.attach_alternative(html_message,'text/html')
        email_message.send()
        mail.save()
        return redirect('news_mail')


# представление для тестирования разных задач
# @cache_page(4)
def test(request):

    try:
        a = 1/0
        return render(request, 'test.html', {'posts':'posts'})
    except ZeroDivisionError as e:
        logger.error('Real error', exc_info=True)
        return render(request, 'test.html')



def ts(request):
    pst=Post.objects.get(pk=1)
    logger.info('Кутагыpst')

    return render(request,
                  '403.html',
                  {'aa': pst.title})


# -! Неиспользуемые классы ниже
class CommListView(ListView):  # класс для отобрпажения
    model = Comment
    template_name = 'flatpages/comm.html'
    context_object_name = 'cmts'