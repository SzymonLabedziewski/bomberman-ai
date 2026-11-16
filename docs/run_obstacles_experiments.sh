#!/usr/bin/env bash
# Dogrywa tylko eksperymenty z ruchomymi przeszkodami (E1_obs, E2_obs) oraz E5 i odświeża analizę.
# Istniejące wyniki E1, E2 i E4 zostają, bo są potrzebne do porównań.
#
#   bash docs/run_obstacles_experiments.sh [--scale 1.0] [--workers N]

set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

WORKERS="${WORKERS:-$(nproc)}"
SCALE="${SCALE:-1.0}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scale) SCALE="$2"; shift 2 ;;
    --workers) WORKERS="$2"; shift 2 ;;
    *) echo "Nieznana opcja: $1 (dostępne: --scale, --workers)"; exit 1 ;;
  esac
done

mkdir -p results/plots
LOG_FILE="results/benchmark_obstacles.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

T_START=$(date +%s)
for e in E1_obs E2_obs E5; do
  log "Eksperyment $e (workers=$WORKERS, scale=$SCALE)"
  python -m bomberman experiment "configs/experiments/$e.json" --workers "$WORKERS" --scale "$SCALE" \
    --out results 2>&1 | tee -a "$LOG_FILE"
done
log "Analiza wyników"
python -m bomberman analyze --out results 2>&1 | tee -a "$LOG_FILE"
log "Koniec po $(( ($(date +%s) - T_START) / 60 )) min."
