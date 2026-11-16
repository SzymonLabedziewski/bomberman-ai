#!/usr/bin/env bash
# Sprawdza, czy w repozytorium są modele Q, wyniki eksperymentów i wykresy.
#
#   bash docs/import_artifacts.sh [--setup] [--analyze] [--train-if-missing] [--test] [--workers N]
#
#   --setup             tworzy .venv (jeśli go nie ma) i instaluje requirements.txt
#   --analyze           odtwarza tables.md, wykresy i summary.json z plików CSV
#   --train-if-missing  trenuje brakujące modele (docs/train_pure_q.sh)
#   --test              uruchamia pytest
#   --workers N         liczba procesów treningu (domyślnie liczba rdzeni)

set -euo pipefail
cd "$(dirname "$0")/.."

DO_SETUP=0
DO_ANALYZE=0
DO_TRAIN=0
DO_TEST=0
WORKERS="$(nproc 2>/dev/null || echo 2)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --setup) DO_SETUP=1; shift ;;
    --analyze) DO_ANALYZE=1; shift ;;
    --train-if-missing) DO_TRAIN=1; shift ;;
    --test) DO_TEST=1; shift ;;
    --workers) WORKERS="$2"; shift 2 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "Nieznana opcja: $1 (użyj --help)"; exit 1 ;;
  esac
done

MISSING=0
check() {
  for f in "$@"; do
    if [[ -f "$f" ]]; then
      echo "  [OK]   $f"
    else
      echo "  [BRAK] $f"
      MISSING=1
    fi
  done
}

if [[ "$DO_SETUP" -eq 1 ]]; then
  if [[ ! -d .venv ]]; then
    if command -v python3.12 >/dev/null 2>&1; then python3.12 -m venv .venv; else python3 -m venv .venv; fi
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -q -r requirements.txt
elif [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  echo "Brak .venv: uruchom z --setup albo aktywuj własne środowisko."
fi

echo "Modele:"
MODELS=(
  bomberman/ai/models/q_pure.json bomberman/ai/models/q_pure.train.meta.json
  bomberman/ai/models/q_pure_physics.json bomberman/ai/models/q_pure_physics.train.meta.json
)
check "${MODELS[@]}"
if [[ "$MISSING" -eq 1 && "$DO_TRAIN" -eq 1 ]]; then
  WORKERS="$WORKERS" bash docs/train_pure_q.sh
  MISSING=0
  check "${MODELS[@]}"
fi

echo "Wyniki:"
for e in E1 E1_obs E2 E2_obs E4 E5; do
  check "results/$e.csv" "results/$e.meta.json"
done
check results/ai_cost_ledger.json results/tables.md results/summary.json

echo "Wykresy:"
for name in \
  E1_matchups E1_obs_matchups E2_matchups E2_obs_matchups \
  E1_E2_winrate E1_E2_escape E1_E2_suicides \
  E1_vs_E1_obs_winrate E1_vs_E1_obs_escape E1_vs_E1_obs_cost \
  E2_vs_E2_obs_winrate E2_vs_E2_obs_escape E2_vs_E2_obs_cost \
  all4_variants_winrate all4_variants_escape all4_variants_suicides all4_variants_cost \
  E4_grid E5_all E5_escapable E6_winrate E6_cost bot_efficiency_cost
do
  check "results/plots/$name.png"
done

if [[ "$DO_ANALYZE" -eq 1 ]]; then
  python -m bomberman analyze --out results
fi
if [[ "$DO_TEST" -eq 1 ]]; then
  python -m pytest -q
fi

if [[ "$MISSING" -eq 0 ]]; then
  echo "Wszystkie artefakty są na miejscu."
else
  echo "Czegoś brakuje. Modele: bash docs/train_pure_q.sh,"
  echo "turnieje: bash docs/run_full_benchmark.sh --skip-train, przeszkody: bash docs/run_obstacles_experiments.sh"
  exit 1
fi
