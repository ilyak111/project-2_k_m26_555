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

from primitive_db.core import create_table, drop_table
from primitive_db.utils import load_metadata, save_metadata


class TableTests(unittest.TestCase):
    def setUp(self):
        self.confirm = patch("builtins.input", return_value="y")
        self.confirm.start()
        self.output = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.output)
        self.redirect.__enter__()

    def tearDown(self):
        self.confirm.stop()
        self.redirect.__exit__(None, None, None)

    def test_schema_and_explicit_id(self):
        metadata = create_table({}, "users", ["name:str", "age:int", "active:bool"])
        self.assertEqual(
            metadata["users"], ["ID:int", "name:str", "age:int", "active:bool"]
        )
        create_table(metadata, "other", ["name:str", "ID:int"])
        self.assertEqual(metadata["other"], ["ID:int", "name:str"])
        create_table(metadata, "only_id", [])
        self.assertEqual(metadata["only_id"], ["ID:int"])

    def test_invalid_schemas_do_not_mutate_metadata(self):
        for columns in (
            ["age:float"],
            ["name"],
            ["name:str:bool"],
            ["ID:str"],
            ["name:str", "name:int"],
            ["ID:int", "ID:int"],
            [":str"],
        ):
            with self.subTest(columns=columns):
                metadata = {"existing": ["ID:int"]}
                create_table(metadata, "users", columns)
                self.assertEqual(metadata, {"existing": ["ID:int"]})

    def test_duplicate_and_missing_tables(self):
        metadata = {"users": ["ID:int"]}
        create_table(metadata, "users", ["name:str"])
        create_table(metadata, "Users", ["name:str"])
        self.assertEqual(metadata, {"users": ["ID:int"]})
        drop_table(metadata, "missing")
        self.assertIn("users", metadata)
        self.assertEqual(drop_table(metadata, "users"), {})

    def test_file_roundtrip_and_failed_replace(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "db_meta.json"
            self.assertEqual(load_metadata(path), {})
            original = {"users": ["ID:int", "name:str"]}
            save_metadata(path, original)
            self.assertEqual(load_metadata(path), original)
            with patch("primitive_db.utils.os.replace", side_effect=PermissionError):
                with self.assertRaises(PermissionError):
                    save_metadata(path, {})
            self.assertEqual(load_metadata(path), original)
            self.assertEqual(list(Path(directory).iterdir()), [path])
            for content in ("{broken", "[]", '{"users": ["name:str"]}'):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_metadata(path)

    def test_cli_persistence_errors_and_deletion(self):
        with tempfile.TemporaryDirectory() as directory:

            def run(commands):
                result = subprocess.run(
                    [sys.executable, "-m", "primitive_db.main"],
                    input=commands,
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    cwd=directory,
                    timeout=10,
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                return result.stdout

            output = run(
                "create_table users name:str age:int is_active:bool\n"
                "create_table users name:str\ncreate_table bad value:float\n"
                "create_table\ndrop_table\nlist_tables extra\nhelp extra\n"
                'exit extra\nunknown\n"unterminated\nlist_tables\nexit\n'
            )
            self.assertIn("- users", output)
            self.assertIn("Функции unknown нет.", output)
            path = Path(directory) / "db_meta.json"
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"users": ["ID:int", "name:str", "age:int", "is_active:bool"]},
            )
            self.assertIn("- users", run("list_tables\nexit\n"))
            run("drop_table users\ny\ndrop_table products\ny\nexit\n")
            self.assertEqual(load_metadata(path), {})
            run("")
            path.write_text("{broken", encoding="utf-8")
            self.assertIn("Ошибка чтения метаданных", run("exit\n"))
            self.assertEqual(path.read_text(encoding="utf-8"), "{broken")


if __name__ == "__main__":
    unittest.main()
