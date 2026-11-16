#!/usr/bin/env bash
# Pełny benchmark: trening obu modeli Q, eksperymenty E1, E1_obs, E2, E2_obs, E4, E5 i analiza.
# Gdy modele są już wytrenowane, wystarczy --skip-train (same eksperymenty trwają ok. 45-90 min
# na 4 wątkach).
#
#   bash docs/run_full_benchmark.sh [--skip-train] [--only-train] [--scale 0.25] [--workers 4]
#
# Liczbę epizodów treningu można zmienić zmiennymi EP_NO_PHYS i EP_PHYS.

set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

WORKERS="$(nproc)"
SCALE="1.0"
DO_TRAIN=1
DO_EXPERIMENTS=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-train) DO_TRAIN=0; shift ;;
    --only-train) DO_EXPERIMENTS=0; shift ;;
    --scale) SCALE="$2"; shift 2 ;;
    --workers) WORKERS="$2"; shift 2 ;;
    *) echo "Nieznana opcja: $1 (dostępne: --skip-train, --only-train, --scale, --workers)"; exit 1 ;;
  esac
done

mkdir -p results/plots results/replays
LOG_FILE="results/benchmark_run.log"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log "Benchmark: workers=$WORKERS, scale=$SCALE"
if command -v lscpu >/dev/null 2>&1; then
  lscpu | grep -E "Model name|CPU\(s\)|Thread|Core" | tee -a "$LOG_FILE" || true
fi
T_START=$(date +%s)

if [[ "$DO_TRAIN" -eq 1 ]]; then
  log "Trening modeli Q"
  WORKERS="$WORKERS" bash docs/train_pure_q.sh 2>&1 | tee -a "$LOG_FILE"
fi

if [[ "$DO_EXPERIMENTS" -eq 1 ]]; then
  for e in E1 E1_obs E2 E2_obs E3 E4 E5 E6; do
    rm -f "results/$e.csv" "results/$e.meta.json"
  done
  rm -f results/plots/*.png
  for e in E1 E1_obs E2 E2_obs E4 E5; do
    log "Eksperyment $e"
    python -m bomberman experiment "configs/experiments/$e.json" --workers "$WORKERS" --scale "$SCALE" \
      --out results 2>&1 | tee -a "$LOG_FILE"
  done
  log "Analiza wyników"
  python -m bomberman analyze --out results 2>&1 | tee -a "$LOG_FILE"
fi

log "Koniec po $(( ($(date +%s) - T_START) / 60 )) min. Wyniki w results/, log w $LOG_FILE"
