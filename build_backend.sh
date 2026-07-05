#!/bin/bash
set -e

echo "Building Python Backend with PyInstaller..."

cd backend

# Use the virtual environment's pyinstaller
./.venv/bin/pyinstaller --name notebook-backend \
  --onefile \
  --clean \
  --distpath ../backend-dist \
  --hidden-import "passlib.handlers.bcrypt" \
  --hidden-import "sqlalchemy.dialects.sqlite" \
  --hidden-import "multipart" \
  --hidden-import "chromadb.telemetry.product.posthog" \
  --hidden-import "chromadb.api.segment" \
  main.py

echo "Backend build complete! Output is in backend-dist/"
