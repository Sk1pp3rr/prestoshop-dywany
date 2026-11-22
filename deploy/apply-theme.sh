#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# deploy/apply-theme.sh
# Skrypt zgodnosciowy delegujacy do deploy/activate-theme.sh.
# Zgodnie z wymaganiem D1 modyfikacje realizowane sa wylacznie w motywie
# potomnym 'classic-fashion' (zakaz bezposredniej modyfikacji motywu 'classic').
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/activate-theme.sh" "$@"
