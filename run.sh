#!/bin/bash
set -e

ollama serve &
OLLAMA_PID=$!
sleep 2
ollama pull codellama:13b || true
streamlit run web/app.py

if ps -p $OLLAMA_PID > /dev/null 2>&1; then
  kill $OLLAMA_PID
fi
