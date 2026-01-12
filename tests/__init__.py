# Импорты тестов (опциональные, чтобы не ломать основную функциональность)
try:
    from .test import test_func, test_create_post
except ImportError:
    pass

try:
    from .test_t1 import test_t1
except ImportError:
    pass

