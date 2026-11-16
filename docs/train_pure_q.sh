#!/usr/bin/env bash
# Trening obu tablic Q: bez fizyki oraz z kopaniem i odrzutem (bez ruchomych przeszkód).
#
#   bash docs/train_pure_q.sh
#
# Zmienne: WORKERS (domyślnie liczba rdzeni), EP_NO_PHYS (15000), EP_PHYS (20000).

set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

WORKERS="${WORKERS:-$(nproc)}"
EP_NO_PHYS="${EP_NO_PHYS:-15000}"
EP_PHYS="${EP_PHYS:-20000}"

echo "q_pure.json: $EP_NO_PHYS epizodów, workers=$WORKERS"
python -m bomberman train --episodes "$EP_NO_PHYS" --workers "$WORKERS" --opponent montecarlo \
  --out bomberman/ai/models/q_pure.json

echo "q_pure_physics.json: $EP_PHYS epizodów, workers=$WORKERS"
python -m bomberman train --episodes "$EP_PHYS" --workers "$WORKERS" --opponent montecarlo \
  --physics --no-obstacles --out bomberman/ai/models/q_pure_physics.json
