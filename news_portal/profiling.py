import tracemalloc
import time
from functools import wraps
from django.db import connection, reset_queries
from django.conf import settings

def profile_view(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        tracemalloc.start()
        reset_queries()
        start_time = time.time()
        
        result = func(*args, **kwargs)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        queries_count = len(connection.queries)
        queries_time = sum(float(q['time']) for q in connection.queries)
        
        print(f"\n{'='*60}")
        print(f"Профилирование: {func.__name__}")
        print(f"{'='*60}")
        print(f"Время выполнения: {elapsed_time:.4f} сек")
        print(f"Текущее использование памяти: {current / 1024 / 1024:.2f} MB")
        print(f"Пиковое использование памяти: {peak / 1024 / 1024:.2f} MB")
        print(f"Количество SQL запросов: {queries_count}")
        print(f"Время выполнения SQL запросов: {queries_time:.4f} сек")
        
        if settings.DEBUG and queries_count > 0:
            print(f"\nSQL запросы:")
            for i, query in enumerate(connection.queries[:10], 1):
                print(f"{i}. {query['sql'][:100]}... ({query['time']} сек)")
            if queries_count > 10:
                print(f"... и еще {queries_count - 10} запросов")
        
        print(f"{'='*60}\n")
        
        return result
    return wrapper

def get_top_memory_stats():
    snapshot = tracemalloc.take_snapshot()
    top_stats = snapshot.statistics('lineno')
    
    print("\nТоп 10 строк по использованию памяти:")
    for index, stat in enumerate(top_stats[:10], 1):
        print(f"{index}. {stat}")

