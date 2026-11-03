"""Декораторы для команд БД и функция кэширования."""

import time

from primitive_db.constants import CONFIRM_ANSWER, WRAPPED_ATTRIBUTES


def wraps(func):
    """Сохраняет имя и описание функции после декорирования."""

    def decorate(wrapper):
        """Копирует атрибуты исходной функции."""
        for attribute in WRAPPED_ATTRIBUTES:
            if hasattr(func, attribute):
                setattr(wrapper, attribute, getattr(func, attribute))
        wrapper.__wrapped__ = func
        return wrapper

    return decorate


def handle_db_errors(func):
    """Печатает ошибку и возвращает None."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        """Вызывает функцию с обработкой ошибок."""
        try:
            return func(*args, **kwargs)
        except FileNotFoundError:
            print(
                "Ошибка: Файл данных не найден. "
                "Возможно, база данных не инициализирована."
            )
        except KeyError as error:
            print(f"Ошибка: Таблица или столбец {error} не найден.")
        except ValueError as error:
            print(f"Ошибка валидации: {error}")
        except OSError as error:
            print(f"Ошибка работы с файлами: {error}")
        except Exception as error:
            print(f"Произошла непредвиденная ошибка: {error}")
        return None

    return wrapper


def confirm_action(action_name):
    """Запрашивает подтверждение перед выполнением действия."""

    def decorator(func):
        """Добавляет подтверждение к функции."""

        @wraps(func)
        def wrapper(*args, **kwargs):
            """Выполняет действие только при ответе y."""
            try:
                answer = input(
                    f'Вы уверены, что хотите выполнить "{action_name}"? [y/n]: '
                )
            except (EOFError, KeyboardInterrupt):
                print()
                answer = "n"
            if answer.strip().lower() != CONFIRM_ANSWER:
                print("Операция отменена.")
                return None
            return func(*args, **kwargs)

        return wrapper

    return decorator


def log_time(func):
    """Печатает время работы функции."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        """Замеряет время вызова."""
        started = time.monotonic()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.monotonic() - started
            print(f"Функция {func.__name__} выполнилась за {elapsed:.3f} секунд")

    return wrapper


def create_cacher():
    """Создаёт функцию с собственным кэшем."""
    cache = {}

    def cache_result(key, value_func):
        """Берёт результат из кэша или вычисляет его."""
        if key not in cache:
            cache[key] = value_func()
        return cache[key]

    cache_result.clear = cache.clear
    return cache_result
