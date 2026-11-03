"""Настройки файлов, столбцов и команд."""

META_FILE = "db_meta.json"
DATA_DIR = "data"
SUPPORTED_TYPES = {"int": int, "str": str, "bool": bool}
PRIMARY_KEY = "ID"
PRIMARY_KEY_TYPE = "int"
COLUMN_SEPARATOR = ":"
ID_COLUMN = f"{PRIMARY_KEY}{COLUMN_SEPARATOR}{PRIMARY_KEY_TYPE}"
FIRST_ID = 1
TABLE_FILE_SUFFIX = ".json"
TEMP_FILE_SUFFIX = ".tmp"
ENCODING = "utf-8"
JSON_INDENT = 2
PUNCTUATION = "(),="
QUOTES = "\"'"
CONFIRM_ANSWER = "y"
BOOLEAN_LITERALS = {"true": True, "false": False}
CRUD_COMMANDS = frozenset({"insert", "select", "update", "delete", "info"})
NO_ARGUMENT_COMMANDS = frozenset({"list_tables", "help", "exit"})
TABLE_COMMANDS = NO_ARGUMENT_COMMANDS | {"create_table", "drop_table"}
WRAPPED_ATTRIBUTES = ("__name__", "__doc__", "__module__", "__annotations__")
