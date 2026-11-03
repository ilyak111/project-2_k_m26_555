# Примитивная база данных

Учебный проект на Python. База данных работает в консоли: можно создавать
таблицы, добавлять, читать, изменять и удалять записи. Для вывода используется
PrettyTable, для ввода команд - prompt.

## Установка и запуск

Нужны Python 3.12 или новее и uv. Из папки проекта:

```text
uv sync --locked
uv run database
```

Можно запустить через GNU Make:

```text
make install
make run
```

На Windows вместо GNU Make иногда запускается Borland Make из Delphi.
В таком случае используйте команды uv или GNU Make из MSYS2.

## Команды

```text
create_table <таблица> <столбец:тип> ...
list_tables
drop_table <таблица>
insert into <таблица> values (<значение>, ...)
select from <таблица>
select from <таблица> where <столбец> = <значение>
update <таблица> set <столбец> = <значение> where <столбец> = <значение>
delete from <таблица> where <столбец> = <значение>
info <таблица>
help
exit
```

Типы столбцов: `int`, `str`, `bool`. Строки вводятся в кавычках, логические
значения - `true` и `false`. Все поля обязательны. Значения для `insert`
передаются в порядке столбцов, без ID. Столбец `ID:int` добавляется автоматически,
новый ID равен максимальному ID в таблице плюс один. В пустой таблице это 1.
Менять ID нельзя.

В `where` поддерживается одно сравнение на равенство. В `set` можно указать
несколько полей через запятую. Обновляются или удаляются все подходящие записи.
Перед удалением записей или таблицы нужно ответить `y`, другой ответ отменяет
действие.

Пример работы:

```text
create_table users name:str age:int is_active:bool
list_tables
insert into users values ("Sergei", 28, true)
select from users
select from users where age = 28
update users set age = 29 where name = "Sergei"
select from users
delete from users where ID = 1
y
info users
drop_table users
y
exit
```

Схемы таблиц хранятся в `db_meta.json`, записи - в `data/<таблица>.json`.
Файлы создаются в текущей папке, поэтому для работы с той же БД нужно запускать
программу из неё же. При удалении таблицы удаляется и файл её записей.

Декораторы обрабатывают ошибки, запрашивают подтверждение удаления и печатают
время работы `insert` и `select`. Результаты повторных запросов `select`
хранятся в кэше до изменения данных или завершения программы.

## Проверка и сборка

```text
make lint
make test
make build
uvx twine check dist/*
```

Без Make: `uv run ruff check .`, `uv run ruff format --check .`,
`uv run python -m unittest discover -s tests -v` и `uv build`.
Эти проверки также запускаются в GitHub Actions.

Собранный пакет можно установить отдельно:

```text
uv tool install --force dist/primitive_db-0.5.0-py3-none-any.whl
database
```

Если `database` не находится, выполните `uv tool update-shell` и откройте
терминал заново.

## Демонстрация

[![Работа с базой данных](https://asciinema.org/a/wFOFR8HzpTftcWy4.svg)](https://asciinema.org/a/wFOFR8HzpTftcWy4)
