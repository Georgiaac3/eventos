#!/bin/sh
# Runs the Python API (:8000) and the Next.js frontend (:3000) together.
.venv/bin/uvicorn backend.app:app --reload --port 8000 &
API=$!
trap 'kill $API' EXIT INT TERM
npx next dev
