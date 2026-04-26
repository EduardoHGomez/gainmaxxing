#!/usr/bin/env bash
# One-shot setup for a fresh Hostinger VPS (Ubuntu 22.04/24.04).
# Idempotent — safe to re-run.
#
# Usage (as a non-root user with sudo):
#   bash scripts/bootstrap.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "==> 1/5 system packages"
sudo apt update
sudo apt install -y curl git build-essential

echo "==> 2/5 install uv if missing"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  # Persist for future shells.
  if ! grep -q 'HOME/.local/bin' ~/.bashrc 2>/dev/null; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
  fi
fi
export PATH="$HOME/.local/bin:$PATH"
uv --version

echo "==> 3/5 install project deps into .venv"
uv sync

echo "==> 4/5 .env sanity check"
if [ ! -f .env ]; then
  echo "  ERROR: .env not found. Copy from .env.example and fill in keys, then re-run." >&2
  exit 1
fi
for key in OPENAI_API_KEY ANTHROPIC_API_KEY SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY; do
  if ! grep -q "^${key}=.\+" .env; then
    echo "  WARNING: ${key} appears empty in .env"
  fi
done
if [ ! -f skills/PROFILE.md ]; then
  echo "  ERROR: skills/PROFILE.md not found. Copy from skills/PROFILE.example.md and fill in." >&2
  exit 1
fi

echo "==> 5/5 ready"
echo
echo "Run the server with:"
echo "  uv run uvicorn server.app:app --host 0.0.0.0 --port 8000 --reload"
echo
echo "Health check (in another shell):"
echo "  curl http://localhost:8000/health"
