import json
import os
import time

from primitive_db.constants import (
    DATA_DIR,
    ENCODING,
    JSON_INDENT,
    TABLE_FILE_SUFFIX,
    TEMP_FILE_SUFFIX,
)
from primitive_db.validation import normalize_columns


def load_metadata(filepath):
    """Загружает схемы таблиц. Если файла нет, возвращает пустой словарь."""
    try:
        with open(filepath, encoding=ENCODING) as file:
            data = json.load(file)
    except FileNotFoundError:
        return {}
    if not isinstance(data, dict):
        raise ValueError("Метаданные должны быть словарём таблиц.")
    for name, columns in data.items():
        if (
            not name.isidentifier()
            or not isinstance(columns, list)
            or not all(isinstance(column, str) for column in columns)
            or normalize_columns(columns) != columns
        ):
            raise ValueError(f'Некорректная структура таблицы "{name}".')
    return data


def save_metadata(filepath, data):
    """Сохраняет JSON через временный файл."""
    path = os.fspath(filepath)
    temporary_path = None
    try:
        candidate = f"{path}.{os.getpid()}.{time.monotonic_ns()}{TEMP_FILE_SUFFIX}"
        with open(candidate, "x", encoding=ENCODING) as file:
            temporary_path = candidate
            json.dump(data, file, ensure_ascii=False, indent=JSON_INDENT)
            file.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.remove(temporary_path)


def table_data_path(table_name):
    """Возвращает путь к файлу таблицы."""
    if not table_name.isidentifier():
        raise ValueError(f"Некорректное имя таблицы: {table_name}.")
    return os.path.join(DATA_DIR, f"{table_name}{TABLE_FILE_SUFFIX}")


def load_table_data(table_name):
    """Загружает записи таблицы. Если файла нет, возвращает пустой список."""
    try:
        with open(table_data_path(table_name), encoding=ENCODING) as file:
            data = json.load(file)
    except FileNotFoundError:
        return []
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise ValueError("Данные таблицы должны быть списком записей.")
    return data


def save_table_data(table_name, data):
    """Сохраняет записи таблицы в папку data."""
    path = table_data_path(table_name)
    os.makedirs(DATA_DIR, exist_ok=True)
    save_metadata(path, data)


def remove_table_data(table_name):
    """Удаляет файл таблицы, если он существует."""
    try:
        os.remove(table_data_path(table_name))
    except FileNotFoundError:
        pass
