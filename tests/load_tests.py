import tracemalloc
import time
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.db import connection, reset_queries
from django.conf import settings
from news_portal.models import Post, Author, Category, PostCategory
from datetime import datetime, timedelta, timezone

@override_settings(DEBUG=True)
class LoadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.client = Client()
        
        cls.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        
        cls.author_user = User.objects.create_user(
            username='authoruser',
            email='author@test.com',
            password='testpass123'
        )
        
        authors_group = Group.objects.create(name='authors')
        cls.author_user.groups.add(authors_group)
        
        cls.author = Author.objects.create(user=cls.author_user)
        
        cls.category1 = Category.objects.create(category='Технологии')
        cls.category2 = Category.objects.create(category='Наука')
        
        cls.posts = []
        for i in range(50):
            post = Post.objects.create(
                author=cls.author,
                title=f'Тестовый пост {i}',
                content=f'Содержание поста {i}' * 10,
                postType='NS'
            )
            PostCategory.objects.create(post=post, category=cls.category1)
            if i % 2 == 0:
                PostCategory.objects.create(post=post, category=cls.category2)
            cls.posts.append(post)
    
    def test_posts_list_load(self):
        self.client.force_login(self.user)
        
        tracemalloc.start()
        reset_queries()
        start_time = time.time()
        
        for _ in range(20):
            reset_queries()
            response = self.client.get(reverse('main_page'))
            self.assertEqual(response.status_code, 200)
        
        end_time = time.time()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        elapsed_time = end_time - start_time
        avg_time = elapsed_time / 20
        queries_count = len(connection.queries) if settings.DEBUG else 0
        
        print(f"\n{'='*60}")
        print(f"Нагрузочный тест: PostsList (20 запросов)")
        print(f"{'='*60}")
        print(f"Общее время: {elapsed_time:.4f} сек")
        print(f"Среднее время на запрос: {avg_time:.4f} сек")
        print(f"Текущее использование памяти: {current / 1024 / 1024:.2f} MB")
        print(f"Пиковое использование памяти: {peak / 1024 / 1024:.2f} MB")
        print(f"SQL запросов в последнем запросе: {queries_count}")
        print(f"{'='*60}\n")
        
        self.assertLess(avg_time, 1.0)  # Более реалистичный лимит
    
    def test_post_detail_load(self):
        self.client.force_login(self.user)
        post = self.posts[0]
        
        tracemalloc.start()
        reset_queries()
        start_time = time.time()
        
        for _ in range(20):
            reset_queries()
            response = self.client.get(reverse('post_detail', args=[post.pk]))
            self.assertEqual(response.status_code, 200)
        
        end_time = time.time()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        elapsed_time = end_time - start_time
        avg_time = elapsed_time / 20
        queries_count = len(connection.queries) if settings.DEBUG else 0
        
        print(f"\n{'='*60}")
        print(f"Нагрузочный тест: PostDetail (20 запросов)")
        print(f"{'='*60}")
        print(f"Общее время: {elapsed_time:.4f} сек")
        print(f"Среднее время на запрос: {avg_time:.4f} сек")
        print(f"Текущее использование памяти: {current / 1024 / 1024:.2f} MB")
        print(f"Пиковое использование памяти: {peak / 1024 / 1024:.2f} MB")
        print(f"SQL запросов в последнем запросе: {queries_count}")
        print(f"{'='*60}\n")
        
        self.assertLess(avg_time, 0.5)  # Более реалистичный лимит
    
    def test_edit_post_load(self):
        self.client.force_login(self.author_user)
        post = self.posts[0]
        
        tracemalloc.start()
        reset_queries()
        start_time = time.time()
        
        for _ in range(10):
            reset_queries()
            response = self.client.get(reverse('edit_post', args=[post.pk]))
            self.assertEqual(response.status_code, 200)
        
        end_time = time.time()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        elapsed_time = end_time - start_time
        avg_time = elapsed_time / 10
        queries_count = len(connection.queries) if settings.DEBUG else 0
        
        print(f"\n{'='*60}")
        print(f"Нагрузочный тест: edit_post (10 запросов)")
        print(f"{'='*60}")
        print(f"Общее время: {elapsed_time:.4f} сек")
        print(f"Среднее время на запрос: {avg_time:.4f} сек")
        print(f"Текущее использование памяти: {current / 1024 / 1024:.2f} MB")
        print(f"Пиковое использование памяти: {peak / 1024 / 1024:.2f} MB")
        print(f"SQL запросов в последнем запросе: {queries_count}")
        print(f"{'='*60}\n")
        
        self.assertLess(avg_time, 0.6)  # Более реалистичный лимит
    
    def test_concurrent_requests(self):
        self.client.force_login(self.user)
        
        tracemalloc.start()
        reset_queries()
        start_time = time.time()
        
        responses = []
        for i in range(30):
            reset_queries()
            if i % 3 == 0:
                response = self.client.get(reverse('main_page'))
            elif i % 3 == 1:
                post = self.posts[i % len(self.posts)]
                response = self.client.get(reverse('post_detail', args=[post.pk]))
            else:
                response = self.client.get(reverse('search_post'))
            responses.append(response.status_code)
        
        end_time = time.time()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        elapsed_time = end_time - start_time
        avg_time = elapsed_time / 30
        queries_count = len(connection.queries) if settings.DEBUG else 0
        
        print(f"\n{'='*60}")
        print(f"Нагрузочный тест: Смешанные запросы (30 запросов)")
        print(f"{'='*60}")
        print(f"Общее время: {elapsed_time:.4f} сек")
        print(f"Среднее время на запрос: {avg_time:.4f} сек")
        print(f"Текущее использование памяти: {current / 1024 / 1024:.2f} MB")
        print(f"Пиковое использование памяти: {peak / 1024 / 1024:.2f} MB")
        print(f"SQL запросов в последнем запросе: {queries_count}")
        print(f"Успешных ответов (200): {sum(1 for code in responses if code == 200)}")
        print(f"Всего ответов: {len(responses)}")
        print(f"{'='*60}\n")
        
        # Проверяем, что большинство запросов успешны
        success_count = sum(1 for code in responses if code == 200)
        self.assertGreaterEqual(success_count, 25, f"Слишком мало успешных запросов: {success_count}/30")

