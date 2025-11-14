from __future__ import annotations

import json
import os
import subprocess
from typing import Optional

import typer

from .engine import CodexEngine
from .git_utils import prepare_repository

app = typer.Typer(add_completion=False, help="Codex Local CLI")


def _build_engine(session_id: str, repo: Optional[str], model: Optional[str]) -> CodexEngine:
    repo_path = prepare_repository(repo) if repo else None
    return CodexEngine(
        session_id=session_id,
        repo_path=str(repo_path) if repo_path else None,
        model=model,
    )


@app.command()
def ask(
    question: str,
    repo: Optional[str] = typer.Option(None, help="Chemin ou URL du dépôt"),
    session_id: str = typer.Option("default"),
    model: Optional[str] = typer.Option(None),
) -> None:
    """Poser une question sur le dépôt."""

    engine = _build_engine(session_id, repo, model)
    typer.echo(engine.ask(question))


@app.command()
def plan(
    goal: str,
    repo: Optional[str] = typer.Option(None),
    session_id: str = typer.Option("default"),
    model: Optional[str] = typer.Option(None),
) -> None:
    """Générer un plan structuré."""

    engine = _build_engine(session_id, repo, model)
    typer.echo(engine.plan(goal))


@app.command()
def pr(
    summary: str,
    repo: Optional[str] = typer.Option(None),
    session_id: str = typer.Option("default"),
    model: Optional[str] = typer.Option(None),
) -> None:
    """Produire un diff de pull request."""

    engine = _build_engine(session_id, repo, model)
    typer.echo(engine.pr(summary))


@app.command()
def run(target: str, session_id: str = typer.Option("default")) -> None:
    """Exécuter une commande dans le sandbox."""

    engine = CodexEngine(session_id=session_id)
    result = engine.run(target)
    output = {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
        "duration": result.duration,
    }
    typer.echo(json.dumps(output, indent=2, ensure_ascii=False))


@app.command()
def serve(
    session_id: str = typer.Option("default"),
    repo: Optional[str] = typer.Option(None),
    model: Optional[str] = typer.Option(None),
) -> None:
    """Lancer l'interface Streamlit."""

    env = os.environ.copy()
    env["CODEX_SESSION_ID"] = session_id
    if repo:
        env["CODEX_REPO_PATH"] = str(prepare_repository(repo))
    if model:
        env["CODEX_LOCAL_MODEL"] = model
    subprocess.run(["streamlit", "run", "web/app.py"], check=True, env=env)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
