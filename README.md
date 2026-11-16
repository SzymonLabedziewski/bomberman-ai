# Bomberman AI

Boty grają w Bombermana na małej siatce. Są trzy rodziny decydentów:

- **Losowe** - `random`, `randomsafe` (baseline).
- **Algorytmiczne** - `planner` (BFS po stanach pole x tick), `montecarlo` (krótkie symulacje).
- **AI (RL)** - `qlearner` (tabular Q-learning: trening offline, w meczu odczyt `Q(s,a)`).

Każda decyzja zapisuje telemetrię (czas, ops, RSS) - widać koszt "gotowego" searchu vs koszt nauczonego AI.

Rozszerzenia:

- **fizyka**: kopanie i ślizg bomb z tarciem, zderzenia z restytucją i zachowaniem pędu, odrzut po wybuchu, ruchome przeszkody;
- **silnik gry Godot 4**: gra na żywo (także człowiek kontra bot), nakładki, koszty decyzji, powtórki, ekran wyników i turniej na żywo.

Cała logika gry, fizyka, boty i eksperymenty są w Pythonie. Godot tylko rysuje stan i wysyła wejście gracza przez WebSocket.

Dokumenty: [zasady gry i fizyki](docs/zasady.md), [protokół Python <-> Godot](docs/protokol.md),
[Q-learning - wnioski i metryki](docs/qlearning.md), [sprawozdanie](report/sprawozdanie.md), [prezentacja](report/prezentacja.md).

## Wymagania

| Narzędzie | Wersja | Do czego |
|---|---|---|
| Python | 3.12 | silnik, boty, eksperymenty, serwer |
| Godot | 4.7.2 Standard (nie .NET) | wizualizacja i gra na żywo (opcjonalnie) |
| pandoc + xelatex | dowolna aktualna | tylko do zbudowania PDF ze sprawozdania |

Biblioteki Pythona (`requirements.txt`, wersje przypięte): `websockets`, `pandas`, `matplotlib`, `pytest`, `psutil`.
Rdzeń gry i boty (poza pomiarem RSS) korzystają z biblioteki standardowej.
Nie trzeba pobierać żadnych danych: wszystkie gry i sytuacje testowe generuje symulator z seedów zapisanych w `configs/experiments/`.

## Instalacja od zera

### Windows (PowerShell)

1. Zainstaluj Pythona 3.12 z [python.org](https://www.python.org/downloads/) (zaznacz "Add python.exe to PATH").
2. Pobierz Godot 4.7.2 Standard z [godotengine.org](https://godotengine.org/download/archive/4.7.2-stable/) i rozpakuj (to jeden plik exe, bez instalacji).
3. W PowerShellu:

```powershell
git clone https://github.com/SzymonLabedziewski/bomberman-ai.git
cd bomberman-ai
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest
```

Jeśli PowerShell nie pozwala aktywować środowiska, wykonaj raz
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` i spróbuj ponownie.

### Linux, macOS albo WSL

```bash
git clone https://github.com/SzymonLabedziewski/bomberman-ai.git
cd bomberman-ai
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest
```

Testy (111) trwają kilka sekund. Sprawdzają zasady gry, fizykę (wzory na drogę hamowania, zachowanie pędu
i energii, odbicia, odrzut), przewidywanie zagrożeń, boty, Q-learning, metryki i serwer.

## Uruchomienie

### Trening Q-learning (AI)

```powershell
python -m bomberman train --episodes 15000 --opponent montecarlo --out bomberman/ai/models/q_pure.json
python -m bomberman train --episodes 20000 --opponent montecarlo --physics --out bomberman/ai/models/q_pure_physics.json
```

Zapisuje tablicę Q oraz `*.train.meta.json` (czas treningu, peak RSS, winrate ewaluacji) - koszt **utworzenia** AI.
Preferowane tablice w grze: `bomberman/ai/models/q_pure.json` (bez fizyki) oraz `bomberman/ai/models/q_pure_physics.json` (z fizyką).

### Gra w terminalu (bez Godota)

```powershell
python -m bomberman play --p1 planner --p2 montecarlo --delay 0.2
python -m bomberman play --p1 qlearner --p2 randomsafe --stats
python -m bomberman play --p1 planner --p2 montecarlo --physics --seed 3 --save-replay
```

- Boty: `random`, `randomsafe`, `planner`, `montecarlo`, `qlearner` (fizykę włącza `--physics`).
- `--stats` wypisuje średni czas decyzji, ops i RSS (bez animacji).
- Fizyka: `--physics` włącza wszystko, a `--kick`, `--knockback` i `--obstacles` pojedyncze elementy.
- `--save-replay [PLIK]` zapisuje powtórkę do odtworzenia w Godocie (domyślnie w `results/replays/`).

### Gra w Godocie

1. Uruchom serwer i zostaw otwarte okno terminala:

   ```powershell
   python -m bomberman serve
   ```

2. Otwórz Godota, wybierz **Import**, wskaż `godot/project.godot` i uruchom projekt klawiszem **F5**.
   Za pierwszym razem Godot importuje pliki (kilka sekund).
3. W menu wybierz graczy (człowiek albo bot), ziarno planszy, prędkość i elementy fizyki, a potem kliknij **Start**.

Bez serwera działa odtwarzanie powtórek (przykładowa powtórka jest w `godot/mock/replay.json`) i ekran wyników
czytający `results/summary.json`.

Sterowanie:

| Klawisz | Działanie |
|---|---|
| strzałki albo WSAD, spacja | ruch i bomba (jeden człowiek) |
| A: WSAD + spacja, B: strzałki + Enter | dwóch ludzi przy jednej klawiaturze |
| P (albo spacja, gdy nie gra człowiek) | pauza |
| N albo `.` | jeden tick do przodu; w powtórce także strzałki w lewo i w prawo |
| `+` / `-` | prędkość |
| 1 / 2 | nakładki: mapa zagrożeń (za ile ticków pole będzie w ogniu) i plany Plannera |
| Esc | powrót do menu |

Panel z prawej strony pokazuje akcję i tryb każdego bota (np. ucieczka, atak, podchodzenie) oraz oceny akcji Monte Carlo.

Ekran **Wyniki eksperymentów i turniej** pokazuje wykresy z `results/summary.json` (z przedziałami ufności)
i pozwala uruchomić na serwerze turniej dwóch botów z podglądem wyników na żywo.

Godot można też uruchomić z argumentami (po `--`), np. do demo albo testów bez okna:

```powershell
godot --path godot -- --live=human,planner --physics --tps=6
godot --path godot -- --replay=../results/replays/planner_vs_montecarlo_seed3_fizyka.json
godot --path godot -- --results --chart=E1_E2_winrate
godot --headless --path godot -- --live=planner,montecarlo --tps=30 --autoquit
```

## Import artefaktów (modele, wyniki, wykresy)

Po sklonowaniu albo po ściągnięciu PR sprawdź, czy są wszystkie wygenerowane rzeczy
(modele Q, CSV, `tables.md`, PNG, `summary.json`):

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File docs\import_artifacts.ps1 -Setup -Analyze -Test
```

```bash
# Linux / WSL
bash docs/import_artifacts.sh --setup --analyze --test
```

Skrypt wypisuje inwentarz i oznaczy `[BRAK]`, jeśli czegoś nie ma. Brakujące modele:
`bash docs/train_pure_q.sh`. Pełny benchmark: `bash docs/run_full_benchmark.sh`
(oraz `docs/run_obstacles_experiments.sh` dla wariantów z przeszkodami).

## Odtworzenie wyników

Jedno polecenie uruchamia wszystkie eksperymenty (E1, E2, E4-E6), liczy statystyki, rysuje wykresy i zapisuje powtórki demonstracyjne:

```powershell
python -m bomberman reproduce
```

- Czas: około 25 minut na 4 wątkach (laptop z Intel Core i7-6600U). Liczbę procesów zmienia `--workers N`.
- `python -m bomberman reproduce --quick` robi to samo na 10% gier (około 2,5 minuty) i zapisuje wyniki w `results/quick/`.
- Wyniki trafiają do `results/`:
  - `E1.csv` ... `E6.csv` (jeden wiersz na gracza w grze albo na sytuację testową), `E*.meta.json` oraz `ai_cost_ledger.json`;
  - `plots/*.png` (wykresy do sprawozdania);
  - `tables.md` (tabele do sprawozdania);
  - `summary.json` (dane dla ekranu wyników w Godocie);
  - `replays/` (powtórki demonstracyjne).
- Pojedynczy eksperyment i sama analiza:

  ```powershell
  python -m bomberman experiment configs/experiments/E4.json --workers 4 --scale 0.5 --out results/tmp
  python -m bomberman analyze --out results/tmp
  ```

Seedy są zapisane w konfiguracjach, a symulacja jest deterministyczna, więc wyniki (poza czasem decyzji) są
powtarzalne co do gry. Czas decyzji zależy od komputera i od liczby równolegle działających procesów.

| Eksperyment | Co sprawdza |
|---|---|
| E1 | turniej 5 botów (w tym Q-Learning) bez fizyki, ~200 gier/parę, limit 200 ticków |
| E1_obs | jak E1, ale z ruchomymi przeszkodami (bez kopania/odrzutu) |
| E2 | ten sam turniej z fizyką (kopanie + odrzut, **bez** przeszkód) |
| E2_obs | jak E2 + ruchome przeszkody |
| E4 | Monte Carlo z K ∈ {10, 30, 100} i D ∈ {4, 8, 12} przeciw Plannerowi |
| E5 | ucieczka z 500 sytuacji x 4 warianty środowiska (macierz fizyka x przeszkody) |
| E6 | Q-Learning vs RandomSafe / Planner / MonteCarlo (wyodrębnione z turniejów) + koszty |

## Konfiguracja

- `configs/default.json`: rozmiar planszy, zapalnik, promień wybuchu, limit ticków i wszystkie parametry fizyki
  (prędkość kopnięcia, tarcie, restytucja, masy, impuls odrzutu, prędkość przeszkód).
- `configs/experiments/E*.json`: boty, liczba gier, seedy i warianty każdego eksperymentu.
- Inny plik konfiguracji gry: `python -m bomberman play --config moja.json`.

## Struktura repozytorium

```text
bomberman/
  __main__.py      CLI: play | serve | train | experiment | analyze | reproduce
  engine/          stan gry, plansza z seeda, zasady (step), fizyka, zapis do JSON, podgląd ASCII
  ai/              predykcja, Planner, Monte Carlo, Q-learning (`qlearner`), telemetria, models/
  experiments/     zadania i równoległe uruchamianie, metryki, scenariusze ucieczki, analiza
  server.py        serwer WebSocket dla Godota
  match.py         wspólne nagrywanie gier i dane dla nakładek
configs/           default.json i konfiguracje eksperymentów (E1, E2, E4-E6)
tests/             testy pytest
godot/             projekt Godota: scenes/ (Menu, Game, Results), scripts/, mock/replay.json
results/           wyniki eksperymentów, wykresy, summary.json, ai_cost_ledger.json, powtórki
docs/              jak działa kod (jak_dziala.md), zasady gry i fizyki, protokół, Q-learning
report/            sprawozdanie i prezentacja
```

## Sprawozdanie i prezentacja w PDF

Gotowe pliki to `report/sprawozdanie.pdf` i `report/prezentacja.pdf`. Po zmianie tekstu albo wyników
(wymaga pandoc, xelatex i fontów DejaVu; na Windows najprościej w WSL):

```bash
cd report
pandoc sprawozdanie.md -o sprawozdanie.pdf --pdf-engine=xelatex --resource-path=.:..
pandoc prezentacja.md -t beamer -o prezentacja.pdf --pdf-engine=xelatex --resource-path=.:..
python rysunki/architektura.py   # tylko po zmianie rysunku architektury
```

## Praca zespołowa

- Dostęp do repozytorium dla współpracownika (właściciel repozytorium, GitHub CLI):
  `gh api -X PUT repos/SzymonLabedziewski/bomberman-ai/collaborators/LOGIN -f permission=push`.
- Każda zmiana na osobnej gałęzi `feature/...` i przez Pull Request; scalamy po przejściu `python -m pytest`.
- Pliki `*.gd.uid` w `godot/scripts/` należą do repozytorium (Godot zapisuje w nich identyfikatory skryptów).
  Folder `godot/.godot/` to cache importu i jest ignorowany.
- Zmiana zasad gry wymaga zmiany `docs/zasady.md` i testów.

## Rozwiązywanie problemów

- **Menu Godota pokazuje "brak połączenia"**: serwer nie działa albo port 8765 jest zajęty
  (`python -m bomberman serve --port 8766` wymaga tej samej zmiany w `godot/scripts/net.gd`).
- **`py -3.12` nie działa**: Python 3.12 nie jest zainstalowany albo nie ma go w PATH; sprawdź `py -0`.
- **Eksperymenty trwają za długo**: użyj `--quick` albo `--scale 0.25`, ewentualnie mniejszej liczby gier w `configs/experiments/`.
