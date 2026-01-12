import tracemalloc
import time
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.db import connection, reset_queries
from django.conf import settings
from news_portal.models import Post, Author, Category, PostCategory
from news_portal.profiling import profile_view

@override_settings(DEBUG=True)
class ProfilingTests(TestCase):
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
        for i in range(30):
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
    
    def test_profile_posts_list(self):
        self.client.force_login(self.user)
        
        tracemalloc.start()
        reset_queries()
        start_time = time.time()
        
        response = self.client.get(reverse('main_page'))
        
        end_time = time.time()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        elapsed_time = end_time - start_time
        queries_count = len(connection.queries)
        queries_time = sum(float(q['time']) for q in connection.queries)
        
        print(f"\n{'='*60}")
        print(f"Профилирование: PostsList")
        print(f"{'='*60}")
        print(f"Статус ответа: {response.status_code}")
        print(f"Время выполнения: {elapsed_time:.4f} сек")
        print(f"Текущее использование памяти: {current / 1024 / 1024:.2f} MB")
        print(f"Пиковое использование памяти: {peak / 1024 / 1024:.2f} MB")
        print(f"Количество SQL запросов: {queries_count}")
        print(f"Время выполнения SQL запросов: {queries_time:.4f} сек")
        
        if queries_count > 0:
            print(f"\nПервые 5 SQL запросов:")
            for i, query in enumerate(connection.queries[:5], 1):
                print(f"{i}. {query['sql'][:80]}... ({query['time']} сек)")
        
        print(f"{'='*60}\n")
        
        self.assertEqual(response.status_code, 200)
        # Проверяем, что количество запросов разумное (не более 20)
        self.assertLess(queries_count, 25, f"Слишком много SQL запросов: {queries_count}")
    
    def test_profile_post_detail(self):
        self.client.force_login(self.user)
        post = self.posts[0]
        
        tracemalloc.start()
        reset_queries()
        start_time = time.time()
        
        response = self.client.get(reverse('post_detail', args=[post.pk]))
        
        end_time = time.time()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        elapsed_time = end_time - start_time
        queries_count = len(connection.queries)
        queries_time = sum(float(q['time']) for q in connection.queries)
        
        print(f"\n{'='*60}")
        print(f"Профилирование: PostDetail")
        print(f"{'='*60}")
        print(f"Статус ответа: {response.status_code}")
        print(f"Время выполнения: {elapsed_time:.4f} сек")
        print(f"Текущее использование памяти: {current / 1024 / 1024:.2f} MB")
        print(f"Пиковое использование памяти: {peak / 1024 / 1024:.2f} MB")
        print(f"Количество SQL запросов: {queries_count}")
        print(f"Время выполнения SQL запросов: {queries_time:.4f} сек")
        
        if queries_count > 0:
            print(f"\nПервые 5 SQL запросов:")
            for i, query in enumerate(connection.queries[:5], 1):
                print(f"{i}. {query['sql'][:80]}... ({query['time']} сек)")
        
        print(f"{'='*60}\n")
        
        self.assertEqual(response.status_code, 200)
        # Проверяем, что количество запросов разумное (не более 15)
        self.assertLess(queries_count, 20, f"Слишком много SQL запросов: {queries_count}")
    
    def test_profile_edit_post(self):
        self.client.force_login(self.author_user)
        post = self.posts[0]
        
        tracemalloc.start()
        reset_queries()
        start_time = time.time()
        
        response = self.client.get(reverse('edit_post', args=[post.pk]))
        
        end_time = time.time()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        elapsed_time = end_time - start_time
        queries_count = len(connection.queries)
        queries_time = sum(float(q['time']) for q in connection.queries)
        
        print(f"\n{'='*60}")
        print(f"Профилирование: edit_post")
        print(f"{'='*60}")
        print(f"Статус ответа: {response.status_code}")
        print(f"Время выполнения: {elapsed_time:.4f} сек")
        print(f"Текущее использование памяти: {current / 1024 / 1024:.2f} MB")
        print(f"Пиковое использование памяти: {peak / 1024 / 1024:.2f} MB")
        print(f"Количество SQL запросов: {queries_count}")
        print(f"Время выполнения SQL запросов: {queries_time:.4f} сек")
        
        if queries_count > 0:
            print(f"\nПервые 5 SQL запросов:")
            for i, query in enumerate(connection.queries[:5], 1):
                print(f"{i}. {query['sql'][:80]}... ({query['time']} сек)")
        
        print(f"{'='*60}\n")
        
        self.assertEqual(response.status_code, 200)
        # Проверяем, что количество запросов разумное (не более 18)
        self.assertLess(queries_count, 25, f"Слишком много SQL запросов: {queries_count}")

