import shlex

import prompt
from prettytable import PrettyTable

from primitive_db.constants import (
    COLUMN_SEPARATOR,
    CRUD_COMMANDS,
    META_FILE,
    NO_ARGUMENT_COMMANDS,
    PRIMARY_KEY,
    TABLE_COMMANDS,
)
from primitive_db.core import (
    create_table,
    delete,
    drop_table,
    insert,
    invalidate_select_cache,
    list_tables,
    select,
    update,
)
from primitive_db.decorators import handle_db_errors
from primitive_db.parser import parse_crud
from primitive_db.utils import (
    load_metadata,
    load_table_data,
    remove_table_data,
    save_metadata,
    save_table_data,
)
from primitive_db.validation import validate_fields, validate_table_data


def print_help() -> None:
    """Печатает доступные команды."""
    print("\n***Процесс работы с таблицей***")
    print("Функции:")
    print("<command> create_table <имя_таблицы> <столбец1:тип> .. - создать таблицу")
    print("<command> list_tables - показать список всех таблиц")
    print("<command> drop_table <имя_таблицы> - удалить таблицу")
    print("\n***Операции с данными***")
    print("insert into <таблица> values (<значение1>, <значение2>, ...) - добавить")
    print("select from <таблица> [where <столбец> = <значение>] - прочитать")
    print("update <таблица> set <столбец> = <значение> where <столбец> = <значение>")
    print("delete from <таблица> where <столбец> = <значение> - удалить записи")
    print("info <таблица> - структура и количество записей")
    print("Типы: int, str, bool. Строки в кавычках, логические значения: true/false.")
    print("<command> exit - выход из программы")
    print("<command> help - справочная информация")


@handle_db_errors
def handle_crud(metadata, user_input):
    """Выполняет команду для работы с записями."""
    command, table_name, values, where = parse_crud(user_input)
    if table_name not in metadata:
        raise ValueError(f'Таблица "{table_name}" не существует.')
    columns = metadata[table_name]
    if where is not None:
        validate_fields(columns, where)
    if command == "insert":
        data = insert(metadata, table_name, values)
        if data is None:
            return
        save_table_data(table_name, data)
        invalidate_select_cache()
        print(
            f"Запись с ID={data[-1][PRIMARY_KEY]} успешно добавлена "
            f'в таблицу "{table_name}".'
        )
        return
    data = load_table_data(table_name)
    validate_table_data(columns, data)
    if command == "info":
        print(f"Таблица: {table_name}")
        print("Столбцы: " + ", ".join(columns))
        print(f"Количество записей: {len(data)}")
    elif command == "select":
        names = [column.split(COLUMN_SEPARATOR)[0] for column in columns]
        table = PrettyTable(names)
        rows = select(data, where)
        if rows is None:
            return
        for row in rows:
            table.add_row([row[name] for name in names])
        print(table)
    else:
        if command == "update":
            validate_fields(columns, values, allow_id=False)
        affected = select(data, where)
        if not affected:
            print("Записи по условию не найдены.")
            return
        if command == "update":
            changed = update(data, values, where)
        else:
            changed = delete(data, where)
        if changed is None:
            return
        save_table_data(table_name, changed)
        invalidate_select_cache()
        for row in affected:
            if command == "update":
                print(
                    f'Запись с ID={row[PRIMARY_KEY]} в таблице "{table_name}" '
                    "успешно обновлена."
                )
            else:
                print(
                    f"Запись с ID={row[PRIMARY_KEY]} успешно удалена "
                    f'из таблицы "{table_name}".'
                )


@handle_db_errors
def handle_table_change(metadata, command, arguments):
    """Создаёт или удаляет таблицу и сохраняет изменения."""
    table_name = arguments[0]
    if command == "create_table":
        result = create_table(metadata, table_name, arguments[1:])
    else:
        result = drop_table(metadata, table_name)
    if result is None:
        return
    if command == "create_table":
        save_table_data(table_name, [])
    save_metadata(META_FILE, metadata)
    if command == "drop_table":
        remove_table_data(table_name)
    invalidate_select_cache()
    if command == "create_table":
        print(
            f'Таблица "{table_name}" успешно создана со столбцами: '
            + ", ".join(metadata[table_name])
        )
    else:
        print(f'Таблица "{table_name}" успешно удалена.')


def run() -> None:
    """Запускает ввод и выполнение команд."""
    print("***База данных***")
    print_help()
    while True:
        try:
            metadata = load_metadata(META_FILE)
        except (OSError, ValueError) as error:
            print(f"Ошибка чтения метаданных: {error}")
            return
        try:
            user_input = prompt.string("\n>>>Введите команду: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return
        first_word = user_input.strip().split(maxsplit=1)
        if first_word and first_word[0] in CRUD_COMMANDS:
            handle_crud(metadata, user_input)
            continue
        try:
            args = shlex.split(user_input)
        except ValueError:
            print(f"Некорректное значение: {user_input}. Попробуйте снова.")
            continue
        if not args:
            continue
        command, *arguments = args
        if command not in TABLE_COMMANDS:
            print(f"Функции {command} нет. Попробуйте снова.")
            continue
        valid_arguments = (
            (command == "create_table" and len(arguments) >= 1)
            or (command == "drop_table" and len(arguments) == 1)
            or (command in NO_ARGUMENT_COMMANDS and not arguments)
        )
        if not valid_arguments:
            print(f"Некорректное значение: {user_input}. Попробуйте снова.")
            continue
        if command == "exit":
            return
        elif command == "help":
            print_help()
        elif command == "list_tables":
            list_tables(metadata)
        else:
            handle_table_change(metadata, command, arguments)
