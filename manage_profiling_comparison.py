"""
Скрипт для сравнения производительности view-функций до и после оптимизации.
Запуск: python manage_profiling_comparison.py
Показывает улучшения в производительности после применения оптимизаций.
"""
import os
import sys
import django
from pathlib import Path

# Настройка Django окружения
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'djangoProject_News_Portal.settings')
django.setup()

# Временно включаем DEBUG для отслеживания SQL запросов
from django.conf import settings
settings.DEBUG = True
settings.DEBUG_PROPAGATE_EXCEPTIONS = True

import tracemalloc
import time
from django.test import Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.db import connection, reset_queries
from news_portal.models import Post, Author, Category, PostCategory
from news_portal.views import PostsList, PostDetail
from news_portal import views

def setup_test_data():
    """Создание тестовых данных для профилирования"""
    print("Создание тестовых данных...")
    
    user, created = User.objects.get_or_create(
        username='testuser',
        defaults={'email': 'test@test.com'}
    )
    if created or not user.check_password('testpass123'):
        user.set_password('testpass123')
        user.save()
    
    author_user, created = User.objects.get_or_create(
        username='authoruser',
        defaults={'email': 'author@test.com'}
    )
    if created or not author_user.check_password('testpass123'):
        author_user.set_password('testpass123')
        author_user.save()
    
    authors_group, _ = Group.objects.get_or_create(name='authors')
    if not author_user.groups.filter(name='authors').exists():
        author_user.groups.add(authors_group)
    
    author, _ = Author.objects.get_or_create(user=author_user)
    
    category1, _ = Category.objects.get_or_create(category='Технологии')
    category2, _ = Category.objects.get_or_create(category='Наука')
    
    # Создаем достаточно постов для реалистичного тестирования
    posts_count = Post.objects.count()
    if posts_count < 30:
        print(f"Создание {30 - posts_count} тестовых постов...")
        for i in range(posts_count, 30):
            post = Post.objects.create(
                author=author,
                title=f'Тестовый пост {i}',
                content=f'Содержание поста {i}. ' * 50,
                postType='NS'
            )
            PostCategory.objects.get_or_create(post=post, category=category1)
            if i % 2 == 0:
                PostCategory.objects.get_or_create(post=post, category=category2)
    
    print(f"Тестовые данные готовы. Всего постов: {Post.objects.count()}\n")
    return user, author_user, author

# Глобальные переменные для хранения оригинальных методов
_original_methods = {}

def profile_view_unoptimized(view_name, url_name, user, pk=None, queryset_func=None):
    """Профилирование view-функции БЕЗ оптимизаций"""
    global _original_methods
    client = Client(enforce_csrf_checks=False)
    client.force_login(user)
    
    try:
        # Для PostsList
        if view_name == "PostsList":
            # Сохраняем оригинальные методы
            if 'PostsList_get_queryset' not in _original_methods:
                _original_methods['PostsList_get_queryset'] = PostsList.get_queryset
                _original_methods['PostsList_form'] = PostsList.form
            # Неоптимизированный queryset без select_related и prefetch_related
            PostsList.get_queryset = lambda self: Post.objects.all().order_by('-create_time')
            # Также убираем оптимизацию из form() метода
            def form_unoptimized(self):
                from news_portal.models import UserSubcribes
                from news_portal.forms import SubsribeForm
                # БЕЗ select_related
                user_subscriptions = UserSubcribes.objects.filter(subcribe=self.request.user)
                subscribed_categories = [us.category for us in user_subscriptions]
                form = SubsribeForm(initial={'category': subscribed_categories})
                if self.request.path == '/news/edit_subscribe/':
                    form.fields['category'].disabled = False
                return form
            PostsList.form = form_unoptimized
        # Для PostDetail
        elif view_name == "PostDetail":
            # Сохраняем оригинальные значения
            if 'PostDetail_queryset' not in _original_methods:
                _original_methods['PostDetail_queryset'] = PostDetail.queryset
                _original_methods['PostDetail_get_context_data'] = PostDetail.get_context_data
            # Неоптимизированный queryset
            PostDetail.queryset = Post.objects.all()
            # Убираем оптимизацию из get_context_data
            def get_context_data_unoptimized(self, **kwargs):
                context = super(PostDetail, self).get_context_data(**kwargs)
                from news_portal.models import Comment
                from news_portal.forms import PostForm
                # БЕЗ select_related
                context['comm'] = Comment.objects.filter(post_id=self.kwargs['pk'])
                post_categories = list(self.object.category.all())
                form = PostForm(initial={
                    'title': self.object.title,
                    'content': self.object.content,
                    'create_time': self.object.create_time,
                    'author': self.object.author,
                    'postType': self.object.postType,
                    'category': post_categories
                })
                form.fields['author'].disabled = True
                form.fields['title'].disabled = True
                form.fields['content'].disabled = True
                form.fields['postType'].disabled = True
                form.fields['category'].disabled = True
                context['form'] = form
                context['id'] = self.object.pk
                context['is_author'] = self.request.user.groups.filter(name='authors').exists()
                return context
            PostDetail.get_context_data = get_context_data_unoptimized
    
    except Exception as e:
        print(f"ОШИБКА при замене queryset: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    tracemalloc.start()
    reset_queries()
    start_time = time.time()
    
    try:
        if pk:
            url = reverse(url_name, args=[pk])
        else:
            url = reverse(url_name)
        
        if not url.startswith('/news/'):
            url = '/news' + url
        
        response = client.get(url, follow=True)
        
        if response.status_code == 302 and '/accounts/login' in response.url:
            client.force_login(user)
            response = client.get(url, follow=True)
            
    except Exception as e:
        print(f"ОШИБКА при выполнении запроса: {e}")
        if original_get_queryset:
            PostsList.get_queryset = original_get_queryset
        if original_queryset is not None:
            PostDetail.queryset = original_queryset
        tracemalloc.stop()
        return None
    
    end_time = time.time()
    current, peak = tracemalloc.get_traced_memory()
    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()
    
    # Восстанавливаем оригинальные методы после теста
    if 'PostsList_get_queryset' in _original_methods:
        PostsList.get_queryset = _original_methods['PostsList_get_queryset']
        PostsList.form = _original_methods['PostsList_form']
    if 'PostDetail_queryset' in _original_methods:
        PostDetail.queryset = _original_methods['PostDetail_queryset']
        PostDetail.get_context_data = _original_methods['PostDetail_get_context_data']
    
    elapsed_time = end_time - start_time
    queries_count = len(connection.queries) if settings.DEBUG else 0
    queries_time = sum(float(q['time']) for q in connection.queries) if settings.DEBUG and connection.queries else 0
    
    return {
        'status': response.status_code,
        'elapsed_time': elapsed_time,
        'current_memory': current,
        'peak_memory': peak,
        'queries_count': queries_count,
        'queries_time': queries_time,
        'snapshot': snapshot
    }

def profile_view_optimized(view_name, url_name, user, pk=None):
    """Профилирование view-функции С оптимизациями"""
    client = Client(enforce_csrf_checks=False)
    client.force_login(user)
    
    tracemalloc.start()
    reset_queries()
    start_time = time.time()
    
    try:
        if pk:
            url = reverse(url_name, args=[pk])
        else:
            url = reverse(url_name)
        
        if not url.startswith('/news/'):
            url = '/news' + url
        
        response = client.get(url, follow=True)
        
        if response.status_code == 302 and '/accounts/login' in response.url:
            client.force_login(user)
            response = client.get(url, follow=True)
            
    except Exception as e:
        print(f"ОШИБКА при выполнении запроса: {e}")
        tracemalloc.stop()
        return None
    
    end_time = time.time()
    current, peak = tracemalloc.get_traced_memory()
    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()
    
    elapsed_time = end_time - start_time
    queries_count = len(connection.queries) if settings.DEBUG else 0
    queries_time = sum(float(q['time']) for q in connection.queries) if settings.DEBUG and connection.queries else 0
    
    return {
        'status': response.status_code,
        'elapsed_time': elapsed_time,
        'current_memory': current,
        'peak_memory': peak,
        'queries_count': queries_count,
        'queries_time': queries_time,
        'snapshot': snapshot
    }

def profile_edit_post_comparison(user, post_pk):
    """Сравнение edit_post до и после оптимизации"""
    from news_portal import views
    client = Client(enforce_csrf_checks=False)
    client.force_login(user)
    url = f'/news/{post_pk}/edit/'
    
    # Неоптимизированная версия - сохраняем оригинальную функцию
    original_edit_post = views.edit_post
    
    # Создаем неоптимизированную версию edit_post
    def edit_post_unoptimized(request, pk):
        try:
            # БЕЗ select_related и prefetch_related
            post = Post.objects.get(pk=pk)
            if post.author.user == request.user:
                # БЕЗ оптимизаций - каждый доступ к связанным объектам делает отдельный запрос
                post_categories = list(post.category.all())  # Дополнительный запрос
                all_categories = Category.objects.all()  # Отдельный запрос
                from news_portal.forms import PostForm
                form = PostForm(initial={
                    'create_time': post.create_time,
                    'author': post.author,
                    'postType': post.postType,
                    'title': post.title,
                    'content': post.content,
                    'category': post_categories
                })
                form.fields['postType'].disabled = True
                form.fields['author'].disabled = True
                form.fields['category'].queryset = all_categories
                form.fields['category'].disabled = True
                form.fields['category'].required = False
                from django.shortcuts import render
                return render(request, 'flatpages/edit.html', {'form': form, 'button': 'Сохранить изменения'})
        except Exception as e:
            from django.shortcuts import render
            return render(request, '403.html', {'not_your_publication': True})
        return None
    
    # Неоптимизированная версия
    tracemalloc.start()
    reset_queries()
    start_time = time.time()
    
    try:
        views.edit_post = edit_post_unoptimized
        response = client.get(url, follow=True)
    except Exception as e:
        views.edit_post = original_edit_post
        tracemalloc.stop()
        return None, None
    
    end_time = time.time()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    unoptimized = {
        'status': response.status_code,
        'elapsed_time': end_time - start_time,
        'current_memory': current,
        'peak_memory': peak,
        'queries_count': len(connection.queries) if settings.DEBUG else 0,
        'queries_time': sum(float(q['time']) for q in connection.queries) if settings.DEBUG and connection.queries else 0,
    }
    
    # Восстанавливаем оригинальную функцию
    views.edit_post = original_edit_post
    
    # Оптимизированная версия
    tracemalloc.start()
    reset_queries()
    start_time = time.time()
    
    try:
        response = client.get(url, follow=True)
    except Exception as e:
        tracemalloc.stop()
        return unoptimized, None
    
    end_time = time.time()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    optimized = {
        'status': response.status_code,
        'elapsed_time': end_time - start_time,
        'current_memory': current,
        'peak_memory': peak,
        'queries_count': len(connection.queries) if settings.DEBUG else 0,
        'queries_time': sum(float(q['time']) for q in connection.queries) if settings.DEBUG and connection.queries else 0,
    }
    
    return unoptimized, optimized

def print_comparison(view_name, unopt, opt):
    """Вывод сравнения результатов"""
    if not unopt or not opt:
        print(f"\n⚠ Не удалось получить данные для {view_name}\n")
        return
    
    print(f"\n{'='*80}")
    print(f"СРАВНЕНИЕ: {view_name}")
    print(f"{'='*80}")
    
    # Время выполнения
    time_improvement = ((unopt['elapsed_time'] - opt['elapsed_time']) / unopt['elapsed_time']) * 100
    print(f"\n⏱ ВРЕМЯ ВЫПОЛНЕНИЯ:")
    print(f"  Без оптимизации:  {unopt['elapsed_time']:.4f} сек")
    print(f"  С оптимизацией:   {opt['elapsed_time']:.4f} сек")
    print(f"  Улучшение:        {time_improvement:+.1f}% ({'↑' if time_improvement > 0 else '↓'})")
    
    # SQL запросы
    queries_improvement = ((unopt['queries_count'] - opt['queries_count']) / unopt['queries_count'] * 100) if unopt['queries_count'] > 0 else 0
    print(f"\n🗄 SQL ЗАПРОСЫ:")
    print(f"  Без оптимизации:  {unopt['queries_count']} запросов ({unopt['queries_time']:.4f} сек)")
    print(f"  С оптимизацией:   {opt['queries_count']} запросов ({opt['queries_time']:.4f} сек)")
    print(f"  Улучшение:        {queries_improvement:+.1f}% запросов меньше ({'↑' if queries_improvement > 0 else '↓'})")
    
    # Память (пиковая)
    memory_improvement = ((unopt['peak_memory'] - opt['peak_memory']) / unopt['peak_memory'] * 100) if unopt['peak_memory'] > 0 else 0
    print(f"\nПАМЯТЬ (пиковое использование):")
    print(f"  Без оптимизации:  {unopt['peak_memory'] / 1024 / 1024:.2f} MB")
    print(f"  С оптимизацией:   {opt['peak_memory'] / 1024 / 1024:.2f} MB")
    print(f"  Улучшение:        {memory_improvement:+.1f}% ({'↑' if memory_improvement > 0 else '↓'})")
    
    # Общая оценка
    print(f"\nИТОГОВАЯ ОЦЕНКА:")
    total_improvement = (time_improvement + queries_improvement + memory_improvement) / 3
    if total_improvement > 30:
        print(f"  Отличное улучшение: {total_improvement:.1f}%")
    elif total_improvement > 15:
        print(f"  Хорошее улучшение: {total_improvement:.1f}%")
    elif total_improvement > 0:
        print(f"  Небольшое улучшение: {total_improvement:.1f}%")
    else:
        print(f"  Требуется дополнительная оптимизация")
    
    print(f"{'='*80}\n")

if __name__ == '__main__':
    print("\n" + "="*80)
    print("СРАВНЕНИЕ ПРОИЗВОДИТЕЛЬНОСТИ ДО И ПОСЛЕ ОПТИМИЗАЦИИ")
    print("="*80 + "\n")
    
    try:
        user, author_user, author = setup_test_data()
        
        print("\n" + "-"*80)
        print("НАЧАЛО СРАВНЕНИЯ")
        print("-"*80 + "\n")
        
        # 1. Сравнение PostsList
        print("1. PostsList (список постов)")
        print("   Запуск без оптимизаций...")
        unopt_posts = profile_view_unoptimized("PostsList", "main_page", user)
        print("   Запуск с оптимизациями...")
        opt_posts = profile_view_optimized("PostsList", "main_page", user)
        print_comparison("PostsList", unopt_posts, opt_posts)
        
        # 2. Сравнение PostDetail
        print("2. PostDetail (детальная страница поста)")
        post = Post.objects.first()
        if post:
            print("   Запуск без оптимизаций...")
            unopt_detail = profile_view_unoptimized("PostDetail", "post_detail", user, post.pk)
            print("   Запуск с оптимизациями...")
            opt_detail = profile_view_optimized("PostDetail", "post_detail", user, post.pk)
            print_comparison("PostDetail", unopt_detail, opt_detail)
        else:
            print("⚠ Посты не найдены, пропускаем тест")
        
        # 3. Сравнение edit_post
        if post:
            print("3. edit_post (редактирование поста)")
            print("   Запуск без оптимизаций...")
            print("   Запуск с оптимизациями...")
            unopt_edit, opt_edit = profile_edit_post_comparison(author_user, post.pk)
            print_comparison("edit_post", unopt_edit, opt_edit)
        else:
            print("⚠ Посты не найдены, пропускаем тест")
        
        print("\n" + "="*80)
        print("СРАВНЕНИЕ ЗАВЕРШЕНО")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\nОШИБКА при выполнении сравнения: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

