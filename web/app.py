import os
import uuid
from pathlib import Path

import streamlit as st

from codex_cli.engine import CodexEngine
from codex_cli.git_utils import extract_zip, prepare_repository

st.set_page_config(layout="centered", page_title="Codex")

# Session initialisation ------------------------------------------------------

def _get_session_id() -> str:
    if "session_id" in st.session_state:
        return st.session_state["session_id"]
    env_id = os.environ.get("CODEX_SESSION_ID")
    session_id = env_id or str(uuid.uuid4())
    st.session_state["session_id"] = session_id
    return session_id


def _init_engine() -> CodexEngine:
    session_id = _get_session_id()
    repo_path = os.environ.get("CODEX_REPO_PATH")
    model = os.environ.get("CODEX_LOCAL_MODEL")
    engine = CodexEngine(session_id=session_id, repo_path=repo_path, model=model)
    st.session_state["engine"] = engine
    return engine


def get_engine() -> CodexEngine:
    engine = st.session_state.get("engine")
    if engine is None:
        engine = _init_engine()
    return engine


engine = get_engine()

# Sidebar actions -------------------------------------------------------------

st.sidebar.header("Projet")
current_repo = engine.session.repo_path if engine.session.repo_path else "Non défini"
st.sidebar.write(f"Dépôt courant : {current_repo}")

def _handle_zip_upload(data) -> None:
    uploads_dir = Path("codex_sessions/uploads")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    archive_path = uploads_dir / data.name
    archive_path.write_bytes(bytes(data.getbuffer()))
    repo_path = extract_zip(str(archive_path))
    engine.set_repo(str(repo_path))
    st.sidebar.success(f"Dépôt chargé depuis {archive_path.name}")


uploaded_repo = st.sidebar.file_uploader("Importer un dépôt (.zip)", type=["zip"], on_change=None)
if uploaded_repo is not None:
    _handle_zip_upload(uploaded_repo)

manual_repo = st.sidebar.text_input("Chemin local ou URL Git")
if st.sidebar.button("Charger le dépôt"):
    if manual_repo:
        repo_path = prepare_repository(manual_repo)
        engine.set_repo(str(repo_path))
        st.sidebar.success(f"Dépôt chargé: {repo_path}")
    else:
        st.sidebar.error("Veuillez fournir un chemin ou une URL valide")

# --- HEADER ---
col1, col2 = st.columns([1, 4])
with col1:
    st.markdown("### Codex")
with col2:
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.button("Paramètres")
    with c2:
        st.button("Docs")
    with c3:
        st.markdown(
            "<span style=\"background:red;color:white;padding:2px 6px;border-radius:4px;font-size:12px\">PLUS</span>",
            unsafe_allow_html=True,
        )

# --- TITRE ---
st.markdown("<h2 style='text-align:center'>Qu'allons-nous coder maintenant ?</h2>", unsafe_allow_html=True)

# --- CHAT HISTORY ---
for message in engine.get_history():
    role = message.get("role", "assistant")
    content = message.get("content", "")
    if role == "system":
        st.info(content)
        continue
    with st.chat_message("user" if role == "user" else "assistant"):
        st.markdown(content)

# --- INPUT ---
user_input = st.chat_input("Posez une question avec /plan")

# --- BARRE OUTILS ---
col_add, col_repo, col_branch, col_zoom, col_mic, col_send = st.columns([0.5, 2, 1, 0.5, 0.5, 0.5])
with col_add:
    st.button("+", key="add")
with col_repo:
    st.caption("Swiftmill/codex-cli")
with col_branch:
    st.caption("main")
with col_zoom:
    st.caption("1x")
with col_mic:
    st.button("🎤")
with col_send:
    st.button("↑")

# --- ONGLETS ---
tab1, tab2, tab3 = st.tabs(["Tâches", "Revues du code", "Archiver"])
with tab1:
    st.markdown("Historique des tâches")
with tab2:
    st.markdown("Revues en cours")
with tab3:
    st.markdown("Discussions archivées")

# --- CHAT LOGIQUE ---
if user_input:
    with st.chat_message("user"):
        st.write(user_input)
    response = engine.handle_user_input(user_input)
    with st.chat_message("assistant"):
        st.markdown(response)
