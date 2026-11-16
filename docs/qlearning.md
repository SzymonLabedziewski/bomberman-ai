# Q-Learning (AI) - wnioski z treningu i metryki

Ten dokument zbiera **empiryczne ustalenia**, których nie wolno pominąć przy ocenie
albo dalszym trenowaniu bota `qlearner`. Nie zastępuje sprawozdania - to notatka
techniczna do kodu i kolejnych eksperymentów.

## 1. Co mylące w metrykach

| Metryka | Wygląda dobrze gdy... | Faktycznie oznacza... |
|---|---|---|
| `final_eval_winrate` ~1.0 vs RandomSafe | agent "wygrywa" | często: **nie atakuje**, czeka aż słaby przeciwnik zginie / gra się urwie |
| `self_kill_rate` = 0 | "nie popełnia samobójstw" | często: **w ogóle nie stawia bomb** |
| Dużo epizodów / stanów w `q_*.json` | "dużo się nauczył" | tablica może kodować politykę **tchórza** (STAY / krążenie) |

**Wniosek:** sama wygrana przeciw RandomSafe **nie dowodzi**, że AI gra jak przeciwnik,
który chce Cię pokonać. Trzeba mierzyć też:

- odsetek gier z >=1 bombą (`bombs_placed`),
- win/draw/loss vs **Planner** i **MonteCarlo**,
- liczbę trybów `escape` vs `exploit` w telemetrii.

## 2. Dane z pomiarów (2026-10-26)

### Trening użytkownika (przed poprawką agresji)

```text
episodes=50000  workers=4  opponent=curriculum  physics=false
n_states=1054  wall~360 s  peak_RSS~18 MB
eval WR vs RandomSafe = 1.0
eval self-kill/gra = 0.0
```

### Szybki turniej kontrolny po tym treningu (20 gier / para, bez fizyki)

| Przeciwnik | W-R-P | Obserwacja zachowania |
|---|---|---|
| RandomSafe | 20-0-0 | wygrywa bez ataku |
| Planner | 0-20-0 | same remisy |
| MonteCarlo | 1-19-0 | prawie same remisy |
| sample seed 11 | - | RIGHT/LEFT, **0 bomb**, 0x tryb escape |

### E6 (wcześniejsza tablica, `results/tables.md`)

| Para | bez fizyki | z fizyką |
|---|---|---|
| Q vs RandomSafe | ~57% WR | ~52% |
| Q vs Planner | **0%** | **0%** |
| Q vs MonteCarlo | **0%** | **0%** |

### Wcześniejszy trening (19k)

`train_self_kills~8316` przy 19k epizodach - w trakcie nauki dużo samobójstw;
ewaluacja z `safe_play` potem ukrywała problem (0 self-kill przy braku bomb).

## 3. Przyczyna (mechanizm)

1. Nagroda mocno premiowała **przeżycie**; vs RandomSafe optymalne było **nie bombować**.
2. Kara za śmierć od własnej bomby + filtr `safe_play` utrwalały "nie ruszaj BOMB".
3. Credit assignment: wybuch po 5 tickach - bez silnego shapingu Q nie łączy BOMB->ucieczka->kill.
4. Na wielu seedach bomba w narożniku **nie ma ucieczki** (promień 2 + skrzynie) - poprawny
   zakaz BOMB bywa mylony z "nigdy nie bombuj".

Ucieczka BFS przy `in_danger` (hybryda) chroni przed "postaw i stój", ale **nie uczy ataku**.

## 4. Co jest "prawdziwym AI" w tym projekcie

### Czysta polityka (domyślnie od 2026-10-27)

W grze i w ewaluacji treningu bot **`qlearner` wybiera akcję wyłącznie z tablicy Q**
(`argmax` / ε-greedy). **Bez** override `escape_path` i bez filtra `_safe_actions`.

- Flaga `safe_play=False` (domyślna) = czyste AI.
- `safe_play=True` = opcjonalna hybryda A/B (BFS przy ogniu) - nie używana w menu / eval.
- Nadal OK w RL: cechy `encode_state` i shaping nagrody w treningu (nauczyciel, nie search w runtime).

### Porównanie kosztów (trenowanie vs algorytm w grze)

| | Q (pure) | Planner / MonteCarlo |
|---|---|---|
| Koszt przed grą | trening: `wall_seconds`, `cpu_seconds_est`, `energy_wh_est` w meta + ledger | brak |
| Koszt na tick | niski `ops` (lookup Q) | wysoki `ops` / `wall_ms` (BFS / rollouts) |
| Energia (szacunek) | `cpu_s/3600 * 15 W` (trening) + ms decyzji x ta sama stała | tylko decyzje w meczu |

Ledger łączny: `results/ai_cost_ledger.json` (suma epizodów / Wh po kolejnych `train`).
Stała `assumed_cpu_watts = 15` - założenie laptopa, nie pomiar z gniazdka.

Sukces = wygrywa / grozi bomami vs człowiek i vs Planner **przy czystej Q**, nie tylko WR vs RandomSafe.

## 5. Trening agresywny (80k, 2026-10-26 wieczór) - **bez fizyki**

```text
physics=false   <- ważne: kick / knockback / przeszkody NIE były w tym treningu
episodes=80000  workers=4  opponent=aggressive  ~625 s
train_bombs=168172  n_states=1228
eval vs RandomSafe: WR=1.0  bomb_rate=0.1  self-kill=0
eval vs Planner:    WR=0.0  draw=0.25  loss=0.75  bomb_rate=1.0
```

Kontrola: vs Planner bombował za często "dla bombowania" (pusta mapa -> schowanie).
Po poprawce: `bomb_is_useful` - BOMB tylko gdy grozi przeciwnikowi albo niszczy skrzynie.

**Fizyka:** osobny trening `--physics` (cecha `physics` jest w kluczu stanu). Jedna tablica
wytrenowana tylko bez fizyki **nie** "dostosowuje się" magicznie do kopania/odrzutu/przeszkód.

```bash
# bez fizyki (selektywne bomby)
python -m bomberman train --episodes 60000 --workers $(nproc) --opponent aggressive

# z pełną fizyką -> osobna tablica
python -m bomberman train --episodes 60000 --workers $(nproc) --opponent aggressive \
  --physics --out bomberman/ai/models/q_physics.json
```

W grze w Godocie i w CLI (`play --physics`) rejestr botów (`bomberman/ai/registry.py`)
automatycznie wybiera tablicę odpowiadającą trybowi fizyki (`q_pure_physics.json` przy włączonej
fizyce oraz `q_pure.json` bez fizyki).

## 5b. Trening 60k + `bomb_is_useful` (2026-10-27) - bez i z fizyką

Po bramce `bomb_is_useful` (BOMB tylko gdy grozi przeciwnikowi albo niszczy skrzynie).
Oba biegi: `episodes=60000`, `workers=4`, `opponent=aggressive`, `seed=42`.

| | `q_default` (physics=false) | `q_physics` (physics=true) |
|---|---|---|
| wall / peak RSS | 585 s / 19.2 MB | 907 s / 19.4 MB |
| n_states | 2956 | 3273 |
| train_bombs | 121969 | 113185 |
| train W-D-L | 13255-2479-44266 | 14105-2883-43012 |
| train_self_kills | 45596 | 43930 |
| eval vs RandomSafe | WR=1.0, bomb_rate=0.25, self-kill=0 | WR=0.975, bomb_rate=0.55, self-kill=0.025 |
| eval vs Planner | WR=0, draw=0.96, loss=0.04, bomb_rate=1.0 | WR=0.1, draw=0.2, loss=0.7, bomb_rate=1.0, self-kill=0.34 |

Porównanie z §5 (80k, przed `bomb_is_useful`): bomb_rate vs RandomSafe wzrósł
(0.1 -> 0.25 / 0.55), bez fizyki vs Planner prawie same remisy zamiast przegranych,
z fizyką pierwsze realne wygrane vs Planner (WR 0.1) kosztem self-killów.

**Wniosek:** filtr bomby pomaga vs RandomSafe; vs Planner nadal słabo - remisy / self-kille
i ograniczenia bazowych botów (RandomSafe 1-tick "bezpieczeństwo", deadlock Planner<->Planner)
psują też jakość sygnału ewaluacji (todo punkt 2).

## 6. Survival upgrade + cechy fizyki (2026-10-27 wieczór)

### Faza 1 (resume, te same klucze + nowe nagrody)

Mocniejszy survival w `train.py`: `SELF_KILL=-2`, `DANGER_STAY=-0.8`,
`DEATH=-1.4`, `ESCAPE_MOVE_BONUS=+0.55`, curriculum Planner od 55% epizodów (4/6).
Cel: self-kill vs Planner w dół względem pure 100k (0.42 / 0.74).

```bash
bash docs/train_pure_q.sh   # albo ręcznie 80k resume x2, potem Faza 2
```

### Faza 2 (nowe cechy fizyki -> nowe pliki, wyniki z `results/console.txt`)

`encode_state` kończy się `|kick|knock|obstacle` (bez fizyki zawsze `0|0|0`).
Wyniki po 80k+80k (Faza 1) i 100k+120k (Faza 2) ujawniły jednak nadal obecne błędy zachowania:
- `q_pure` (100k, bez fizyki): vs RandomSafe `WR=0.9125, bomb_rate=0.525, self-kill=0.0875`, vs Planner `WR=0.0, draw=0.3, loss=0.7`.
- `q_pure_physics` (120k, z fizyką): vs RandomSafe `WR=0.7375, bomb_rate=0.8875, self-kill=0.225`, vs Planner `WR=0.1, draw=0.1, loss=0.8`.
- W grze bot potrafił oscylować między dwoma polami, cofać się z bezpiecznego pola w zasięg własnej bomby (gdyż `fire=0` nie mówiło, z którego kierunku jest bomba, a brak kary za wejście w ogień pozwalał "farmić" `ESCAPE_MOVE_BONUS=+0.55`), oraz grać biernie na starcie przy włączonej fizyce (bo dostawał `KILL_BONUS` i `WIN_REWARD` za samobójstwo przeciwnika).

### Faza 3 (kierunkowe cechy `escape_dir`/`nav_dir`/`dir_mask` + uszczelnienie nagród + trening vs MonteCarlo)

1. **Kierunkowe `encode_state` i kompresja zagrożeń:**
   - Dodano `escape_dir` (`0..5`), `nav_dir` (`0..4`, BFS po bezpiecznych polach) oraz `dir_safety_mask` (4-znakowy kod `0/1/2` dla `UP, DOWN, LEFT, RIGHT`).
   - Przy `fire > 0` cechy nawigacyjne są zerowane, co 60-krotnie redukuje liczbę stanów zagrożenia i przyspiesza naukę ucieczki.
2. **Anty-oscylacja i uszczelnienie `_step_reward`:**
   - `ENTER_DANGER_PENALTY = -0.75` (przewyższa `ESCAPE_MOVE_BONUS = +0.55`), `BACKTRACK_PENALTY = -0.06`, `KICK_ATTACK_BONUS = +0.45`, `PASSIVE_PENALTY = -0.60`.
   - Brak `KILL_BONUS` za samobójstwo przeciwnika (`by_self=True`) i kontrfaktyczna ocena wszystkich legalnych akcji przy pierwszych wizytach w stanie (eliminacja luk `Q = 0.0`).
3. **Trening przeciwko `MonteCarloBot` po obu stronach mapy (`seat 0` i `seat 1`):**
   - Domyślny `--opponent montecarlo` trenuje na `MonteCarloBot` (60%) + `self-play` (40%), wykluczając `random` i `planner`.
   - `RandomSafeBot` został uzupełniony o wielotickową ucieczkę przed własną bombą (`b.owner == me`), dzięki czemu nie popełnia samobójstw od własnych bomb.
   - **Wyniki po pełnym treningu `bash docs/train_pure_q.sh` (15k bez fizyki + 20k z fizyką):**
     - `q_pure` (bez fizyki, `stany=2455`, `czas=1303.88 s`, `21.73 Wh`):
       - vs `RandomSafe`: `WR=0.7625, draw=0.225, loss=0.0125, bomb_rate=1.0, self-kill=0.0125`
       - vs `Planner`: `WR=0.0, draw=0.9875, loss=0.0125, bomb_rate=1.0, self-kill=0.0125` (spadek porażek z `0.70` do `0.0125`!)
       - vs `MonteCarlo`: `WR=0.0875, draw=0.775, loss=0.1375, bomb_rate=1.0, self-kill=0.1625`
     - `q_pure_physics` (z fizyką, `stany=17662`, `czas=3601.43 s`, `60.02 Wh`):
       - vs `RandomSafe`: `WR=0.825, draw=0.125, loss=0.05, bomb_rate=1.0, self-kill=0.075`
       - vs `Planner`: `WR=0.20, draw=0.60, loss=0.20, bomb_rate=1.0, self-kill=0.10` (wzrost WR z `0.10` do `0.20`, spadek porażek z `0.80` do `0.20`!)
       - vs `MonteCarlo`: `WR=0.15, draw=0.5125, loss=0.3375, bomb_rate=1.0, self-kill=0.2125`

### Faza 4 (aktywne kopanie bomb `kick_score`, świadomość odrzutu `knockback` i anty-looping AI vs AI)

- Odblokowano kierunek kopania bomby przy `fire > 0` (`kick = 3`, `nav_dir` zachowuje kierunek kopnięcia), dodano kombo "postaw -> cofnij się o 1 pole -> kopnij" (`_can_setup_kick_attack`) oraz ocenę `kick_score` i `best_kick_action`.
- Rozszerzono cechę `knock` na 3 stany (`0` brak, `1` własne pole zagrożone odrzutem, `2` wróg w zasięgu odrzutu).
- Dodano detekcję kolizji czołowych i cykli wielokrokowych (`_edge_counts`, `_bomb_counts` resetowane po zniszczeniu skrzyni).
- Po treningu weryfikacyjnym Fazy 4 (`1500` epizodów bez fizyki i `2000` z fizyką):
  - `q_pure.json` (bez fizyki, `stany=1868`, `122.61 s`, `2.04 Wh`): vs `RandomSafe` `WR=0.875, loss=0.0, self-kill=0.0`; vs `Planner` `draw=1.0, loss=0.0, self-kill=0.0`; vs `MonteCarlo` `WR=0.15, draw=0.775, loss=0.075`.
  - `q_pure_physics.json` (z fizyką, `stany=9183`, `341.77 s`, `5.70 Wh`, `6198` kopnięć w treningu): vs `Planner` `WR=0.35, draw=0.50, loss=0.15, kicks/g=10.775`; vs `MonteCarlo` `WR=0.20, draw=0.275, kicks/g=7.225`.

Historia decyzji i wyników: [docs/ai_evolution.md](ai_evolution.md).

## 7. Artefakty

- Tablice w grze: `bomberman/ai/models/q_pure.json` (bez fizyki) oraz `bomberman/ai/models/q_pure_physics.json` (z fizyką)
- Metadane treningu: `bomberman/ai/models/*.train.meta.json`
- Ledger: `results/ai_cost_ledger.json`
- Skrypt: `docs/train_pure_q.sh`
- Ten plik + `docs/ai_evolution.md`

