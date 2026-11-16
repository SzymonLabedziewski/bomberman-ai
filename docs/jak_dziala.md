# Jak działa program

Zasady gry i wzory fizyki są w [zasady.md](zasady.md), protokół z Godotem w [protokol.md](protokol.md),
a szczegóły treningu Q-learningu w [qlearning.md](qlearning.md). Tutaj opis tego, jak działa kod.

## Silnik (`bomberman/engine`)

- `state.py` - stan gry i podstawowe typy, wspólne dla silnika, botów i serwera. Pola planszy są
  w spłaszczonej siatce (`y * width + x`). `flame_info` trzyma dla każdego pola ognia właścicieli bomb
  (bity 0 i 1) oraz informację, czy któraś z tych bomb była wcześniej poruszona przez fizykę (bit 2).
- `rules.py` - `step()` przesuwa stan o jeden tick. Wybuchy liczone są razem z reakcjami łańcuchowymi;
  trafione skrzynie znikają dopiero po sprawdzeniu śmierci graczy. Śmierć liczy się jako "z udziałem
  fizyki", jeśli gracz dostał odrzut w ciągu kilku ostatnich ticków.
- `physics.py` - ciała poruszają się zawsze wzdłuż jednej osi (przy dwóch składowych prędkości zostaje
  większa). Pozycja i prędkość są ciągłe, ruch w ticku liczony jest dokładnymi wzorami dla stałego
  opóźnienia, a zderzenia w dokładnym czasie kontaktu. Ruchoma przeszkoda jedzie ze stałą prędkością
  i zawraca przed ścianą, skrzynią, graczem lub inną przeszkodą; bombę popycha
  (`v' = (1 + e) * u - e * v`), o ile bomba ma dokąd się przesunąć. Odrzut po wybuchu daje ciału
  prędkość `dv = J / m`, a ruch zaczyna się w następnym ticku. Przewidywanie toru gracza po odrzucie
  jest przybliżone: gracz zatrzymuje się na pierwszej przeszkodzie.

## Predykcja zagrożeń (`ai/danger.py`)

`predict()` przewija kopię stanu o kilka ticków tą samą funkcją `step()`, której używa gra, zakładając,
że gracze stoją w miejscu i nie kładą nowych bomb ("pasywna przyszłość"). Dzięki temu reakcje
łańcuchowe, ślizgające się bomby, odbicia i ruchome przeszkody trafiają do predykcji bez dodatkowego kodu.

- Element 0 osi czasu to stan bieżący, element `t` to stan po `t` tickach. Symulacja kończy się wcześniej,
  gdy na planszy nie ma już bomb ani ognia.
- Przy ruchomych przeszkodach ogień liczony jest tak, jakby przeszkody nie osłaniały - przeszkoda zawraca
  przed graczem, więc osłona z pasywnej przyszłości jest niepewna.
- Opcja `absent` usuwa gracza z symulacji. Bot planujący własny ruch nie powinien zakładać, że stojąc
  w miejscu zatrzyma ślizgającą się bombę albo zawróci przeszkodę.
- `with_kick_threats()` dokłada ogień bomb, które przeciwnik zdąży kopnąć. Dla każdej nieruchomej bomby
  i każdego pola, z którego da się ją kopnąć, symulowane jest kopnięcie w najwcześniejszym możliwym ticku - raz z graczem stojącym w miejscu, raz bez niego. Wynik to suma ognia ze wszystkich scenariuszy
  (predykcja pesymistyczna).
- `escape_path()` to BFS po stanach (pole, tick). Zwraca listę pól, po jednym na tick, albo `None`.
  Parametry: `start`/`start_t` (szukanie od innego pola lub ticku), `best_effort` (gdy ucieczki nie ma,
  droga, na której gracz przeżyje najdłużej), `contested` (pola, na które przeciwnik może wejść wcześniej - ścieżka je omija, bo jednoczesne wejście zatrzymuje obu graczy), `collect` (zbiera cały bezpieczny
  obszar zamiast kończyć na pierwszym polu).

## Boty (`bomberman/ai`)

Każdy bot ma własny, deterministyczny generator liczb losowych. Pole `debug` bota serwer przesyła
do Godota i rysuje jako nakładkę (zaplanowana ścieżka, oceny akcji).

### RandomSafe

Losuje spośród akcji, po których przeżyje następny tick. Bombę kładzie tylko, gdy ma drogę ucieczki.
Pierwszeństwo mają ruchy poza zasięg własnych bomb, potem najkrótsze ucieczki, a na końcu ruchy,
po których bot po prostu przeżyje tick.

### Planner

W każdym ticku:

1. Predykcja zagrożeń na H ticków do przodu.
2. Jeśli pole bota będzie w ogniu - najkrótsza ścieżka ucieczki. Najpierw szuka ucieczki omijającej
   pola sporne (te, na które przeciwnik dojdzie nie później niż bot).
3. W przeciwnym razie ocenia ataki (bomba, kopnięcia) w stanie hipotetycznym. Atak jest dozwolony tylko,
   gdy bot ma pewną ucieczkę, także jeśli przeciwnik w tym samym ticku położy bombę albo kopnie bombę,
   do której zdąży dojść. Najwyżej oceniana jest pułapka (przeciwnik bez ucieczki), potem zagrożenie
   przeciwnika (tym wyżej, im mniejszy bezpieczny obszar mu zostaje), na końcu niszczenie skrzyń.
4. W pozostałych przypadkach podchodzi do przeciwnika albo skrzyń, wybierając tylko ruchy, po których
   istnieje ucieczka.

### Monte Carlo

Dla każdej dozwolonej akcji bot rozgrywa K symulacji o głębokości D ticków funkcją `step()`. W pierwszym
ticku wykonuje badaną akcję, potem obaj gracze grają szybką losową polityką: unikają pól bliskiego wybuchu,
a bombę kładą z małym prawdopodobieństwem. Wynik: +1 za śmierć przeciwnika, -1 za własną, 0 gdy giną obaj;
gdy gra trwa dalej - mała ocena heurystyczna (zagrożenie, ruchliwość, odległość). Wygrywa akcja z najlepszą
średnią. Wszystkie akcje oceniane są na tych samych ziarnach losowych (common random numbers), co zmniejsza
wariancję porównań.

### Q-learning

- `features.py` zamienia stan na klucz tablicy Q - 16 pól oddzielonych `|`. Ostatnie trzy (kick, knock,
  obstacle) są zawsze obecne; bez fizyki wynoszą `0|0|0`. Kod bezpieczeństwa ruchów ma po jednym znaku
  na kierunek (UP, DOWN, LEFT, RIGHT): `0` ruch nielegalny/śmiertelny/bez ucieczki, `1` pole zagrożone,
  ale z ucieczką, `2` pole bezpieczne.
- `bomb_is_useful()` - bomba ma sens, gdy da się przed nią uciec i niszczy skrzynie albo realnie grozi
  przeciwnikowi.
- Ucieczka przy włączonym kopaniu: gdy gracz stoi na bombie, woli krok w tył, żeby w następnym ticku
  kopnąć ją w cel. Kopnięcie obronne liczy się tylko dla cudzej lub poruszonej bomby albo gdy bez niego
  nie ma ucieczki.
- `QLearnerBot` w grze wybiera argmax z tablicy Q (w treningu epsilon-greedy). Dodatkowe poprawki przerywają
  pętle: po zderzeniu czołowym jeden z graczy na zmianę wybiera inny ruch, bot nie kładzie trzeciej bomby
  z rzędu na tym samym polu i nie cofa się bez powodu na poprzednie pole. Zderzenie wykrywane jest po tym,
  że bot po ruchu stoi w tym samym miejscu i nie kopnął bomby.
- `safe_play=True` włącza wariant hybrydowy do porównań: w zagrożeniu bot ucieka ścieżką BFS, a poza nim
  wybiera tylko akcje z ucieczką. `bomb_explore` zwiększa w treningu szansę wylosowania użytecznej bomby.
- `train.py` - nagrody premiują atak i wygraną, a nie samo przeżycie. Kara za wejście w zagrożenie musi
  być co do modułu większa niż bonus za wyjście, inaczej wchodzenie i wychodzenie by się opłacało.
  Tryb `montecarlo` przeplata MonteCarlo (60%) z self-play (40%); tryby `aggressive` i `curriculum`
  zaczynają od RandomSafe, potem głównie MonteCarlo i self-play. Energia treningu liczona jest
  przy założonym poborze 15 W (to założenie, nie pomiar).

## Eksperymenty (`bomberman/experiments`)

- `runner.py` - gra nr `i` używa ziarna `seed + i`, więc każda para botów gra na tych samych planszach.
  `games_for` zmniejsza liczbę gier dla najdroższych par. W grach o nieparzystym numerze boty zamieniają
  się narożnikami. Gry idą równolegle (`multiprocessing.Pool`), najdroższe zadania najpierw; wynik nie
  zależy od liczby procesów. Wynik to `results/<nazwa>.csv`.
- `metrics.py` - dla każdego gracza: wynik i długość gry, ruchy samobójcze (akcja, po której
  `escape_path` nie znajduje ucieczki, choć przed nią istniała; sprawdzane kontrfaktycznie), śmierć od
  własnej bomby i z udziałem fizyki, epizody ucieczki (od wejścia w przewidywaną strefę wybuchu do wyjścia
  albo śmierci, osobno z wyjściem i bez), czas decyzji, ops, RSS, liczba kopnięć i bomb.
- `scenarios.py` (E5) - gracz 0 stoi na losowym polu w zasięgu 1-3 bomb przeciwnika. W wariancie
  z fizyką dochodzi bomba ślizgająca się w stronę gracza. Sytuacje bez wyjścia są odrzucane
  z prawdopodobieństwem 75%, żeby obie grupy były podobnej wielkości. Bot nie może kłaść bomb
  (BOMB zamieniane na STAY), żeby mierzyć samą ucieczkę.
- `analyze.py` - przedziały ufności Wilsona, wykresy, `summary.json` dla Godota i `tables.md`
  do sprawozdania.

## Serwer i Godot

Python prowadzi całą grę: pętlę ticków, decyzje botów i fizykę. Godot wysyła polecenia i wejście gracza,
a dostaje stan po każdym ticku; niczego nie liczy, tylko rysuje. Każde połączenie to osobna sesja.
Ruch człowieka trwa, dopóki klient nie wyśle STAY (krótkie wciśnięcie między tickami też się liczy),
BOMB działa raz.

Klient (`net.gd`) łączy się sam i ponawia połączenie co kilka sekund, więc serwer można uruchomić
w dowolnej chwili. Bufor WebSocket jest powiększony do 16 MB, bo powtórki mają kilka MB.
Plansza (`board_view.gd`) interpoluje pozycje ciał między stanami, a zdarzenia (wybuchy, kopnięcia,
odrzut, zderzenia) dostają efekty cząsteczkowe. Interfejs menu jest budowany w kodzie, żeby pliki
`.tscn` były minimalne i nie powodowały konfliktów przy scalaniu.

Powtórka (`match.py`) to `{"type": "replay", "meta": ..., "frames": [...]}`; klatka `k` zawiera stan
po `k` tickach, zdarzenia, które do niego doprowadziły, i decyzje botów podjęte w tym stanie.

Argumenty Godota po `--` (testy bez okna, demo):

| Argument | Działanie |
|---|---|
| `--replay=ŚCIEŻKA` | od razu odtwarza powtórkę |
| `--live=P1,P2` | od razu zaczyna grę na żywo (np. `--live=human,planner`) |
| `--physics` | gra na żywo z pełną fizyką |
| `--tps=N` | prędkość (ticki na sekundę) |
| `--autoquit` | zamyka grę po końcu powtórki albo gry |
| `--offline` | nie łączy się z serwerem |
| `--results[=PLIK]` | od razu otwiera ekran wyników (domyślnie `../results/summary.json`) |
| `--tournament=P1,P2` | na ekranie wyników od razu zaczyna turniej na żywo |
