"""Проверка столбцов и значений."""

from primitive_db.constants import (
    COLUMN_SEPARATOR,
    FIRST_ID,
    ID_COLUMN,
    PRIMARY_KEY,
    PRIMARY_KEY_TYPE,
    SUPPORTED_TYPES,
)


def normalize_columns(columns):
    """Проверяет столбцы и ставит ID первым."""
    result = [ID_COLUMN]
    names = set()
    for column in columns:
        parts = column.split(COLUMN_SEPARATOR)
        if len(parts) != 2:
            raise ValueError(column)
        name, data_type = parts
        if not name.isidentifier() or data_type not in SUPPORTED_TYPES or name in names:
            raise ValueError(column)
        names.add(name)
        if name == PRIMARY_KEY:
            if data_type != PRIMARY_KEY_TYPE:
                raise ValueError(column)
        else:
            result.append(column)
    return result


def validate_fields(columns, fields, *, allow_id=True):
    """Проверяет имена и типы переданных значений."""
    schema = dict(column.split(COLUMN_SEPARATOR) for column in columns)
    for name, value in fields.items():
        if name not in schema:
            raise ValueError(f'Столбец "{name}" не существует.')
        if name == PRIMARY_KEY and not allow_id:
            raise ValueError("ID генерируется автоматически и не может быть изменён.")
        expected = schema[name]
        # isinstance(True, int) возвращает True, поэтому сравниваем типы напрямую.
        if type(value) is not SUPPORTED_TYPES[expected]:
            raise ValueError(f'Столбец "{name}" требует тип {expected}.')


def validate_table_data(columns, data):
    """Проверяет записи из файла и повторяющиеся ID."""
    names = {column.split(COLUMN_SEPARATOR)[0] for column in columns}
    ids = set()
    for row in data:
        if not isinstance(row, dict) or set(row) != names:
            raise ValueError("Структура сохранённой записи не соответствует схеме.")
        validate_fields(columns, row)
        if row[PRIMARY_KEY] < FIRST_ID or row[PRIMARY_KEY] in ids:
            raise ValueError("ID записей должны быть положительными и уникальными.")
        ids.add(row[PRIMARY_KEY])
