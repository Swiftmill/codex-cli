# Codex Local

[![Local](https://img.shields.io/badge/runtime-local-green.svg)](#)
[![Streamlit](https://img.shields.io/badge/ui-streamlit-orange.svg)](#)
[![Ollama](https://img.shields.io/badge/model-ollama-blue.svg)](#)

Codex Local est une expérience hors ligne qui combine un moteur CLI inspiré de `codex-cli` et une interface Streamlit reproduisant fidèlement [https://chatgpt.com/codex](https://chatgpt.com/codex). L'outil repose entièrement sur Ollama et des modèles open-source pour proposer un copilote local pour vos dépôts Git.

## Aperçu de l'interface

```
[ Codex ]                                    [Paramètres] [Docs] [PLUS]

           Qu'allons-nous coder maintenant ?

    ┌──────────────────────────────────────────────────────┐
    │ Posez une question avec /plan                        │
    └──────────────────────────────────────────────────────┘

    +  Swiftmill/codex-cli     main     1x     [micro] [↑]

    Tâches    Revues du code    Archiver
```

## Installation

```bash
git clone <votre-fork>/codex-local
cd codex-local
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Assurez-vous d'avoir [Ollama](https://ollama.com) installé et lancé en local.

## Lancement rapide

```bash
./run.sh
# L'interface web est disponible sur http://localhost:8501
```

## Commandes CLI

```bash
codex plan "ajouter auth"
codex ask "explique main.py"
codex run scripts/generate_docs.py
codex pr "corriger le bug de connexion"
codex serve
```

## Structure du projet

```
textcodex-local/
├── codex_cli/
│   ├── __init__.py
│   ├── __main__.py
│   ├── engine.py
│   ├── sandbox.py
│   └── git_utils.py
├── web/
│   └── app.py
├── requirements.txt
├── README.md
├── run.sh
└── codex_sessions/
```

## Capture d'écran (ASCII)

```
╔════════════════════════════════════════════════════════╗
║ Codex Local                                            ║
║ Qu'allons-nous coder maintenant ?                      ║
║ [Prompt Box : Posez une question avec /plan]           ║
║ Onglets : Tâches | Revues du code | Archiver           ║
╚════════════════════════════════════════════════════════╝
```

## Développement

- Le moteur CLI utilise `typer` pour proposer des commandes simples et extensibles.
- L'intégration RAG repose sur `tree-sitter` afin de résumer le dépôt actif.
- L'exécution sandboxée est assurée via `RestrictedPython` et un gestionnaire de processus à temps limité.
- L'interface Streamlit partage l'état avec la CLI via des fichiers JSON dans `codex_sessions/`.

## Licence

MIT
