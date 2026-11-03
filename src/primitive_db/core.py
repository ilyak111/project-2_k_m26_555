import json

from primitive_db.constants import COLUMN_SEPARATOR, FIRST_ID, PRIMARY_KEY
from primitive_db.decorators import (
    confirm_action,
    create_cacher,
    handle_db_errors,
    log_time,
)
from primitive_db.utils import load_table_data
from primitive_db.validation import (
    normalize_columns,
    validate_fields,
    validate_table_data,
)


@handle_db_errors
def create_table(metadata, table_name, columns):
    """Создаёт таблицу и добавляет её схему в metadata."""
    if any(name.casefold() == table_name.casefold() for name in metadata):
        raise ValueError(f'Таблица "{table_name}" уже существует.')
    if not table_name.isidentifier():
        raise ValueError(table_name)
    normalized = normalize_columns(columns)
    metadata[table_name] = normalized
    return metadata


@handle_db_errors
@confirm_action("удаление таблицы")
def drop_table(metadata, table_name):
    """Удаляет таблицу из metadata после подтверждения."""
    if table_name not in metadata:
        raise KeyError(table_name)
    del metadata[table_name]
    return metadata


@handle_db_errors
def list_tables(metadata):
    """Печатает список таблиц."""
    if not metadata:
        print("Таблиц пока нет.")
    for table_name in metadata:
        print(f"- {table_name}")


@handle_db_errors
@log_time
def insert(metadata, table_name, values):
    """Проверяет значения и добавляет запись с новым ID."""
    if table_name not in metadata:
        raise ValueError(f'Таблица "{table_name}" не существует.')
    columns = metadata[table_name]
    names = [column.split(COLUMN_SEPARATOR)[0] for column in columns[1:]]
    if len(values) != len(names):
        raise ValueError(f"Ожидается значений: {len(names)}, получено: {len(values)}.")
    fields = dict(zip(names, values))
    validate_fields(columns, fields, allow_id=False)
    data = load_table_data(table_name)
    validate_table_data(columns, data)
    next_id = max((row[PRIMARY_KEY] for row in data), default=FIRST_ID - 1) + 1
    data.append({PRIMARY_KEY: next_id, **fields})
    return data


def matches(row, clause):
    """Проверяет, подходит ли запись под условие."""
    for name, value in clause.items():
        if name not in row or type(row[name]) is not type(value):
            return False
        if row[name] != value:
            return False
    return True


_select_cache = create_cacher()


def invalidate_select_cache():
    """Очищает кэш запросов."""
    _select_cache.clear()


@handle_db_errors
@log_time
def select(table_data, where_clause=None):
    """Возвращает все записи или записи по условию."""
    # Изменение данных должно менять ключ кэша.
    key = (
        json.dumps(table_data, sort_keys=True, ensure_ascii=False),
        json.dumps(where_clause, sort_keys=True, ensure_ascii=False),
    )

    def find_rows():
        """Собирает подходящие записи для кэша."""
        rows = []
        for row in table_data:
            if where_clause is None or matches(row, where_clause):
                rows.append(dict(row))
        return rows

    result = _select_cache(key, find_rows)
    # Возвращаем копии, чтобы результат запроса не менял кэш.
    return [dict(row) for row in result]


@handle_db_errors
def update(table_data, set_clause, where_clause):
    """Обновляет поля у записей, подходящих под условие."""
    if PRIMARY_KEY in set_clause:
        raise ValueError("ID генерируется автоматически и не может быть изменён.")
    result = []
    for row in table_data:
        updated_row = dict(row)
        if matches(row, where_clause):
            updated_row.update(set_clause)
        result.append(updated_row)
    return result


@handle_db_errors
@confirm_action("удаление записей")
def delete(table_data, where_clause):
    """Удаляет записи по условию после подтверждения."""
    remaining = []
    for row in table_data:
        if not matches(row, where_clause):
            remaining.append(row)
    return remaining
