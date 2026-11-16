# Protokół Python <-> Godot

Serwer (`python -m bomberman serve`) nasłuchuje na `ws://127.0.0.1:8765`.
Każda wiadomość to jeden obiekt JSON wysłany jako ramka tekstowa WebSocket.
Godot nie liczy logiki gry: wysyła polecenia i wejście gracza, a rysuje stany przysłane przez Pythona.

## Godot -> Python

| `type` | Pola | Znaczenie |
|---|---|---|
| `start` | `p1`, `p2` (nazwy botów albo `human`), `physics` (bool albo obiekt z flagami `kick`, `knockback`, `moving_obstacles`), `seed`, `tps` | nowa gra na żywo |
| `input` | `action` (`UP`, `DOWN`, `LEFT`, `RIGHT`, `STAY`, `BOMB`), opcjonalnie `player` | wejście gracza; ruch trwa, dopóki klient nie wyśle `STAY`, `BOMB` działa raz |
| `control` | `cmd`: `pause`, `resume`, `step`, `speed` (z `value` = ticki na sekundę), `stop` | sterowanie grą |
| `get_results` | - | prośba o `results/summary.json` |
| `list_replays` | - | lista zapisanych powtórek z `results/replays/` |
| `get_replay` | `name` | pełna powtórka |
| `tournament` | `p1`, `p2`, `games`, `physics`, `seed` | turniej na żywo bez rysowania gier |

## Python -> Godot

| `type` | Pola | Znaczenie |
|---|---|---|
| `hello` | `bots`, `version` | po połączeniu: lista dostępnych botów |
| `state` | patrz niżej | stan po każdym ticku |
| `game_over` | `winner`, `ticks`, `stats` | koniec gry na żywo |
| `results` | `summary` (obiekt albo `null`) | zawartość `summary.json` |
| `replays` | `items` (lista nazw) | lista powtórek |
| `replay` | `name`, `data` | powtórka: `{"meta": {...}, "frames": [state, ...]}` |
| `tournament_progress` | `done`, `total`, `stats` | postęp turnieju |
| `error` | `message` | błąd polecenia |

## Wiadomość `state`

```json
{
  "type": "state", "tick": 17, "width": 9, "height": 9,
  "grid": ["#########", "#..+.+..#", "..."],
  "players": [{"id": 0, "x": 1.0, "y": 3.0, "vx": 0.0, "vy": 0.0, "alive": true, "stunned": false, "name": "Planner"}],
  "bombs": [{"id": 4, "x": 4.6, "y": 1.0, "vx": 0.9, "vy": 0.0, "timer": 2, "owner": 1, "radius": 2}],
  "obstacles": [{"id": 0, "x": 4.5, "y": 3.0, "vx": 0.5, "vy": 0.0}],
  "flames": [[3, 1], [4, 1]],
  "events": [{"type": "kick", "x": 4, "y": 1, "player": 1}],
  "done": false, "winner": null,
  "debug": {
    "danger": {"4,1": 2, "5,1": 2},
    "plans": {"0": [[1, 3], [1, 4]]},
    "values": {"1": {"STAY": 0.1, "BOMB": -0.4}},
    "modes": {"0": "escape"}
  }
}
```

- `grid`: `#` ściana, `+` skrzynia, `.` wolne pole.
- `danger`: pole `"x,y"` -> za ile ticków będzie w nim ogień (predykcja `predict()`).
- `plans`: zaplanowana ścieżka Bota A (kolejne pola, jedno na tick).
- `values`: średnie oceny akcji Bota B z symulacji Monte Carlo.
- Typy zdarzeń w `events`: `bomb`, `kick`, `explosion`, `box`, `knock`, `push`, `collision`, `death`.
  `collision` ma pozycję ciała w chwili kontaktu (`x`, `y` mogą być ułamkowe), `with`
  (`static`, `anchor`, `body`, `obstacle`) oraz `bomb` albo `player`.
