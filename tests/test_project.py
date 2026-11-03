"""Проверки структуры проекта и импортов."""

import ast
import unittest
from pathlib import Path


class ProjectTests(unittest.TestCase):
    def test_application_imports_functions_and_structure(self):
        root = Path(__file__).resolve().parents[1] / "src" / "primitive_db"
        allowed = {
            "json",
            "shlex",
            "time",
            "os",
            "prettytable",
            "prompt",
            "primitive_db",
        }
        required = {
            "main.py",
            "engine.py",
            "core.py",
            "utils.py",
            "parser.py",
            "decorators.py",
            "constants.py",
            "__init__.py",
        }
        self.assertTrue(required.issubset({path.name for path in root.glob("*.py")}))
        for path in root.glob("*.py"):
            with self.subTest(module=path.name):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    self.assertNotIsInstance(node, ast.ClassDef)
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            self.assertIn(alias.name.split(".")[0], allowed)
                    elif isinstance(node, ast.ImportFrom):
                        self.assertIn(node.module.split(".")[0], allowed)
                    elif isinstance(node, ast.FunctionDef):
                        self.assertTrue(
                            ast.get_docstring(node), f"{path.name}: {node.name}"
                        )
