# Zasady gry i model fizyczny

Ten dokument opisuje dokładnie to, co implementuje silnik (`bomberman/engine/`).
Każda zmiana zasad wymaga zmiany tego pliku i testów w `tests/` (przez Pull Request).

Wszystkie parametry są w `configs/default.json` (wartości domyślne podane w nawiasach).

## 1. Plansza

- Wymiary W x H są nieparzyste (9x9). Współrzędne: `x` to kolumna, `y` to wiersz, `(0, 0)` to lewy górny róg.
  W kodzie pole to indeks `y * W + x`.
- Na brzegach są ściany, a na polach o parzystym `x` i parzystym `y` stoją stałe filary.
- Skrzynie są losowane z seeda z prawdopodobieństwem `box_density` (0,4), **symetrycznie względem środka planszy**
  (obrót o 180°). Żaden narożnik nie jest więc uprzywilejowany.
- Gracz 0 startuje w `(1, 1)`, gracz 1 w `(W-2, H-2)`. Pola startowe i ich dwaj sąsiedzi są zawsze wolne.
- Gdy włączone są ruchome przeszkody, wiersze ich torów są oczyszczone ze skrzyń
  (dla 9x9 są to wiersze 3 i 5).

## 2. Ticki i akcje

- Gra toczy się w tickach. W każdym ticku oba boty **jednocześnie** wybierają jedną akcję:
  `STAY`, `UP`, `DOWN`, `LEFT`, `RIGHT`, `BOMB`.
- Ruch przesuwa gracza o jedno pole, jeśli na polu docelowym nie ma ściany, skrzyni, ruchomej przeszkody,
  bomby ani drugiego gracza (liczy się pozycja z początku ticku, więc gracze nie mogą zamienić się miejscami).
- Jeśli obaj gracze chcą wejść na to samo pole, obaj zostają w miejscu.
- `BOMB` kładzie bombę na polu gracza, jeśli gracz ma wolną bombę (`max_bombs` = 1) i na tym polu nie ma bomby.
- Gracz może zejść z pola z bombą, ale nie może na nie wrócić. Przy włączonym kopaniu próba wejścia
  na pole z nieruchomą bombą kopie ją (rozdział 6).
- Gracz ogłuszony odrzutem (w ślizgu) nie wykonuje akcji, dopóki się nie zatrzyma.

## 3. Bomby, ogień i reakcje łańcuchowe

- Bomba położona w ticku `t` ma zapalnik `bomb_timer` (5) i wybucha w ticku `t + 5`.
  Gracz, który ją położył, ma więc 5 ruchów na ucieczkę.
- Wybuch ma kształt krzyża o promieniu `bomb_radius` (2), liczonego od pola, na którym bomba **aktualnie** leży
  (przy fizyce bomba mogła się przesunąć).
- Promień ognia w danym kierunku:
  - zatrzymuje się na ścianie i na ruchomej przeszkodzie (tych pól nie podpala);
  - zatrzymuje się na skrzyni (podpala ją, skrzynia znika na końcu ticku);
  - zatrzymuje się na innej bombie (podpala ją; ta bomba wybucha w tym samym ticku, czyli reakcja łańcuchowa).
- Ogień trwa `flame_duration` (1) tick: pola z ogniem są widoczne w stanie po ticku wybuchu
  i gasną na początku kolejnego ticku. Bomba, która znajdzie się w aktywnym ogniu, wybucha.
- Gracz, którego pole jest w ogniu na końcu ticku, ginie.

## 4. Koniec gry

- Gdy ginie jeden gracz, wygrywa drugi.
- Jeśli obaj giną w tym samym ticku albo minie `max_ticks` (200) ticków, jest remis.

## 5. Kolejność obliczeń w `step()`

1. Wygaszenie ognia z poprzednich ticków.
2. Akcje: najpierw kładzenie bomb, potem ruchy i kopnięcia (gracz 0 przed graczem 1).
3. Fizyka: ruchome przeszkody, bomby w ruchu (w kolejności `id`), ślizgający się gracze.
4. Zapalniki maleją o 1 (z wyjątkiem bomb położonych w tym ticku), wybuchy z reakcjami łańcuchowymi.
5. Odrzut od wybuchów: ciała dostają prędkość, ruch zaczyna się w następnym ticku.
6. Śmierć graczy stojących w ogniu, zniszczenie trafionych skrzyń.
7. `tick += 1` i sprawdzenie końca gry.

`step()` jest deterministyczny: ten sam stan i te same akcje zawsze dają ten sam wynik.

## 6. Model fizyczny (rozszerzenie)

Każdy element ma osobną flagę w `physics`: `kick`, `knockback`, `moving_obstacles`.
Gdy wszystkie są wyłączone, gra jest dokładnie wariantem podstawowym.

### 6.1. Ciała i jednostki

- Jednostka długości to jedno pole, jednostka czasu to jeden tick, prędkość to pola/tick.
- Ciała dynamiczne: bomby (`mass_bomb` = 1) i gracze w ślizgu (`mass_player` = 2).
  Gracz, który się nie ślizga, stoi pewnie na ziemi i dla innych ciał jest nieruchomą przeszkodą.
- Ruchome przeszkody to ciała kinematyczne: mają zadany ruch, nie reagują na zderzenia
  (zachowują się jak ciało o nieskończonej masie), a jedynie zmieniają kierunek po kontakcie.
- Pozycje i prędkości są ciągłe (liczby zmiennoprzecinkowe). Ruch odbywa się zawsze wzdłuż jednej osi
  (korytarze labiryntu mają szerokość jednego pola). Gdy ciało dostanie prędkość w obu osiach,
  zostaje składowa o większej wartości.
- Ciało zajmuje pole, nad którym leży jego środek. Przy liczeniu kontaktu ciało jest kwadratem
  o boku 1: kontakt z przeszkodą stojącą w polu `c + 1` następuje, gdy środek ciała dojdzie do środka pola `c`.
  Ruchoma przeszkoda w położeniu połówkowym zajmuje oba pola, nad którymi stoi.

### 6.2. Kopnięcie

Gracz wchodzący na pole z nieruchomą bombą kopie ją: bomba dostaje prędkość `kick_speed` (1,5)
w kierunku ruchu gracza i rusza jeszcze w tym samym ticku. Gracz zostaje na swoim polu.
Nie można kopnąć bomby, na której stoi drugi gracz.

### 6.3. Ślizg z tarciem

Tarcie kinetyczne daje stałe opóźnienie `friction` (μ = 0,15). W czasie `dt` przy prędkości początkowej `v`:

- jeśli `v / μ <= dt`, ciało zatrzymuje się po drodze `s = v² / (2μ)`;
- w przeciwnym razie przebywa `s = v*dt - μ*dt²/2` i ma prędkość `v - μ*dt`.

Wzory są dokładne dla stałego opóźnienia, więc całkowita droga hamowania wynosi `v0² / (2μ)` niezależnie
od podziału na ticki. Po zatrzymaniu ciało wyrównuje się do środka pola, nad którym leży.

### 6.4. Zderzenia (współczynnik restytucji `e`)

Gdy ciało dojdzie do punktu kontaktu w trakcie ticku, liczony jest dokładny czas dojścia,
rozwiązywane jest zderzenie, a pozostały czas ticku jest symulowany dalej (najwyżej 4 zderzenia na tick).

- Ściana lub skrzynia: `v' = -e_w * v` (`restitution_wall` = 0,5 dla bomb; gracze się nie odbijają, `e = 0`).
- Stojący gracz: bomba (lub ślizgający się gracz) zatrzymuje się (`v' = 0`). Gracz jest zakotwiczony w ziemi.
- Dwa ciała dynamiczne o masach `m1`, `m2` i prędkościach `v1`, `v2` (`restitution_body` = 1):
  - `v1' = (m1*v1 + m2*v2 - m2*e*(v1 - v2)) / (m1 + m2)`
  - `v2' = (m1*v1 + m2*v2 + m1*e*(v1 - v2)) / (m1 + m2)`
  - pęd jest zachowany zawsze, a energia kinetyczna przy `e = 1`
    (dla równych mas ciała wymieniają się prędkościami, jak w kołysce Newtona).
- Ruchoma przeszkoda o prędkości `u` (składowa wzdłuż osi ruchu ciała): `v' = (1 + e)*u - e*v`,
  gdzie `e = restitution_wall` dla bomb i `e = 0` dla graczy. Przeszkoda popycha bombę i jedzie dalej.
  Jeśli bomba nie ma dokąd się przesunąć, przeszkoda zawraca.
- Zderzenia są rozwiązywane sekwencyjnie w kolejności `id`. Uderzone ciało rusza w swojej kolejce
  (w tym samym albo w następnym ticku).
- Zderzenie zachodzi tylko wtedy, gdy ciała się zbliżają. Jeśli ciało dogoniło szybsze ciało,
  które jeszcze nie wykonało ruchu w tym ticku, czeka w punkcie kontaktu do końca ticku (tarcie dalej działa).
- Ciało wolniejsze niż 0,001 pola/tick uznajemy za zatrzymane.

### 6.5. Odrzut po wybuchu

- Fala uderzeniowa biegnie wzdłuż czterech kierunków krzyża, ale tylko w tych kierunkach, w których
  ogień dotarł na pełny promień (nie zatrzymał się na ścianie, skrzyni, przeszkodzie ani bombie).
- Ciała (bomby i żywi gracze) w odległości `d` od środka wybuchu, gdzie `bomb_radius < d <= knock_range` (4),
  dostają impuls skierowany od wybuchu: `J = knock_impulse * (1 - d / (knock_range + 1))` (`knock_impulse` = 4),
  czyli zmianę prędkości `Δv = J / m`. Lżejsze bomby lecą więc dwa razy szybciej niż gracze.
- Falę zatrzymują ściany, skrzynie i ruchome przeszkody.
- Gracz, który dostał prędkość, jest ogłuszony (nie wykonuje akcji) aż do zatrzymania.
  Może zostać wepchnięty w ogień innej bomby albo wypchnięty ze strefy zagrożenia.

### 6.6. Ruchome przeszkody

- Dwie przeszkody jeżdżą po oczyszczonych wierszach (dla 9x9 start w `(4, 3)` w prawo i w `(4, 5)` w lewo)
  ze stałą prędkością `obstacle_speed` (0,5).
- Zawracają po kontakcie ze ścianą, skrzynią, graczem lub drugą przeszkodą.
- Blokują ruch graczy i ogień, zasłaniają przed falą uderzeniową i popychają bomby.

### 6.7. Dlaczego fizyka jest liczona w Pythonie

Boty przewidują zagrożenia, przewijając kopię stanu do przodu tą samą funkcją `step()`.
Ślizgające się bomby, odbicia i ruchome przeszkody automatycznie trafiają więc do predykcji,
a gra, boty i eksperymenty korzystają z jednej, deterministycznej implementacji.
Fizyka wbudowana w Godota nie pozwala na tanie skopiowanie świata i przewinięcie go do przodu.
