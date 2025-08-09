#!/usr/bin/env bash
set -euo pipefail
export GEMINI_API_KEY=${GEMINI_API_KEY:-"REPLACE_ME"}
streamlit run app/streamlit_app.py
