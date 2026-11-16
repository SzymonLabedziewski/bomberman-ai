# Sprawdza, czy w repozytorium są modele Q, wyniki eksperymentów i wykresy (Windows).
#
#   powershell -ExecutionPolicy Bypass -File docs\import_artifacts.ps1 [-Setup] [-Analyze] [-TrainIfMissing] [-Test] [-Workers N]
#
# Pełny trening i benchmark wygodniej uruchamiać w WSL (docs/run_full_benchmark.sh).

param(
    [switch]$Setup,
    [switch]$Analyze,
    [switch]$TrainIfMissing,
    [switch]$Test,
    [int]$Workers = 0
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$script:missing = $false
function Test-Files([string[]]$paths) {
    foreach ($f in $paths) {
        if (Test-Path $f) {
            Write-Host "  [OK]   $f" -ForegroundColor Green
        } else {
            Write-Host "  [BRAK] $f" -ForegroundColor Yellow
            $script:missing = $true
        }
    }
}

$py = $null
foreach ($c in @("py -3.12", "py -3", "python")) {
    try {
        $null = Invoke-Expression "$c --version" 2>$null
        $py = $c
        break
    } catch { }
}
if (-not $py) {
    throw "Nie znaleziono Pythona. Zainstaluj 3.12 i dodaj go do PATH."
}

if ($Setup) {
    if (-not (Test-Path .venv)) {
        Invoke-Expression "$py -m venv .venv"
    }
    & .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
} elseif (Test-Path .\.venv\Scripts\Activate.ps1) {
    & .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "Brak .venv: uruchom z -Setup."
}

$models = @(
    "bomberman\ai\models\q_pure.json", "bomberman\ai\models\q_pure.train.meta.json",
    "bomberman\ai\models\q_pure_physics.json", "bomberman\ai\models\q_pure_physics.train.meta.json"
)
Write-Host "Modele:"
Test-Files $models
if ($script:missing -and $TrainIfMissing) {
    if ($Workers -le 0) { $Workers = [Environment]::ProcessorCount }
    python -m bomberman train --episodes 15000 --workers $Workers --opponent montecarlo --out bomberman/ai/models/q_pure.json
    python -m bomberman train --episodes 20000 --workers $Workers --opponent montecarlo --physics --no-obstacles --out bomberman/ai/models/q_pure_physics.json
    $script:missing = $false
    Test-Files $models
}

Write-Host "Wyniki:"
foreach ($e in @("E1", "E1_obs", "E2", "E2_obs", "E4", "E5")) {
    Test-Files @("results\$e.csv", "results\$e.meta.json")
}
Test-Files @("results\ai_cost_ledger.json", "results\tables.md", "results\summary.json")

Write-Host "Wykresy:"
$plots = @(
    "E1_matchups", "E1_obs_matchups", "E2_matchups", "E2_obs_matchups",
    "E1_E2_winrate", "E1_E2_escape", "E1_E2_suicides",
    "E1_vs_E1_obs_winrate", "E1_vs_E1_obs_escape", "E1_vs_E1_obs_cost",
    "E2_vs_E2_obs_winrate", "E2_vs_E2_obs_escape", "E2_vs_E2_obs_cost",
    "all4_variants_winrate", "all4_variants_escape", "all4_variants_suicides", "all4_variants_cost",
    "E4_grid", "E5_all", "E5_escapable", "E6_winrate", "E6_cost", "bot_efficiency_cost"
)
Test-Files ($plots | ForEach-Object { "results\plots\$_.png" })

if ($Analyze) {
    python -m bomberman analyze --out results
}
if ($Test) {
    python -m pytest -q
}

if ($script:missing) {
    Write-Host "Czegoś brakuje. Modele: -TrainIfMissing albo docs/train_pure_q.sh (WSL)." -ForegroundColor Yellow
    exit 1
}
Write-Host "Wszystkie artefakty są na miejscu." -ForegroundColor Green
