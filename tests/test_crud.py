import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from primitive_db.core import delete, insert, select, update
from primitive_db.engine import handle_crud
from primitive_db.parser import parse_crud, parse_set, parse_where
from primitive_db.utils import load_table_data, save_metadata, save_table_data


class ParserTests(unittest.TestCase):
    def test_single_and_double_quotes_have_equivalent_escaping(self):
        for literal, expected in (
            (r'''"\ud83d\ude00"''', "\U0001f600"),
            (r"'\ud83d\ude00'", "\U0001f600"),
            (r"'A\"B'", 'A"B'),
            (r"'C:\\data'", "C:\\data"),
            (r"'O\'Brien'", "O'Brien"),
            ("''", ""),
            ('""', ""),
        ):
            with self.subTest(literal=literal):
                self.assertEqual(parse_where("name = " + literal), {"name": expected})

    def test_quoted_values_and_clauses(self):
        self.assertEqual(parse_where("age=28"), {"age": 28})
        self.assertEqual(
            parse_where('name = "A, = where set"'), {"name": "A, = where set"}
        )
        self.assertEqual(
            parse_set("age=29, active=false"), {"age": 29, "active": False}
        )
        self.assertEqual(
            parse_crud('insert into users values ("Иван, = where", -28, true)')[2],
            ["Иван, = where", -28, True],
        )
        self.assertEqual(parse_crud("insert into users values ()")[2], [])
        self.assertEqual(parse_where(r'''name = "A\"B"'''), {"name": 'A"B'})
        self.assertEqual(parse_where("name = 'O\"Brien'"), {"name": 'O"Brien'})
        self.assertEqual(
            parse_where(r'''name = "\u0418\u0432\u0430\u043d"'''), {"name": "Иван"}
        )
        self.assertEqual(parse_where(r"""name = 'O\'Brien' """), {"name": "O'Brien"})
        self.assertEqual(parse_where(r'''name = "C:\\data"'''), {"name": "C:\\data"})
        self.assertEqual(
            parse_crud('update users set name="where", age=29 where name="set"')[2:],
            ({"name": "where", "age": 29}, {"name": "set"}),
        )

    def test_malformed_commands_are_rejected(self):
        for command in (
            "insert into users values (Sergei, 28, true)",
            'insert into users values ("Sergei", 28, true,)',
            'insert into users values ("Sergei" 28 true)',
            'insert into users values ("unclosed)',
            'insert into users values ("x", 28, null)',
            'insert into users values ("x", 2.5, true)',
            "select from users where age == 28",
            "select from users where age=28 extra",
            "update users set age=29",
            "update users set age=29, age=30 where ID=1",
            "delete from users",
            "info users extra",
        ):
            with self.subTest(command=command), self.assertRaises(ValueError):
                parse_crud(command)


class CrudTests(unittest.TestCase):
    def setUp(self):
        self.confirm = patch("builtins.input", return_value="y")
        self.confirm.start()
        self.temporary = tempfile.TemporaryDirectory()
        self.previous_directory = Path.cwd()
        os.chdir(self.temporary.name)
        self.metadata = {"users": ["ID:int", "name:str", "age:int", "active:bool"]}
        save_metadata("db_meta.json", self.metadata)

    def tearDown(self):
        self.confirm.stop()
        os.chdir(self.previous_directory)
        self.temporary.cleanup()

    def command(self, command):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            handle_crud(self.metadata, command)
        return output.getvalue()

    def cli(self, commands):
        result = subprocess.run(
            [sys.executable, "-m", "primitive_db.main"],
            input=commands,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=10,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_insert_id_generation_and_required_types(self):
        self.assertEqual(load_table_data("users"), [])
        data = insert(self.metadata, "users", ["Sergei", 28, True])
        self.assertEqual(
            data[0], {"ID": 1, "name": "Sergei", "age": 28, "active": True}
        )
        save_table_data("users", [data[0], {**data[0], "ID": 3}])
        self.assertEqual(
            insert(self.metadata, "users", ["Other", 20, False])[-1]["ID"], 4
        )
        before = Path("data/users.json").read_bytes()
        for values in (
            ["name", 28],
            [1, "name", 28, True],
            ["name", True, True],
            ["name", 28, 1],
            ["name", "28", True],
            [None, 28, True],
        ):
            with self.subTest(values=values):
                self.assertIsNone(insert(self.metadata, "users", values))
        self.assertEqual(Path("data/users.json").read_bytes(), before)
        self.assertIsNone(insert(self.metadata, "missing", []))
        self.metadata["only_id"] = ["ID:int"]
        self.assertEqual(insert(self.metadata, "only_id", []), [{"ID": 1}])

    def test_select_update_delete_all_matches_without_mutating_input(self):
        data = [
            {"ID": 1, "name": "A", "age": 28, "active": True},
            {"ID": 2, "name": "B", "age": 28, "active": False},
            {"ID": 3, "name": "C", "age": 20, "active": True},
        ]
        self.assertEqual(select(data), data)
        self.assertEqual(len(select(data, {"age": 28})), 2)
        self.assertEqual(select(data, {"ID": True}), [])
        changed = update(data, {"age": 29}, {"age": 28})
        self.assertEqual([row["age"] for row in changed], [29, 29, 20])
        self.assertEqual(data[0]["age"], 28)
        self.assertEqual(delete(changed, {"age": 29}), [data[2]])
        self.assertEqual(delete(data, {"age": 100}), data)
        self.assertIsNone(update(data, {"ID": 9}, {"ID": 1}))

    def test_invalid_clauses_and_failed_save_do_not_change_file(self):
        self.command('insert into users values ("Sergei", 28, true)')
        before = Path("data/users.json").read_bytes()
        for command in (
            "select from users where missing=1",
            'select from users where age="28"',
            "update users set ID=2 where ID=1",
            "update users set age=true where ID=1",
            "update users set missing=1 where ID=1",
            "delete from users where active=1",
        ):
            with self.subTest(command=command):
                self.assertIn("Ошибка", self.command(command))
        self.assertEqual(Path("data/users.json").read_bytes(), before)
        with patch("primitive_db.engine.save_table_data", side_effect=PermissionError):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                handle_crud(self.metadata, "update users set age=29 where ID=1")
            self.assertIn("Ошибка работы с файлами", output.getvalue())
            self.assertNotIn("успешно", output.getvalue())
        self.assertEqual(Path("data/users.json").read_bytes(), before)

    def test_cli_full_workflow_persistence_and_drop_recreate(self):
        output = self.cli(
            'insert into users values ("Sergei", 28, true)\n'
            'insert into users values ("Иван, = where", 28, false)\n'
            "select from users where age=28\n"
            "update users set age=29, active=false where age=28\n"
            "select from users\ninfo users\nexit\n"
        )
        self.assertIn("+----+", output)
        self.assertIn("Sergei", output)
        self.assertIn("Иван, = where", output)
        self.assertIn("Количество записей: 2", output)
        self.assertEqual([row["age"] for row in load_table_data("users")], [29, 29])
        self.assertIn("Sergei", self.cli("select from users where ID=1\nexit\n"))
        self.cli("delete from users where ID=1\ny\nexit\n")
        self.assertEqual([row["ID"] for row in load_table_data("users")], [2])
        self.cli('insert into users values ("New", 18, true)\nexit\n')
        self.assertEqual([row["ID"] for row in load_table_data("users")], [2, 3])
        output = self.cli(
            'insert into users values ("Bad", true, true)\n'
            "update users set ID=99 where ID=2\n"
            "delete from users\nselect from missing\ninfo users\nexit\n"
        )
        self.assertIn("Количество записей: 2", output)
        self.cli("drop_table users\ny\ncreate_table users name:str\nexit\n")
        self.assertEqual(load_table_data("users"), [])
        self.cli("drop_table users\ny\nexit\n")
        self.assertFalse(Path("data/users.json").exists())

    def test_corrupt_table_data_is_not_overwritten(self):
        Path("data").mkdir()
        for content in (
            "{broken",
            "{}",
            '[{"ID": 1}]',
            '[{"ID": true, "name": "A", "age": 1, "active": true}]',
            json.dumps([{"ID": 1, "name": "A", "age": 1, "active": True}] * 2),
        ):
            Path("data/users.json").write_text(content, encoding="utf-8")
            output = self.cli('insert into users values ("X", 20, false)\nexit\n')
            self.assertIn("Ошибка", output)
            self.assertEqual(
                Path("data/users.json").read_text(encoding="utf-8"), content
            )


if __name__ == "__main__":
    unittest.main()
