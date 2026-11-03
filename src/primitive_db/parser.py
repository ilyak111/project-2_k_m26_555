"""Разбор команд insert, select, update и delete."""

import json

from primitive_db.constants import BOOLEAN_LITERALS, PUNCTUATION, QUOTES


def tokenize(command):
    """Разбивает команду на части, сохраняя строки в кавычках."""
    tokens = []
    position = 0
    while position < len(command):
        character = command[position]
        if character.isspace():
            position += 1
            continue
        start = position
        if character in PUNCTUATION:
            position += 1
        elif character in QUOTES:
            quote = character
            position += 1
            while position < len(command) and command[position] != quote:
                if command[position] == "\\":
                    position += 1
                position += 1
            if position >= len(command):
                raise ValueError("Строка должна заканчиваться закрывающей кавычкой.")
            position += 1
        else:
            while (
                position < len(command)
                and not command[position].isspace()
                and command[position] not in PUNCTUATION + QUOTES
            ):
                position += 1
        tokens.append(command[start:position])
    return tokens


def decode_string(token):
    """Читает строку в кавычках и заменяет escape-последовательности."""
    if len(token) < 2 or token[-1] != token[0]:
        raise ValueError(f"Некорректная строка: {token}.")
    if token[0] == '"':
        return json.loads(token)
    # json.loads принимает двойные кавычки. Одинарные сначала переводим в JSON.
    result = ['"']
    position = 1
    while position < len(token) - 1:
        character = token[position]
        if character != "\\":
            result.append('\\"' if character == '"' else character)
            position += 1
            continue
        if position + 1 >= len(token) - 1:
            raise ValueError(f"Некорректное экранирование: {token}.")
        escaped = token[position + 1]
        if escaped == "'":
            result.append("'")
            position += 2
        else:
            result.append(token[position : position + 2])
            position += 2
    result.append('"')
    return json.loads("".join(result))


def parse_value(token):
    """Определяет значение: str, int или bool."""
    if token.startswith(('"', "'")):
        return decode_string(token)
    if token in BOOLEAN_LITERALS:
        return BOOLEAN_LITERALS[token]
    digits = token[1:] if token.startswith(("+", "-")) else token
    if digits and all("0" <= character <= "9" for character in digits):
        return int(token)
    raise ValueError(f"Некорректное значение: {token}. Строки указывайте в кавычках.")


def parse_assignments(tokens):
    """Собирает пары столбец = значение в словарь."""
    if not tokens:
        raise ValueError("Ожидается условие вида столбец = значение.")
    fields = {}
    while tokens:
        if len(tokens) < 3 or not tokens[0].isidentifier() or tokens[1] != "=":
            raise ValueError("Ожидается условие вида столбец = значение.")
        name = tokens[0]
        if name in fields:
            raise ValueError(f'Столбец "{name}" указан повторно.')
        fields[name] = parse_value(tokens[2])
        tokens = tokens[3:]
        if tokens:
            if tokens[0] != "," or len(tokens) == 1:
                raise ValueError("Присваивания SET разделяются запятыми.")
            tokens = tokens[1:]
    return fields


def parse_where(clause):
    """Разбирает одно условие where."""
    tokens = tokenize(clause) if isinstance(clause, str) else clause
    if len(tokens) != 3:
        raise ValueError("WHERE поддерживает одно условие: столбец = значение.")
    return parse_assignments(tokens)


def parse_set(clause):
    """Разбирает поля после set."""
    tokens = tokenize(clause) if isinstance(clause, str) else clause
    return parse_assignments(tokens)


def parse_values(tokens):
    """Разбирает список значений после values."""
    if len(tokens) < 2 or tokens[0] != "(" or tokens[-1] != ")":
        raise ValueError("Значения VALUES должны быть заключены в скобки.")
    values = tokens[1:-1]
    if not values:
        return []
    if len(values) % 2 == 0 or any(token != "," for token in values[1::2]):
        raise ValueError("Значения VALUES разделяются запятыми.")
    return [parse_value(token) for token in values[::2]]


def parse_crud(command):
    """Возвращает команду, имя таблицы, значения и условие."""
    tokens = tokenize(command)
    if len(tokens) >= 5 and tokens[:2] == ["insert", "into"] and tokens[3] == "values":
        return "insert", tokens[2], parse_values(tokens[4:]), None
    if len(tokens) >= 3 and tokens[:2] == ["select", "from"]:
        if len(tokens) == 3:
            return "select", tokens[2], None, None
        if tokens[3] == "where":
            return "select", tokens[2], None, parse_where(tokens[4:])
    if (
        len(tokens) >= 10
        and tokens[0] == "update"
        and tokens[2] == "set"
        and tokens[-4] == "where"
    ):
        return "update", tokens[1], parse_set(tokens[3:-4]), parse_where(tokens[-3:])
    if len(tokens) >= 4 and tokens[:2] == ["delete", "from"] and tokens[3] == "where":
        return "delete", tokens[2], None, parse_where(tokens[4:])
    if len(tokens) == 2 and tokens[0] == "info":
        return "info", tokens[1], None, None
    raise ValueError("Некорректный синтаксис команды. Введите help для справки.")
