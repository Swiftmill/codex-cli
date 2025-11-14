from __future__ import annotations

import subprocess
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from RestrictedPython import compile_restricted
from RestrictedPython import safe_builtins, utility_builtins
from RestrictedPython.Eval import default_guarded_getiter
from RestrictedPython.PrintCollector import PrintCollector


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    returncode: int
    duration: float


class SandboxRunner:
    """Execute code in a controlled environment."""

    def __init__(self, *, timeout: int = 30):
        self.timeout = timeout

    def _restricted_globals(self) -> Dict[str, object]:
        allowed_builtins = dict(safe_builtins)
        allowed_builtins.update(
            {
                "range": range,
                "len": len,
                "enumerate": enumerate,
                "min": min,
                "max": max,
                "sum": sum,
            }
        )
        allowed_builtins.update(utility_builtins)
        allowed_globals = {
            "__builtins__": allowed_builtins,
            "_print_": PrintCollector,
            "_getattr_": getattr,
            "_setattr_": setattr,
            "_getitem_": lambda obj, key: obj[key],
            "_getiter_": default_guarded_getiter,
        }
        return allowed_globals

    def run_python(self, script_path: Path) -> SandboxResult:
        start = time.time()
        try:
            code = script_path.read_text(encoding="utf-8")
        except OSError as exc:
            return SandboxResult("", str(exc), 1, 0.0)

        try:
            byte_code = compile_restricted(code, filename=str(script_path), mode="exec")
        except SyntaxError as exc:
            stderr = textwrap.dedent(
                f"""
                Erreur de syntaxe: {exc.msg}
                Ligne {exc.lineno}: {exc.text}
                """
            ).strip()
            return SandboxResult("", stderr, 1, time.time() - start)

        stdout_buffer = PrintCollector()
        locals_dict: Dict[str, object] = {}
        globals_dict = self._restricted_globals()
        globals_dict["print"] = stdout_buffer

        try:
            exec(byte_code, globals_dict, locals_dict)  # noqa: S102 - RestrictedPython handles safety
        except Exception as exc:  # noqa: BLE001
            stderr = repr(exc)
            return SandboxResult(stdout_buffer.getvalue(), stderr, 1, time.time() - start)

        duration = time.time() - start
        return SandboxResult(stdout_buffer.getvalue(), "", 0, duration)

    def run_subprocess(self, target: str) -> SandboxResult:
        start = time.time()
        try:
            completed = subprocess.run(
                target,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
                check=False,
                text=True,
            )
        except subprocess.TimeoutExpired:
            duration = time.time() - start
            return SandboxResult("", f"Temps d'exécution dépassé ({self.timeout}s)", 124, duration)
        except OSError as exc:
            duration = time.time() - start
            return SandboxResult("", str(exc), 1, duration)
        duration = time.time() - start
        return SandboxResult(completed.stdout, completed.stderr, completed.returncode, duration)

    def run(self, target: str) -> SandboxResult:
        path = Path(target)
        if path.exists() and path.suffix == ".py":
            return self.run_python(path)
        return self.run_subprocess(target)
