# Ewolucja AI (Q-learning) - historia zmian do sprawozdania

Dokument zbiera **dlaczego** zmienialiśmy podejście, **co** było wcześniej,
**jaki** był efekt i **dokąd** zmierzamy. Uzupełnia `docs/qlearning.md` (metryki techniczne).

---

## 1. Punkt wyjścia: "AI wygrywa", ale nie atakuje

**Problem:** tabular Q vs RandomSafe dawał WR ~1.0 przy `bomb_rate ~0` i `self_kill = 0`.
Wyglądało na sukces; w praktyce agent **nie stawiał bomb** i czekał, aż słaby przeciwnik
zginie albo gra się urwie.

**Dlaczego tak:** nagroda mocno premiowała przeżycie; vs RandomSafe optymalne było
nie bombować. Filtr `safe_play` + BFS escape w grze **ukrywały** słabość polityki Q
(ewaluacja wyglądała bezpiecznie).

**Wniosek metryczny:** zawsze patrzeć na `bomb_rate`, WR vs **Planner**, nie tylko vs RandomSafe.

---

## 2. Agresja i `bomb_is_useful`

**Zmiana:** opponent `aggressive`, shaping za użyteczną bombę / karę za spam,
bramka `bomb_is_useful` (skrzynie lub groźba).

**Efekt (60k, eval jeszcze z hybrydą `safe_play`):**

| Model | vs RandomSafe | vs Planner |
|-------|---------------|------------|
| `q_default` | WR 1.0, bomb 0.25 | WR 0, draw 0.96 |
| `q_physics` | WR 0.975, bomb 0.55 | WR 0.1, loss 0.7 |

Agent zaczął bombować; vs Planner nadal słabo (remisy / self-kille przy fizyce).

**Boty bazowe:** poprawiono RandomSafe (bomba tylko z ucieczką), Planner approach
(contested + seat yield), Q hybrid escape - żeby ewaluacja nie była zafałszowana
błędami przeciwników (todo pkt 2).

---

## 3. Wymóg "100% AI" = czysta polityka w runtime

**Cel projektu / sprawozdania:** człowiek + algorytmy (Planner/MC/...) + AI, które
**w grze wybiera wyłącznie z tablicy Q** (bez BFS jako refleksu).

**Zmiana:** domyślnie `safe_play=False`; eval treningu też pure.
Zostaje: cechy stanu i shaping nagrody w **treningu** (nauczyciel, nie search w `act`).

**Dotrenowanie 100k x 2 (resume, pure eval):**

| Model | koszt (ten bieg) | vs RandomSafe | vs Planner |
|-------|------------------|---------------|------------|
| `q_default` | ~736 s wall, ~12.3 Wh | WR 0.96, bomb 0.26, sk 0.025 | WR 0, draw 0.49, loss 0.51, **sk 0.43** |
| `q_physics` | ~1377 s, ~22.9 Wh | WR 0.71, bomb 0.76, **sk 0.29** | WR 0.025, **sk 0.74** |

**Interpretacja:** czyste AI jest uczciwe metrycznie, ale **ginie od własnych bomb**
vs Planner / przy fizyce - tablica nie dostała wystarczającego sygnału "wyjdź z ognia",
a cechy nie opisywały kick/knock/przeszkód (tylko flaga `physics=0/1`).

Ledger łącznie (historia + pure): ~320k epizodów, ~60 Wh @ 15 W założenia.

---

## 4. Survival upgrade (Faza 1) - bez zmiany klucza stanu

**Cel:** przy **nadal czystej Q** nauczyć przeżycia i ruchu z zagrożenia.

**Zmiany w logice (nie w runtime search):**

- ostrzejsze kary: śmierć, self-kill, STAY w ogniu;
- łagodniejszy remis (żeby śmierć nie była "tańsza" od draw);
- **`ESCAPE_MOVE_BONUS`**: ruch, który wychodzi z `in_danger` -> nagroda;
- curriculum: wcześniej i częściej **Planner**.

**Dlaczego resume, nie nowe pliki:** te same cechy `encode_state` (przed Fazą 2) - wartość Q da się dotrenować; od zera marnowałoby wcześniejsze ~60 Wh.

**Oczekiwany efekt:** spadek self-kill vs Planner; utrzymanie bomb_rate i sensownego WR vs RandomSafe.

Komendy: `docs/train_pure_q.sh` (sekcja Faza 1).

---

## 5. Cechy fizyki (Faza 2) - nowe pliki `q_pure*`

**Problem:** przy kick / knockback / ruchomych przeszkodach ten sam klucz Q
opisywał różne zagrożenia -> losowe samobójstwa.

**Zmiana:** sufiks stanu `|kick_threat|knock_near|obstacle_adj` (0 gdy brak fizyki).

**Dlaczego nowe pliki (`q_pure.json`, `q_pure_physics.json`):** zmiana stringa klucza
psuje mapowanie starej tablicy; lepiej zachować `q_default` / `q_physics` jako historię
i trenować nowe od zera pod nową reprezentację.

**Registry:** preferuje `q_pure*` gdy istnieją.

---

## 6. Wyniki Fazy 1 i Fazy 2 (`results/console.txt`) oraz wykryte problemy w grze

Po uruchomieniu pełnego skryptu treningowego (Faza 1A/1B: 2x80k epizodów resume; Faza 2A/2B: 100k `q_pure` + 120k `q_pure_physics` od zera) otrzymano następujące wyniki ewaluacji czystej polityki (`safe_play=False`):

| Bieg | Epizody | Stany | Czas / Energia | vs RandomSafe | vs Planner |
|------|---------|-------|----------------|---------------|------------|
| Faza 1A (`q_default` resume, bez fizyki) | 80 000 | 6 143 | 595.5 s / 9.93 Wh | WR 0.875, bomb 0.638, **sk 0.125** | WR 0.0, draw 0.413, loss 0.588, bomb 1.0 |
| Faza 1B (`q_physics` resume, z fizyką) | 80 000 | 18 265 | 1215.3 s / 20.26 Wh | WR 0.713, bomb 0.950, **sk 0.250** | WR 0.038, draw 0.088, loss 0.875, bomb 1.0 |
| Faza 2A (`q_pure` od zera, bez fizyki) | 100 000 | 3 025 | 746.0 s / 12.43 Wh | WR 0.913, bomb 0.525, **sk 0.088** | WR 0.0, draw 0.300, loss 0.700, bomb 1.0 |
| Faza 2B (`q_pure_physics` od zera, z fizyką) | 120 000 | 16 700 | 1661.8 s / 27.70 Wh | WR 0.738, bomb 0.888, **sk 0.225** | WR 0.100, draw 0.100, loss 0.800, bomb 1.0 |

### Obserwacje z testów wizualnych w grze (komplikacje po Fazie 2):

1. **Oscylacja ruchów (`A <-> B`) i powrót pod własną bombę (bez fizyki):**
   - Bot AI często powtarzał ruchy (szedł na sąsiednie pole i natychmiast wracał), a po postawieniu bomby i wyjściu z jej krzyża rażenia potrafił **wrócić na pole w zasięgu rażenia i zabić się od własnej bomby**.
2. **Bierna postawa na początku meczu (z włączoną fizyką):**
   - Podczas gry z włączoną fizyką przeciwko innemu botowi, bot AI przyjmował z początku pozycję wyczekującą (licząc na przeżycie, remis albo to, że przeciwnik sam się wyeliminuje).
3. **Samobójstwa bota bazowego `RandomSafeBot`:**
   - Mimo wcześniejszej bramki `bomb_has_escape` przy samym stawianiu bomby, `RandomSafeBot` w kolejnych tickach (gdy `timer > 1`) oceniał ruchy tylko na 1 tick do przodu (`step(sim)`), przez co wchodził z powrotem na własne pole rażenia i ginął od własnej bomby.
4. **Niewłaściwi nauczyciele w treningu (`Random`, `RandomSafe`, `Planner`):**
   - Uczenie przeciwko `Random` i nienaprawionemu `RandomSafe` nagradzało czekanie na samobójstwo wroga.
   - `Planner` gra defensywnie (pesymistyczna predykcja), natomiast **`MonteCarloBot`** (szczególnie z włączonym kopaniem bomb) agresywnie poluje na przeciwnika i wykorzystuje fizykę, stanowiąc najlepszego nauczyciela w treningu.

---

## 7. Diagnoza przyczyn w kodzie i Faza 3 (kierunkowe cechy + uszczelnienie nagród + trening vs MonteCarlo)

### Diagnoza techniczna (dlaczego Faza 2 nie wystarczyła):

1. **Ślepy na kierunki klucz stanu (`encode_state`):**
   - Cecha `fire` opisywała wyłącznie aktualne pole gracza (`here`), a wektor `(dx, dy)` nie widział ścian, filarów ani bomb.
   - Gdy bot postawił bombę i zrobił krok na bezpieczne pole (`fire = 0`), klucz stanu tracił informację, z której strony (`UP/DOWN/LEFT/RIGHT`) leży bomba. Ponieważ `(dx, dy)` nadal wskazywało w stronę przeciwnika (przez bombę), tablica Q odsyłała bota z powrotem w ogień.
2. **Reward hacking (eksploit oscylacji) w `_step_reward`:**
   - Wyjście z pola zagrożonego na bezpieczne dawało `ESCAPE_MOVE_BONUS = +0.55`, ale **wejście z pola bezpiecznego z powrotem w pole rażenia dawało `0.0` (brak kary!)**.
   - Agent w treningu uczył się oscylować na granicy promienia rażenia własnej bomby (`bezpieczne <-> zagrożone`), zbierając co 2 ticki darmowe `+0.55`, aż w ostatnim ticku zapalnika zostawał w ogniu i ginął.
   - Analogicznie `APPROACH_BONUS` nagradzał zmniejszenie dystansu Manhattan (`+0.04`), ale nie karał za jego zwiększenie (`0.0`), co premiowało chodzenie tam i z powrotem przy ścianie.
3. **Nagradzanie bierności przy samobójstwie przeciwnika:**
   - W `_step_reward` bot otrzymywał `KILL_BONUS = +1.5` oraz `WIN_REWARD = +1.5` nawet wtedy, gdy przeciwnik zabił się własną bombą (`by_self = True`), a nasz bot nie wykonał żadnego ataku.
4. **Asymetria narożników:**
   - W `_train_shard` agent grał zawsze jako Gracz `0` (lewy górny róg `(1, 1)`), więc po stronie Gracza `1` trafiał na nieznane konfiguracje kierunków.

### Wdrożone rozwiązanie (Faza 3):

1. **Naprawa `RandomSafeBot` (`bomberman/ai/baselines.py`) oraz `PlannerBot` (`bomberman/ai/planner_bot.py`):**
   - Gdy na planszy leży własna bomba `RandomSafeBot` (`b.owner == me`), bot używa osi czasu `predict` i `escape_path` dla własnych bomb: wychodzi najkrótszą drogą poza krzyż rażenia (`tier2_escapable` -> `tier1_safe`) i nigdy nie wraca na pola objęte wybuchem własnej bomby.
   - W `PlannerBot._approach` zastąpiono sztywne `if me == 0: return Action.STAY` warunkiem zależnym od parzystości ticku `(state.tick + me) % 2 == 0`, dzięki czemu Gracz 0 nie zamiera w miejscu przy pasywnym rywalu.
2. **Kierunkowe cechy stanu i kompresja przestrzeni zagrożeń (`bomberman/ai/features.py`, `qlearner_bot.py`):**
   - Dodano `escape_dir` (`0..5`, pierwszy krok ścieżki `escape_path` z uwzględnieniem `with_kick_threats`), `nav_dir` (`0..4`, pierwszy krok bezpiecznego BFS omijającego ściany, skrzynie i ogień do pozycji ataku/skrzyni/kopnięcia bomby) oraz 4-znakową maskę bezpieczeństwa sąsiadów `dir_safety_mask` (`0` = śmierć/ściana, `1` = w zasięgu ognia z ucieczką, `2` = całkowicie bezpieczne).
   - Dodano funkcję `kick_is_useful` wykrywającą bezpieczne, ofensywne kopnięcie bomby w stronę przeciwnika.
   - Gdy `fire > 0` (bot stoi w strefie zagrożenia), cechy nawigacyjne (`nav_dir`, `dist_b`, `open_map`) są normalizowane do `0`, co **60-krotnie zmniejsza fragmentację stanów ucieczki** w tablicy Q.
   - W `QLearnerBot` dodano pamięć poprzedniego pola (`_prev_cell`), blokującą cofanie się z bezpiecznego pola w zagrożone oraz bezcelowe oscylacje `A <-> B`.
3. **Uszczelnienie nagród i kontrfaktyczna aktualizacja tablicy Q (`bomberman/ai/train.py`):**
   - Dodano `ENTER_DANGER_PENALTY = -0.75` (większą co do modułu niż `ESCAPE_MOVE_BONUS = +0.55`), co czyni cykl `bezpieczne -> ogień -> bezpieczne` nieopłacalnym (`-0.20`).
   - Dodano `ESCAPE_STEP_BONUS = +0.25` i `WRONG_ESCAPE_PENALTY = -0.45` wewnątrz krzyża rażenia, `BACKTRACK_PENALTY = -0.06` za cofanie się, `KICK_ATTACK_BONUS = +0.45` za ofensywne kopnięcie bomby oraz `PASSIVE_PENALTY = -0.60` za brak ataków w meczu.
   - Wyeliminowano przyznawanie `KILL_BONUS` i pełnego `WIN_REWARD` za samobójstwo przeciwnika (`by_self = True`).
   - Dodano kontrfaktyczną ocenę wszystkich legalnych akcji przy pierwszych wizytach w nowym stanie `key`, dzięki czemu w tablicy Q nie zostają nieodwiedzone akcje z pozorną wartością `Q = 0.0`.
4. **Trening przeciwko `MonteCarloBot` i `self-play` na obu narożnikach (`seat = ep % 2`):**
   - Wykluczono `random` i `planner` z domyślnego treningu na rzecz `MonteCarloBot` + `self-play` oraz dodano ewaluację `vs_montecarlo` po obu stronach mapy.
   - **Wyniki pełnego treningu Fazy 3 (`bash docs/train_pure_q.sh`, 80 gier ewaluacyjnych na parę):**

| Model (Faza 3) | Epizody / Stany | Czas / Energia | vs RandomSafe | vs Planner | vs MonteCarlo |
|---|---|---|---|---|---|
| `q_pure.json` (bez fizyki) | 15 000 / 2 455 | 1303.9 s / 21.73 Wh | WR **0.7625**, draw 0.225, loss **0.0125**, sk **0.0125**, bomb 1.0 | WR 0.0, draw **0.9875**, loss **0.0125**, sk **0.0125**, bomb 1.0 | WR **0.0875**, draw **0.775**, loss **0.1375**, sk 0.1625, bomb 1.0 |
| `q_pure_physics.json` (z fizyką) | 20 000 / 17 662 | 3601.4 s / 60.02 Wh | WR **0.825**, draw 0.125, loss **0.05**, sk **0.075**, bomb 1.0 | WR **0.20**, draw **0.60**, loss **0.20**, sk **0.10**, bomb 1.0 | WR **0.15**, draw **0.5125**, loss **0.3375**, sk 0.2125, bomb 1.0 |

   - **Porównanie Faza 2 -> Faza 3:**
     - **Bez fizyki vs Planner:** spadek porażek z **70,0%** do **1,25%** (98,75% remisów) oraz spadek samobójstw (`self-kill`) z **65,0%** do **1,25%** przy `bomb_rate = 1.0`.
     - **Z fizyką vs Planner:** wzrost wygranych z **10,0%** do **20,0%**, spadek porażek z **80,0%** do **20,0%** oraz spadek samobójstw z **63,75%** do **10,0%**.
     - **Z fizyką vs MonteCarlo:** **15,0%** wygranych i **51,25%** remisów (66,25% gier nieprzegranych z najtrudniejszym botem potrafiącym kopać bomby).

---

## 8. Faza 4 - Aktywne kopanie bomb (`kick_score`), wykorzystanie odrzutu (`knockback`) i przełamywanie pętli AI vs AI

Po weryfikacji modeli z Fazy 3 zaobserwowano dwa subtelne ograniczenia:

1. **Brak aktywnego kopania bomb przez bota AI przy włączonej fizyce (`kicks_per_game = 0.0`):**
   - W Fazie 3 w `encode_state` zachodziła kolizja cech: gdy bot stał obok bomby (aby ją kopnąć), znajdował się w odległości 1 pola od niej, a więc wewnątrz jej krzyża rażenia (`fire > 0`). Gałąź `if fire > 0:` w `encode_state` **zerowała `nav_dir = 0`**, przez co informacja z `best_nav_info` o kierunku kopnięcia bomby nigdy nie trafiała do klucza stanu!
   - Co więcej, po położeniu własnej bomby i cofnięciu się o 1 pole, blokada anty-oscylacyjna (`_prev_cell`) zabraniała wejścia z powrotem na pole bomby (czyli jej kopnięcia), a `best_escape_action` od razu prowadziło za róg zamiast ustawić bota w linii strzału.
2. **Zapętlanie się w pojedynkach `QLearner` vs `QLearner`:**
   - Pamięć tylko jednego poprzedniego pola (`_prev_cell`) nie wykrywała:
     a) **kolizji czołowych na spornym polu** (`targets[0] == targets[1]` w `rules.py`), gdzie obaj gracze pozostawali na swoich polach (`_curr_cell == here`), więc `_prev_cell` się nie aktualizowało i obaj powtarzali ten sam zablokowany ruch w nieskończoność;
     b) **cykli 6-tickowych** (stawianie bomby w tym samym narożniku -> schowanie się za filarem -> powrót na to samo pole po wybuchu, gdy skrzynie w zasięgu dawno zniknęły).

### Wdrożone rozwiązanie (Faza 4):

1. **Odblokowanie kopania bomb i komba "postaw-cofnij-kopnij" (`bomberman/ai/features.py`, `qlearner_bot.py`):**
   - Dodano funkcję `kick_score(state, me, action, cfg)` oraz `best_kick_action`: ocenia symulacją `step()` + `predict()`, czy kopnięcie bomby jest bezpieczne dla bota i daje zysk taktyczny względem biernej przyszłości (pułapka na wroga, wepchnięcie bomby w linię wroga, trafienie wroga odrzutem, zniszczenie dodatkowych skrzyń lub obronne odepchnięcie cudzej/ślizgającej się bomby).
   - W `encode_state` przy `fire > 0` zachowano kierunek kopnięcia w `nav_dir = _ACTION_CODE[kick_act]` (gdy `kick = 3`), a w `dir_safety_mask` bezpieczne i celowe kopnięcie bomby oznaczono jako `'2'`.
   - Dodano `_can_setup_kick_attack` (bomba w długim korytarzu jest uznawana za użyteczną, jeśli można się cofnąć o 1 pole i kopnąć ją w stronę wroga/skrzyń), a w `best_escape_action` na świeżo położonej bombie preferowany jest bezpieczny krok w tył ustawiający bota do kopnięcia.
   - W `QLearnerBot` wyłączono blokadę `_prev_cell`, gdy na docelowym polu leży bomba do kopnięcia (`bomb_at(state, target_c) is not None`).
2. **Świadomość odrzutu (`knockback`) w obronie i ataku (`bomberman/ai/features.py`, `train.py`):**
   - Cecha `knock` przyjmuje teraz 3 wartości: `0` = brak, `1` = pole bota w strefie fali uderzeniowej (traktowane na równi z zagrożeniem ogniem - wymusza zejście z linii odrzutu przed wybuchem, `SELF_KNOCK_PENALTY = -0.25`), `2` = przeciwnik w strefie fali uderzeniowej (`KNOCK_ENEMY_BONUS = +0.35`, zachęta do wysadzania bomb ogłuszających/odpychających rywala z odległości $R < d \le R_k = 4$).
3. **Detekcja kolizji czołowych i cykli wielokrokowych w `QLearnerBot` (`bomberman/ai/qlearner_bot.py`):**
   - Dodano detekcję zablokowanego ruchu (`_curr_cell == here` przy ruchu niebędącym kopnięciem bomby) z naprzemiennym ustępowaniem pola.
   - Dodano licznik powtórzeń krawędzi `_edge_counts[(here, action)]` oraz licznik bomb na tym samym polu `_bomb_counts[here]`, automatycznie resetowane w momencie zniszczenia dowolnej skrzyni na mapie (`box_count != _last_box_count`). Po 2 bezskutecznych bombach w tym samym miejscu lub wielokrotnym powtarzaniu tej samej pętli korytarza bot płynnie przełącza się na alternatywne bezpieczne ścieżki.
4. **Wyniki weryfikacji Fazy 4 (po krótkim treningu weryfikacyjnym 1 500 / 2 000 epizodów):**
   - `q_pure.json` (bez fizyki): `vs RandomSafe` **WR = 87,5% (0% porażek, 0% self-kill)**; `vs Planner` **100% remisów, 0% porażek, 0% self-kill**; `vs MonteCarlo` **WR = 15,0%, 77,5% remisów, tylko 7,5% porażek**.
   - `q_pure_physics.json` (pełna fizyka): bot aktywnie kopie bomby (**6 198 kopnięć w treningu**, średnio **5,7-10,8 kopnięć na mecz** w ewaluacji), a przeciwko `Plannerowi` z fizyką osiąga **WR = 35,0% wygranych, 50,0% remisów i tylko 15,0% porażek** (`self-kill = 10,0%`)!

---

## 9. Czego świadomie nie robimy

| Pomysł | Powód odrzucenia |
|--------|------------------|
| BFS escape z powrotem w `act()` | łamie wymóg "tylko nauczone ruchy z tablicy Q" w grze (`safe_play=False`) |
| DQN / sieć neuronowa | poza zakresem tabularnego Q-learningu i wymaga zewnętrznych bibliotek ML |
| Jedna tablica na fizykę i brak | cecha `physics` w kluczu + osobne pliki (`q_pure.json`, `q_pure_physics.json`) dają lepszą specjalizację |

---

## 10. Jak czytać koszty vs algorytmy i próg opłacalności (Break-Even Point)

- **Q-Learning (AI):** duży koszt **przed** grą (trening offline zapisany w `results/ai_cost_ledger.json` oraz `*.train.meta.json`), natomiast w trakcie meczu niski koszt ruchu (odczyt ze słownika $Q(s, a)$ wspierany kierunkowym kodowaniem `encode_state`, średnio $\approx 0{,}6\text{-}1{,}1\text{ ms}$ na ruch i $\approx 4{,}3\text{ ops}$).
- **Planner (BFS w czasie):** brak treningu offline ($0\text{ Wh}$), niski czas decyzji ($\approx 0{,}4\text{-}1{,}9\text{ ms}$, śr. $\approx 10\text{ ops}$ BFS), ale wysoka złożoność projektowa (ręczne reguły czasoprzestrzenne, unikanie pól spornych, symulacja kontrbomby i pesymistyczne scenariusze kopnięć `with_kick_threats`).
- **MonteCarlo (Rollouts):** brak treningu offline ($0\text{ Wh}$), prosta implementacja oparta na wywołaniach `step()`, bardzo wysoka skuteczność w fizyce ciągłej, lecz **ogromny koszt obliczeniowy w każdym ticku gry** ($\approx 32\text{-}76\text{ ms}$ na ruch, $\approx 800\text{-}1440\text{ ops}$ na ruch, czyli **30-75x wolniej** niż `Planner` i `Q-Learning`).

### Analiza środowiskowa (Break-Even przy grze z człowiekiem)

Przy założeniu mocy obliczeniowej $P = 15\text{ W}$:
- Pojedyncza rozgrywka z botem **MonteCarlo** zużywa średnio $\approx 6\text{-}14\text{ s}$ czasu CPU ($\approx 0{,}025\text{-}0{,}058\text{ mWh}$ energii na jeden mecz), podczas gdy bot **Q-Learning (AI)** zużywa w meczu jedynie $\approx 0{,}1\text{-}0{,}2\text{ s}$ czasu CPU ($\approx 0{,}0004\text{-}0{,}0008\text{ mWh}$).
- Oszczędność energii w każdym meczu człowieka z botem `Q-Learning` zamiast `MonteCarlo` wynosi zatem $\Delta E \approx 0{,}025\text{-}0{,}057\text{ mWh}$ na rundę.
- Koszt wytrenowania pary docelowych modeli Fazy 4 (`q_pure.json` + `q_pure_physics.json`: $15\,000 + 20\,000$ epizodów $\approx 81{,}75\text{ Wh}$ dla pełnego biegu lub $\approx 7{,}74\text{ Wh}$ dla biegu szybkiego) zwraca się po rozegraniu:
  - **ok. $140\,000\text{-}220\,000$ rund** (dla krótkiego treningu $\approx 7{,}7\text{ Wh}$),
  - **ok. $1{,}4\text{-}2{,}3\text{ mln}$ rund** (dla pełnego treningu produkcyjnego $\approx 81{,}8\text{ Wh}$),
  - a wliczając cały historyczny budżet badawczy R&D z `results/ai_cost_ledger.json` ($\approx 230{,}8\text{ Wh}$ dla $743\,300$ epizodów) - po **ok. $4{,}0\text{-}6{,}5\text{ mln}$ rund**.
- Wniosek inżynierski: dla pojedynczego gracza lokalnego algorytm `Planner` lub `MonteCarlo` jest tańszy energetycznie w skali całego cyklu życia produktu (ponieważ gracz rozegra kilkadziesiąt lub kilkaset partii, a nie miliony). Natomiast w grze sieciowej / mobilnej obsługującej tysiące graczy jednocześnie na serwerach, jednorazowy koszt treningu `Q-Learningu` amortyzuje się, odciążając procesory serwerowe ponad 50-krotnie w każdej klatce gry względem `MonteCarlo`.

