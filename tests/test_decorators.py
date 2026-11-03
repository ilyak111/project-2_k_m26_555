import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from primitive_db.core import (
    delete,
    drop_table,
    insert,
    invalidate_select_cache,
    matches,
    select,
)
from primitive_db.decorators import (
    confirm_action,
    create_cacher,
    handle_db_errors,
    log_time,
)
from primitive_db.engine import handle_crud, handle_table_change
from primitive_db.utils import save_metadata, save_table_data


class DecoratorTests(unittest.TestCase):
    def test_error_categories_return_none_and_preserve_metadata(self):
        for error, message in (
            (FileNotFoundError(), "Файл данных не найден"),
            (KeyError("users"), "Таблица или столбец"),
            (ValueError("bad"), "Ошибка валидации"),
            (PermissionError("denied"), "Ошибка работы с файлами"),
            (RuntimeError("unexpected"), "непредвиденная ошибка"),
        ):

            @handle_db_errors
            def operation():
                """Тестовая функция."""
                raise error

            with (
                self.subTest(error=error),
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                self.assertIsNone(operation())
                self.assertIn(message, output.getvalue())
                self.assertEqual(operation.__name__, "operation")
                self.assertEqual(operation.__doc__, "Тестовая функция.")

        @handle_db_errors
        def success(value):
            return value

        self.assertEqual(success(value=42), 42)

    def test_confirmation_and_cancellation(self):
        operation = Mock(return_value="done")
        wrapped = confirm_action("удаление")(operation)
        for answer in ("n", "", "yes", "no"):
            with (
                patch("builtins.input", return_value=answer),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertIsNone(wrapped(1, value=2))
        operation.assert_not_called()
        with patch("builtins.input", return_value="y") as question:
            self.assertEqual(wrapped(1, value=2), "done")
        self.assertIn('"удаление"? [y/n]:', question.call_args.args[0])
        operation.assert_called_once_with(1, value=2)
        for error in (EOFError, KeyboardInterrupt):
            with (
                patch("builtins.input", side_effect=error),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertIsNone(wrapped())

    def test_log_time_format_and_exception(self):
        @log_time
        def operation(value):
            return value

        with (
            patch("primitive_db.decorators.time.monotonic", side_effect=[10, 10.125]),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(operation(42), 42)
        self.assertEqual(
            output.getvalue(), "Функция operation выполнилась за 0.125 секунд\n"
        )
        self.assertEqual(operation.__name__, "operation")

        @log_time
        def failing():
            raise ValueError("bad")

        with (
            contextlib.redirect_stdout(io.StringIO()) as output,
            self.assertRaises(ValueError),
        ):
            failing()
        self.assertIn("Функция failing выполнилась за", output.getvalue())

    def test_cacher_independent_instances_none_and_failed_computation(self):
        cache = create_cacher()
        other = create_cacher()
        calculate = Mock(return_value=None)
        self.assertIsNone(cache("key", calculate))
        self.assertIsNone(cache("key", calculate))
        calculate.assert_called_once()
        self.assertEqual(other("key", lambda: 42), 42)
        cache.clear()
        self.assertEqual(cache("key", lambda: 99), 99)
        failing = Mock(side_effect=[ValueError("bad"), 1])
        with self.assertRaises(ValueError):
            cache("retry", failing)
        self.assertEqual(cache("retry", failing), 1)

    def test_select_cache_snapshot_types_and_copy_isolation(self):
        invalidate_select_cache()
        data = [{"ID": 1, "active": True}]

        with (
            patch("primitive_db.core.matches", wraps=matches) as matching,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            first = select(data, {"ID": 1})
            first[0]["ID"] = 99
            self.assertEqual(select(data, {"ID": 1})[0]["ID"], 1)
            self.assertEqual(matching.call_count, 1)
            self.assertEqual(select(data, {"ID": True}), [])
            data[0]["ID"] = 2
            self.assertEqual(select(data, {"ID": 1}), [])
            data[0]["ID"] = 1
            self.assertEqual(select(data, {"ID": 1})[0]["ID"], 1)
            invalidate_select_cache()
            select(data, {"ID": 1})
            self.assertEqual(matching.call_count, 4)

    def test_cancelled_operations_do_not_change_arguments_or_save(self):
        metadata = {"users": ["ID:int", "name:str"]}
        data = [{"ID": 1, "name": "A"}]
        with (
            patch("builtins.input", return_value="n"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertIsNone(drop_table(metadata, "users"))
            self.assertIsNone(delete(data, {"ID": 1}))
        self.assertIn("users", metadata)
        self.assertEqual(data, [{"ID": 1, "name": "A"}])
        with (
            patch("builtins.input", return_value="n"),
            patch("primitive_db.engine.save_metadata") as save,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            handle_table_change(metadata, "drop_table", ["users"])
        save.assert_not_called()

    def test_cli_confirmation_cancel_then_accept_and_cache_after_write(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-m", "primitive_db.main"],
                input=(
                    "create_table users name:str\n"
                    'insert into users values ("A")\n'
                    "select from users\nselect from users\n"
                    'update users set name="B" where ID=1\nselect from users\n'
                    "delete from users where ID=1\nn\ninfo users\n"
                    "delete from users where ID=1\ny\ninfo users\n"
                    "drop_table users\nn\nlist_tables\ndrop_table users\ny\nexit\n"
                ),
                text=True,
                encoding="utf-8",
                capture_output=True,
                cwd=directory,
                timeout=10,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.count("Операция отменена."), 2)
            self.assertIn("Количество записей: 1", result.stdout)
            self.assertIn("Количество записей: 0", result.stdout)
            self.assertIn(" B ", result.stdout)
            self.assertIn("Функция select выполнилась за", result.stdout)
            self.assertEqual(
                (Path(directory) / "db_meta.json").read_text().strip(), "{}"
            )
            self.assertFalse((Path(directory) / "data/users.json").exists())

    def test_error_and_cancel_preserve_real_files(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                metadata = {"users": ["ID:int", "name:str"]}
                save_metadata("db_meta.json", metadata)
                save_table_data("users", [{"ID": 1, "name": "A"}])
                before = Path("data/users.json").read_bytes()
                with (
                    patch("builtins.input", return_value="n"),
                    contextlib.redirect_stdout(io.StringIO()) as output,
                ):
                    handle_crud(metadata, "delete from users where ID=1")
                    handle_crud(metadata, "insert into users values (42)")
                self.assertEqual(Path("data/users.json").read_bytes(), before)
                self.assertNotIn("успешно", output.getvalue())
                self.assertIsNone(insert(metadata, "missing", []))
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
