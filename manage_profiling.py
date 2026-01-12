"""
Скрипт для профилирования view-функций через tracemalloc.
Запуск: python manage_profiling.py
Работает без запущенного сервера Django.
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
# Включаем логирование SQL запросов
settings.DEBUG_PROPAGATE_EXCEPTIONS = True

import tracemalloc
import time
from django.test import Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.db import connection, reset_queries
from news_portal.models import Post, Author, Category, PostCategory

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
    
    # Создаем 30 постов для тестирования
    posts_count = Post.objects.count()
    if posts_count < 30:
        print(f"Создание {30 - posts_count} тестовых постов...")
        for i in range(posts_count, 30):
            post = Post.objects.create(
                author=author,
                title=f'Тестовый пост {i}',
                content=f'Содержание поста {i}. ' * 50,  # Длинный контент для реалистичности
                postType='NS'
            )
            PostCategory.objects.get_or_create(post=post, category=category1)
            if i % 2 == 0:
                PostCategory.objects.get_or_create(post=post, category=category2)
    
    print(f"Тестовые данные готовы. Всего постов: {Post.objects.count()}")
    return user, author_user, author

def profile_view_function(view_name, url_name, user, pk=None):
    """Профилирование view-функции через tracemalloc"""
    # Настройка тестового клиента
    client = Client(enforce_csrf_checks=False)
    client.force_login(user)
    
    # Включаем отслеживание памяти
    tracemalloc.start()
    reset_queries()
    start_time = time.time()
    
    try:
        # Формируем URL правильно с учетом того, что news_portal.urls подключен с префиксом /news/
        if pk:
            url = reverse(url_name, args=[pk])
        else:
            url = reverse(url_name)
        
        # Если URL не начинается с /news/, добавляем префикс
        if not url.startswith('/news/'):
            url = '/news' + url
        
        response = client.get(url, follow=True)
        
        # Если получили редирект на логин, значит пользователь не залогинен
        if response.status_code == 302 and '/accounts/login' in response.url:
            print(f"ПРЕДУПРЕЖДЕНИЕ: Пользователь не авторизован, попытка повторного логина...")
            client.force_login(user)
            response = client.get(url, follow=True)
            
    except Exception as e:
        print(f"ОШИБКА при выполнении запроса: {e}")
        import traceback
        traceback.print_exc()
        tracemalloc.stop()
        return
    
    end_time = time.time()
    current, peak = tracemalloc.get_traced_memory()
    
    # Топ использования памяти (делаем до stop())
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')
    tracemalloc.stop()
    
    elapsed_time = end_time - start_time
    queries_count = len(connection.queries) if settings.DEBUG else 0
    queries_time = sum(float(q['time']) for q in connection.queries) if settings.DEBUG and connection.queries else 0
    
    print(f"\n{'='*70}")
    print(f"Профилирование: {view_name}")
    print(f"{'='*70}")
    print(f"Статус ответа: {response.status_code}")
    if response.status_code != 200:
        print(f"ВНИМАНИЕ: Неожиданный статус ответа! URL: {url}")
        print(f"Содержимое ответа (первые 500 символов): {response.content[:500]}")
    print(f"Время выполнения: {elapsed_time:.4f} сек")
    print(f"Текущее использование памяти: {current / 1024 / 1024:.2f} MB")
    print(f"Пиковое использование памяти: {peak / 1024 / 1024:.2f} MB")
    print(f"Количество SQL запросов: {queries_count}")
    print(f"Время выполнения SQL запросов: {queries_time:.4f} сек")
    print(f"DEBUG режим: {settings.DEBUG}")
    
    if settings.DEBUG and queries_count > 0:
        print(f"\nПервые 10 SQL запросов:")
        for i, query in enumerate(connection.queries[:10], 1):
            sql_preview = query['sql'][:120].replace('\n', ' ')
            print(f"  {i}. {sql_preview}... ({query['time']} сек)")
        if queries_count > 10:
            print(f"  ... и еще {queries_count - 10} запросов")
    
    # Топ использования памяти
    if top_stats:
        print(f"\nТоп 5 строк по использованию памяти:")
        for index, stat in enumerate(top_stats[:5], 1):
            print(f"  {index}. {stat}")
    
    print(f"{'='*70}\n")

if __name__ == '__main__':
    print("\n" + "="*70)
    print("ПРОФИЛИРОВАНИЕ VIEW-ФУНКЦИЙ ЧЕРЕЗ TRACEMALLOC")
    print("="*70 + "\n")
    
    try:
        user, author_user, author = setup_test_data()
        
        print("\n" + "-"*70)
        print("НАЧАЛО ПРОФИЛИРОВАНИЯ")
        print("-"*70 + "\n")
        
        # Профилирование PostsList
        print("1. PostsList (список постов)")
        profile_view_function("PostsList", "main_page", user)
        
        # Профилирование PostDetail
        print("2. PostDetail (детальная страница поста)")
        post = Post.objects.first()
        if post:
            profile_view_function("PostDetail", "post_detail", user, post.pk)
        else:
            print("ОШИБКА: Не найдено постов для тестирования")
        
        # Профилирование edit_post
        print("3. edit_post (редактирование поста)")
        if post:
            profile_view_function("edit_post", "edit_post", author_user, post.pk)
        else:
            print("ОШИБКА: Не найдено постов для тестирования")
        
        print("\n" + "="*70)
        print("ПРОФИЛИРОВАНИЕ ЗАВЕРШЕНО")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\nОШИБКА при выполнении профилирования: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

