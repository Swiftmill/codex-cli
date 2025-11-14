from __future__ import annotations

import json
import os
import subprocess
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from tree_sitter import Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript

from .sandbox import SandboxRunner, SandboxResult

SESSION_DIR = Path(__file__).resolve().parent.parent / "codex_sessions"
DEFAULT_MODEL = os.environ.get("CODEX_LOCAL_MODEL", "codellama:13b")


def ensure_session_dir() -> Path:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    return SESSION_DIR


def _session_file(session_id: str) -> Path:
    safe_id = session_id.replace("/", "_")
    return ensure_session_dir() / f"{safe_id}.json"


def query_ollama(prompt: str, *, model: Optional[str] = None) -> str:
    """Query a local Ollama model and return the generated text."""

    chosen_model = model or DEFAULT_MODEL
    process = subprocess.run(
        ["ollama", "run", chosen_model],
        input=prompt.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        error = process.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(
            "Ollama n'a pas répondu correctement. Assurez-vous que le service est lancé "
            f"et que le modèle '{chosen_model}' est disponible.\n{error}"
        )
    return process.stdout.decode("utf-8").strip()


def _iter_repository_files(repo_path: Path) -> Iterable[Path]:
    ignored_dirs = {".git", "node_modules", "__pycache__", ".venv", "env"}
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for name in files:
            yield Path(root) / name


def _extract_symbols(parser: Parser, source_code: bytes, interesting_types: Iterable[str]) -> List[str]:
    tree = parser.parse(source_code)
    root = tree.root_node
    symbols: List[str] = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type in interesting_types:
            text = source_code[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")
            first_line = text.splitlines()[0].strip()
            symbols.append(first_line)
        stack.extend(reversed(node.children))
    return symbols


def build_rag_context(repo_path: str) -> str:
    """Produce a lightweight summary of the repository using tree-sitter."""

    repository = Path(repo_path)
    if not repository.exists():
        return ""

    python_parser = Parser()
    python_parser.set_language(tspython.language())
    javascript_parser = Parser()
    javascript_parser.set_language(tsjavascript.language())

    interesting: List[str] = []
    file_count = 0
    for path in _iter_repository_files(repository):
        suffix = path.suffix
        if suffix not in {".py", ".js", ".ts", ".tsx"}:
            continue
        file_count += 1
        if file_count > 30:
            break
        try:
            source = path.read_bytes()
        except OSError:
            continue
        if suffix == ".py":
            symbols = _extract_symbols(
                python_parser,
                source,
                ["function_definition", "class_definition"],
            )
        else:
            symbols = _extract_symbols(
                javascript_parser,
                source,
                ["function_declaration", "class_declaration", "method_definition"],
            )
        if not symbols:
            preview = source.decode("utf-8", errors="ignore").splitlines()[:5]
            symbols = [line.strip() for line in preview if line.strip()]
        header = f"Fichier: {path.relative_to(repository)}"
        interesting.append(header)
        interesting.extend(f" - {symbol}" for symbol in symbols[:8])

    summary = "\n".join(interesting)
    return textwrap.dedent(
        f"""
        Contexte du dépôt ({repository.name}):
        {summary}
        """
    ).strip()


def generate_pr_diff(task: str, *, model: Optional[str] = None) -> str:
    """Ask the LLM to create a diff-like proposal for the given task."""

    prompt = textwrap.dedent(
        f"""
        Vous êtes un assistant qui rédige des propositions de pull request.
        Tâche: {task}
        Fournissez un diff Markdown commençant par ```diff.
        Incluez uniquement les fichiers essentiels et des explications concises.
        """
    ).strip()
    return query_ollama(prompt, model=model)


@dataclass
class CodexSession:
    session_id: str
    history: List[Dict[str, str]] = field(default_factory=list)
    repo_path: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def append(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})

    def to_dict(self) -> Dict[str, object]:
        return {
            "session_id": self.session_id,
            "history": self.history,
            "repo_path": self.repo_path,
            "created_at": self.created_at,
        }

    @classmethod
    def from_file(cls, session_id: str) -> "CodexSession":
        path = _session_file(session_id)
        if not path.exists():
            return cls(session_id=session_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            session_id=session_id,
            history=data.get("history", []),
            repo_path=data.get("repo_path"),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
        )

    def save(self) -> None:
        path = _session_file(self.session_id)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


class CodexEngine:
    """Core engine coordinating LLM interactions, RAG and sandbox."""

    def __init__(self, *, session_id: str = "default", repo_path: Optional[str] = None, model: Optional[str] = None):
        self.model = model or DEFAULT_MODEL
        self.session = CodexSession.from_file(session_id)
        if repo_path:
            self.session.repo_path = str(Path(repo_path).resolve())
            self.session.save()
        ensure_session_dir()
        self.sandbox = SandboxRunner()

    # Session helpers -------------------------------------------------
    @property
    def session_id(self) -> str:
        return self.session.session_id

    def set_repo(self, repo_path: str) -> None:
        self.session.repo_path = str(Path(repo_path).resolve())
        self.session.save()

    def get_history(self) -> List[Dict[str, str]]:
        return list(self.session.history)

    def _build_prompt(self, instruction: str, user_message: str) -> str:
        context = ""
        if self.session.repo_path:
            context = build_rag_context(self.session.repo_path)
        previous = "\n".join(
            f"{item['role']}: {item['content']}" for item in self.session.history[-8:]
        )
        return textwrap.dedent(
            f"""
            Vous êtes Codex Local, un assistant de développement fonctionnant entièrement hors-ligne.
            Instruction: {instruction}
            Contexte:
            {context}

            Historique récent:
            {previous}

            Utilisateur:
            {user_message}
            """
        ).strip()

    def _query_llm(self, instruction: str, user_message: str) -> str:
        prompt = self._build_prompt(instruction, user_message)
        return query_ollama(prompt, model=self.model)

    def _record_exchange(self, user_message: str, assistant_message: str) -> None:
        self.session.append("user", user_message)
        self.session.append("assistant", assistant_message)
        self.session.save()

    # Public API ------------------------------------------------------
    def ask(self, question: str) -> str:
        response = self._query_llm("Réponds à la question de l'utilisateur.", question)
        self._record_exchange(question, response)
        return response

    def plan(self, goal: str) -> str:
        instruction = "Établis un plan structuré et hiérarchisé pour accomplir l'objectif."  # noqa: E501
        response = self._query_llm(instruction, goal)
        self._record_exchange(f"/plan {goal}", response)
        return response

    def pr(self, summary: str) -> str:
        response = generate_pr_diff(summary, model=self.model)
        self.session.append("user", f"/pr {summary}")
        self.session.append("assistant", response)
        self.session.save()
        return response

    def run(self, target: str) -> SandboxResult:
        result = self.sandbox.run(target)
        log = textwrap.dedent(
            f"""
            /run {target}
            → code: {result.returncode}
            stdout:\n{result.stdout}
            stderr:\n{result.stderr}
            """
        ).strip()
        self.session.append("system", log)
        self.session.save()
        return result

    def handle_user_input(self, message: str) -> str:
        if message.startswith("/plan"):
            goal = message[len("/plan"):].strip()
            return self.plan(goal)
        if message.startswith("/ask"):
            query = message[len("/ask"):].strip()
            return self.ask(query)
        if message.startswith("/pr"):
            task = message[len("/pr"):].strip()
            return self.pr(task)
        if message.startswith("/run"):
            target = message[len("/run"):].strip()
            result = self.run(target)
            return textwrap.dedent(
                f"""
                Exécution terminée (code {result.returncode}).
                stdout:\n{result.stdout}
                stderr:\n{result.stderr}
                """
            ).strip()
        return self.ask(message)
