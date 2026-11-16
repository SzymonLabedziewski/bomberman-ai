# Wyniki eksperymentów i analiza zasobów

## E1 (bez fizyki (bez przeszkód)): wyniki par (z perspektywy pierwszego bota w nazwie pary)

| para | gry | W | R | P | wygrane | remisy | porażki |
|---|---|---|---|---|---|---|---|
| MonteCarlo vs Q-Learning (AI) | 120 | 19 | 97 | 4 | 15.8% | 80.8% | 3.3% |
| Planner vs MonteCarlo | 120 | 19 | 98 | 3 | 15.8% | 81.7% | 2.5% |
| Planner vs Q-Learning (AI) | 160 | 3 | 157 | 0 | 1.9% | 98.1% | 0.0% |
| Random vs MonteCarlo | 200 | 0 | 0 | 200 | 0.0% | 0.0% | 100.0% |
| Random vs Planner | 200 | 0 | 1 | 199 | 0.0% | 0.5% | 99.5% |
| Random vs Q-Learning (AI) | 200 | 0 | 0 | 200 | 0.0% | 0.0% | 100.0% |
| Random vs RandomSafe | 200 | 0 | 1 | 199 | 0.0% | 0.5% | 99.5% |
| RandomSafe vs MonteCarlo | 200 | 1 | 111 | 88 | 0.5% | 55.5% | 44.0% |
| RandomSafe vs Planner | 200 | 0 | 18 | 182 | 0.0% | 9.0% | 91.0% |
| RandomSafe vs Q-Learning (AI) | 200 | 0 | 53 | 147 | 0.0% | 26.5% | 73.5% |

## E1 (bez fizyki (bez przeszkód)): skuteczność i bezpieczeństwo botów (wszystkie gry)

| bot | gry | W | R | P | wygrane | CI od | CI do | samobójcze/100 t. | śmierć od własnej bomby | udane ucieczki | ticki do bezp. pola | bomby/grę | kopnięcia/grę | śmierci z fizyką |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MonteCarlo | 640 | 310 | 306 | 24 | 48.4% | 44.6% | 52.3% | 0.0180 | 4.5% | 99.9% | 2.57 | 13.16 | 0.00 | 0.0% |
| Q-Learning (AI) | 680 | 351 | 307 | 22 | 51.6% | 47.9% | 55.4% | 0.00 | 3.4% | 99.9% | 2.36 | 15.97 | 0.00 | 0.0% |
| Planner | 680 | 403 | 274 | 3 | 59.3% | 55.5% | 62.9% | 0.00 | 0.0% | 100.0% | 2.04 | 14.37 | 0.00 | 0.0% |
| Random | 800 | 0 | 2 | 798 | 0.0% | 0.0% | 0.5% | 7.24 | 99.1% | 59.0% | 2.92 | 1.55 | 0.00 | 0.0% |
| RandomSafe | 800 | 200 | 183 | 417 | 25.0% | 22.1% | 28.1% | 0.38 | 22.2% | 93.6% | 2.35 | 4.55 | 0.00 | 0.0% |

## E1 (bez fizyki (bez przeszkód)): zużycie zasobów obliczeniowych i pamięci

| bot | rodzina | śr. ticków | decyzja śr. [ms] | max decyzja [ms] | czas decyzji/grę [ms] | CPU/ruch [ms] | CPU/grę [ms] | ops/ruch | ops/grę | RAM śr. [KiB] | RAM max [KiB] | energia/grę [mWh] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MonteCarlo | search | 121.24 | 25.91 | 256.39 | 3387.46 | 25.91 | 3380.35 | 815.04 | 101549.25 | 20761.42 | 22476.00 | 14.08 |
| Q-Learning (AI) | rl | 119.43 | 0.75 | 52.97 | 93.55 | 0.75 | 94.36 | 4.44 | 549.94 | 21916.29 | 22476.00 | 0.39 |
| Planner | search | 107.85 | 0.58 | 84.92 | 67.10 | 0.58 | 67.49 | 10.93 | 1221.28 | 20811.81 | 22476.00 | 0.28 |
| Random | random | 13.75 | 0.17 | 4.27 | 2.30 | 0.16 | 2.27 | 1.00 | 13.75 | 21459.56 | 22476.00 | 0.0095 |
| RandomSafe | random | 98.02 | 0.45 | 11.85 | 44.76 | 0.46 | 45.15 | 3.75 | 375.74 | 21443.01 | 22476.00 | 0.19 |

## E1_obs (bez fizyki + ruchome przeszkody): wyniki par (z perspektywy pierwszego bota w nazwie pary)

| para | gry | W | R | P | wygrane | remisy | porażki |
|---|---|---|---|---|---|---|---|
| MonteCarlo vs Q-Learning (AI) | 120 | 67 | 49 | 4 | 55.8% | 40.8% | 3.3% |
| Planner vs MonteCarlo | 120 | 14 | 79 | 27 | 11.7% | 65.8% | 22.5% |
| Planner vs Q-Learning (AI) | 160 | 53 | 87 | 20 | 33.1% | 54.4% | 12.5% |
| Random vs MonteCarlo | 200 | 0 | 0 | 200 | 0.0% | 0.0% | 100.0% |
| Random vs Planner | 200 | 0 | 2 | 198 | 0.0% | 1.0% | 99.0% |
| Random vs Q-Learning (AI) | 200 | 1 | 1 | 198 | 0.5% | 0.5% | 99.0% |
| Random vs RandomSafe | 200 | 1 | 1 | 198 | 0.5% | 0.5% | 99.0% |
| RandomSafe vs MonteCarlo | 200 | 2 | 73 | 125 | 1.0% | 36.5% | 62.5% |
| RandomSafe vs Planner | 200 | 10 | 16 | 174 | 5.0% | 8.0% | 87.0% |
| RandomSafe vs Q-Learning (AI) | 200 | 39 | 27 | 134 | 19.5% | 13.5% | 67.0% |

## E1_obs (bez fizyki + ruchome przeszkody): skuteczność i bezpieczeństwo botów (wszystkie gry)

| bot | gry | W | R | P | wygrane | CI od | CI do | samobójcze/100 t. | śmierć od własnej bomby | udane ucieczki | ticki do bezp. pola | bomby/grę | kopnięcia/grę | śmierci z fizyką |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MonteCarlo | 640 | 419 | 201 | 20 | 65.5% | 61.7% | 69.1% | 0.0369 | 3.1% | 99.9% | 2.59 | 11.16 | 0.00 | 8.0% |
| Q-Learning (AI) | 680 | 356 | 164 | 160 | 52.4% | 48.6% | 56.1% | 0.17 | 20.7% | 99.1% | 2.35 | 11.10 | 0.00 | 0.6% |
| Planner | 680 | 439 | 184 | 57 | 64.6% | 60.9% | 68.1% | 0.0412 | 6.0% | 99.6% | 2.02 | 11.45 | 0.00 | 8.2% |
| Random | 800 | 2 | 4 | 794 | 0.2% | 0.1% | 0.9% | 6.46 | 97.2% | 57.7% | 3.08 | 1.75 | 0.00 | 2.9% |
| RandomSafe | 800 | 249 | 117 | 434 | 31.1% | 28.0% | 34.4% | 0.54 | 24.0% | 91.4% | 2.38 | 3.70 | 0.00 | 18.2% |

## E1_obs (bez fizyki + ruchome przeszkody): zużycie zasobów obliczeniowych i pamięci

| bot | rodzina | śr. ticków | decyzja śr. [ms] | max decyzja [ms] | czas decyzji/grę [ms] | CPU/ruch [ms] | CPU/grę [ms] | ops/ruch | ops/grę | RAM śr. [KiB] | RAM max [KiB] | energia/grę [mWh] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MonteCarlo | search | 101.61 | 53.79 | 343.04 | 5626.46 | 53.68 | 5609.27 | 814.44 | 82577.62 | 20255.61 | 21512.00 | 23.37 |
| Q-Learning (AI) | rl | 89.21 | 1.33 | 172.70 | 127.67 | 1.33 | 128.32 | 4.42 | 403.44 | 21537.68 | 21640.00 | 0.53 |
| Planner | search | 92.72 | 1.09 | 67.59 | 108.86 | 1.09 | 109.40 | 10.79 | 1019.08 | 20378.54 | 21560.00 | 0.46 |
| Random | random | 15.40 | 0.19 | 4.82 | 2.84 | 0.19 | 2.84 | 1.00 | 15.40 | 20887.20 | 21576.00 | 0.0118 |
| RandomSafe | random | 79.91 | 0.80 | 20.90 | 64.60 | 0.81 | 64.84 | 3.73 | 300.94 | 20908.77 | 21640.00 | 0.27 |

## E2 (z fizyką (kopanie + odrzut, bez przeszkód)): wyniki par (z perspektywy pierwszego bota w nazwie pary)

| para | gry | W | R | P | wygrane | remisy | porażki |
|---|---|---|---|---|---|---|---|
| MonteCarlo vs Q-Learning (AI) | 100 | 21 | 57 | 22 | 21.0% | 57.0% | 22.0% |
| Planner vs MonteCarlo | 100 | 18 | 71 | 11 | 18.0% | 71.0% | 11.0% |
| Planner vs Q-Learning (AI) | 140 | 14 | 118 | 8 | 10.0% | 84.3% | 5.7% |
| Random vs MonteCarlo | 200 | 0 | 0 | 200 | 0.0% | 0.0% | 100.0% |
| Random vs Planner | 200 | 0 | 1 | 199 | 0.0% | 0.5% | 99.5% |
| Random vs Q-Learning (AI) | 200 | 0 | 0 | 200 | 0.0% | 0.0% | 100.0% |
| Random vs RandomSafe | 200 | 0 | 0 | 200 | 0.0% | 0.0% | 100.0% |
| RandomSafe vs MonteCarlo | 200 | 6 | 44 | 150 | 3.0% | 22.0% | 75.0% |
| RandomSafe vs Planner | 200 | 3 | 34 | 163 | 1.5% | 17.0% | 81.5% |
| RandomSafe vs Q-Learning (AI) | 200 | 3 | 31 | 166 | 1.5% | 15.5% | 83.0% |

## E2 (z fizyką (kopanie + odrzut, bez przeszkód)): skuteczność i bezpieczeństwo botów (wszystkie gry)

| bot | gry | W | R | P | wygrane | CI od | CI do | samobójcze/100 t. | śmierć od własnej bomby | udane ucieczki | ticki do bezp. pola | bomby/grę | kopnięcia/grę | śmierci z fizyką |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MonteCarlo | 600 | 382 | 172 | 46 | 63.7% | 59.7% | 67.4% | 0.13 | 8.5% | 99.4% | 2.67 | 8.46 | 4.61 | 91.0% |
| Q-Learning (AI) | 640 | 396 | 206 | 38 | 61.9% | 58.1% | 65.6% | 0.83 | 3.8% | 99.7% | 2.40 | 15.12 | 4.01 | 79.1% |
| Planner | 640 | 394 | 224 | 22 | 61.6% | 57.7% | 65.3% | 0.0266 | 4.1% | 99.8% | 2.06 | 12.81 | 0.0500 | 85.3% |
| Random | 800 | 0 | 1 | 799 | 0.0% | 0.0% | 0.5% | 9.10 | 98.9% | 40.0% | 3.36 | 1.31 | 1.21 | 67.2% |
| RandomSafe | 800 | 212 | 109 | 479 | 26.5% | 23.6% | 29.7% | 0.63 | 18.9% | 91.7% | 2.36 | 4.19 | 1.25 | 74.5% |

## E2 (z fizyką (kopanie + odrzut, bez przeszkód)): zużycie zasobów obliczeniowych i pamięci

| bot | rodzina | śr. ticków | decyzja śr. [ms] | max decyzja [ms] | czas decyzji/grę [ms] | CPU/ruch [ms] | CPU/grę [ms] | ops/ruch | ops/grę | RAM śr. [KiB] | RAM max [KiB] | energia/grę [mWh] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MonteCarlo | search | 96.58 | 30.42 | 219.05 | 3103.27 | 30.45 | 3099.64 | 804.75 | 77337.60 | 26481.02 | 35080.00 | 12.92 |
| Q-Learning (AI) | rl | 104.36 | 2.07 | 20.96 | 225.83 | 2.08 | 226.93 | 4.40 | 471.80 | 34595.95 | 35180.00 | 0.95 |
| Planner | search | 99.77 | 1.03 | 68.42 | 110.02 | 1.04 | 110.59 | 11.31 | 1145.90 | 27679.67 | 35136.00 | 0.46 |
| Random | random | 11.37 | 0.17 | 3.83 | 1.95 | 0.17 | 1.95 | 1.00 | 11.37 | 29193.29 | 35168.00 | 0.0081 |
| RandomSafe | random | 88.45 | 0.82 | 10.00 | 73.15 | 0.82 | 73.61 | 3.68 | 328.97 | 29327.80 | 35180.00 | 0.31 |

## E2_obs (z fizyką (kopanie + odrzut) + ruchome przeszkody): wyniki par (z perspektywy pierwszego bota w nazwie pary)

| para | gry | W | R | P | wygrane | remisy | porażki |
|---|---|---|---|---|---|---|---|
| MonteCarlo vs Q-Learning (AI) | 100 | 41 | 50 | 9 | 41.0% | 50.0% | 9.0% |
| Planner vs MonteCarlo | 100 | 9 | 52 | 39 | 9.0% | 52.0% | 39.0% |
| Planner vs Q-Learning (AI) | 140 | 33 | 67 | 40 | 23.6% | 47.9% | 28.6% |
| Random vs MonteCarlo | 200 | 0 | 0 | 200 | 0.0% | 0.0% | 100.0% |
| Random vs Planner | 200 | 0 | 3 | 197 | 0.0% | 1.5% | 98.5% |
| Random vs Q-Learning (AI) | 200 | 0 | 1 | 199 | 0.0% | 0.5% | 99.5% |
| Random vs RandomSafe | 200 | 0 | 1 | 199 | 0.0% | 0.5% | 99.5% |
| RandomSafe vs MonteCarlo | 200 | 5 | 41 | 154 | 2.5% | 20.5% | 77.0% |
| RandomSafe vs Planner | 200 | 14 | 26 | 160 | 7.0% | 13.0% | 80.0% |
| RandomSafe vs Q-Learning (AI) | 200 | 30 | 19 | 151 | 15.0% | 9.5% | 75.5% |

## E2_obs (z fizyką (kopanie + odrzut) + ruchome przeszkody): skuteczność i bezpieczeństwo botów (wszystkie gry)

| bot | gry | W | R | P | wygrane | CI od | CI do | samobójcze/100 t. | śmierć od własnej bomby | udane ucieczki | ticki do bezp. pola | bomby/grę | kopnięcia/grę | śmierci z fizyką |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MonteCarlo | 600 | 434 | 143 | 23 | 72.3% | 68.6% | 75.8% | 0.17 | 6.8% | 99.4% | 2.65 | 7.91 | 3.76 | 86.3% |
| Q-Learning (AI) | 640 | 399 | 137 | 104 | 62.3% | 58.5% | 66.0% | 0.21 | 13.4% | 99.2% | 2.35 | 11.46 | 3.26 | 55.8% |
| Planner | 640 | 399 | 148 | 93 | 62.3% | 58.5% | 66.0% | 0.11 | 12.2% | 99.0% | 2.05 | 9.92 | 0.31 | 69.0% |
| Random | 800 | 0 | 5 | 795 | 0.0% | 0.0% | 0.5% | 8.10 | 98.2% | 45.0% | 3.29 | 1.46 | 1.19 | 66.5% |
| RandomSafe | 800 | 248 | 87 | 465 | 31.0% | 27.9% | 34.3% | 0.76 | 18.2% | 90.4% | 2.35 | 3.56 | 1.08 | 75.0% |

## E2_obs (z fizyką (kopanie + odrzut) + ruchome przeszkody): zużycie zasobów obliczeniowych i pamięci

| bot | rodzina | śr. ticków | decyzja śr. [ms] | max decyzja [ms] | czas decyzji/grę [ms] | CPU/ruch [ms] | CPU/grę [ms] | ops/ruch | ops/grę | RAM śr. [KiB] | RAM max [KiB] | energia/grę [mWh] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MonteCarlo | search | 85.44 | 56.98 | 297.95 | 4962.63 | 56.91 | 4953.27 | 824.53 | 68724.40 | 25958.91 | 35068.00 | 20.64 |
| Q-Learning (AI) | rl | 86.11 | 3.45 | 46.39 | 300.95 | 3.48 | 302.94 | 4.50 | 391.63 | 34426.80 | 35184.00 | 1.26 |
| Planner | search | 82.92 | 1.70 | 107.36 | 149.81 | 1.71 | 150.72 | 11.58 | 981.52 | 27532.14 | 35164.00 | 0.63 |
| Random | random | 12.82 | 0.18 | 7.55 | 2.33 | 0.18 | 2.34 | 1.00 | 12.82 | 28875.25 | 35172.00 | 0.0097 |
| RandomSafe | random | 74.23 | 1.30 | 25.15 | 97.15 | 1.31 | 97.69 | 3.74 | 278.13 | 28916.27 | 35184.00 | 0.41 |

## Porównanie: (bez fizyki, bez przeszkód) vs (bez fizyki + ruchome przeszkody) [E1 vs E1_obs]

| bot | WR (bez przeszkód) | WR (+ przeszkody) | zmiana WR [p.p.] | ucieczki (bez przeszk.) | ucieczki (+ przeszk.) | samob./100t (bez) | samob./100t (+ przeszk.) | decyzja [ms] (bez) | decyzja [ms] (+ przeszk.) | CPU/grę [ms] (bez) | CPU/grę [ms] (+ przeszk.) | ops/ruch (bez) | ops/ruch (+ przeszk.) | RAM [KiB] (bez) | RAM [KiB] (+ przeszk.) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Random | 0.0% | 0.2% | +0.2 p.p. | 59.0% | 57.7% | 7.24 | 6.46 | 0.17 | 0.19 | 2.27 | 2.84 | 1.00 | 1.00 | 21459.56 | 20887.20 |
| RandomSafe | 25.0% | 31.1% | +6.1 p.p. | 93.6% | 91.4% | 0.38 | 0.54 | 0.45 | 0.80 | 45.15 | 64.84 | 3.75 | 3.73 | 21443.01 | 20908.77 |
| Planner | 59.3% | 64.6% | +5.3 p.p. | 100.0% | 99.6% | 0.00 | 0.0412 | 0.58 | 1.09 | 67.49 | 109.40 | 10.93 | 10.79 | 20811.81 | 20378.54 |
| MonteCarlo | 48.4% | 65.5% | +17.0 p.p. | 99.9% | 99.9% | 0.0180 | 0.0369 | 25.91 | 53.79 | 3380.35 | 5609.27 | 815.04 | 814.44 | 20761.42 | 20255.61 |
| Q-Learning (AI) | 51.6% | 52.4% | +0.7 p.p. | 99.9% | 99.1% | 0.00 | 0.17 | 0.75 | 1.33 | 94.36 | 128.32 | 4.44 | 4.42 | 21916.29 | 21537.68 |

## Porównanie: (z fizyką, bez przeszkód) vs (z fizyką + ruchome przeszkody) [E2 vs E2_obs]

| bot | WR (bez przeszkód) | WR (+ przeszkody) | zmiana WR [p.p.] | ucieczki (bez przeszk.) | ucieczki (+ przeszk.) | samob./100t (bez) | samob./100t (+ przeszk.) | decyzja [ms] (bez) | decyzja [ms] (+ przeszk.) | CPU/grę [ms] (bez) | CPU/grę [ms] (+ przeszk.) | ops/ruch (bez) | ops/ruch (+ przeszk.) | RAM [KiB] (bez) | RAM [KiB] (+ przeszk.) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Random | 0.0% | 0.0% | +0.0 p.p. | 40.0% | 45.0% | 9.10 | 8.10 | 0.17 | 0.18 | 1.95 | 2.34 | 1.00 | 1.00 | 29193.29 | 28875.25 |
| RandomSafe | 26.5% | 31.0% | +4.5 p.p. | 91.7% | 90.4% | 0.63 | 0.76 | 0.82 | 1.30 | 73.61 | 97.69 | 3.68 | 3.74 | 29327.80 | 28916.27 |
| Planner | 61.6% | 62.3% | +0.8 p.p. | 99.8% | 99.0% | 0.0266 | 0.11 | 1.03 | 1.70 | 110.59 | 150.72 | 11.31 | 11.58 | 27679.67 | 27532.14 |
| MonteCarlo | 63.7% | 72.3% | +8.7 p.p. | 99.4% | 99.4% | 0.13 | 0.17 | 30.42 | 56.98 | 3099.64 | 4953.27 | 804.75 | 824.53 | 26481.02 | 25958.91 |
| Q-Learning (AI) | 61.9% | 62.3% | +0.5 p.p. | 99.7% | 99.2% | 0.83 | 0.21 | 2.07 | 3.45 | 226.93 | 302.94 | 4.40 | 4.50 | 34595.95 | 34426.80 |

## Turniej łączny (wszystkie warianty łącznie) - wyniki par

| para | gry | W | R | P | wygrane | remisy | porażki |
|---|---|---|---|---|---|---|---|
| MonteCarlo vs Q-Learning (AI) | 440 | 148 | 253 | 39 | 33.6% | 57.5% | 8.9% |
| Planner vs MonteCarlo | 440 | 60 | 300 | 80 | 13.6% | 68.2% | 18.2% |
| Planner vs Q-Learning (AI) | 600 | 103 | 429 | 68 | 17.2% | 71.5% | 11.3% |
| Random vs MonteCarlo | 800 | 0 | 0 | 800 | 0.0% | 0.0% | 100.0% |
| Random vs Planner | 800 | 0 | 7 | 793 | 0.0% | 0.9% | 99.1% |
| Random vs Q-Learning (AI) | 800 | 1 | 2 | 797 | 0.1% | 0.2% | 99.6% |
| Random vs RandomSafe | 800 | 1 | 3 | 796 | 0.1% | 0.4% | 99.5% |
| RandomSafe vs MonteCarlo | 800 | 14 | 269 | 517 | 1.8% | 33.6% | 64.6% |
| RandomSafe vs Planner | 800 | 27 | 94 | 679 | 3.4% | 11.8% | 84.9% |
| RandomSafe vs Q-Learning (AI) | 800 | 72 | 130 | 598 | 9.0% | 16.2% | 74.8% |

## Turniej łączny (wszystkie warianty łącznie) - ranking i zasoby botów

| bot | rodzina | gry | W | R | P | wygrane | decyzja śr. [ms] | CPU/grę [ms] | ops/ruch | RAM śr. [KiB] | energia/grę [mWh] |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MonteCarlo | search | 2480 | 1545 | 822 | 113 | 62.3% | 41.71 | 4268.19 | 814.69 | 23272.12 | 17.78 |
| Q-Learning (AI) | rl | 2640 | 1502 | 814 | 324 | 56.9% | 1.88 | 185.81 | 4.44 | 27925.48 | 0.77 |
| Planner | search | 2640 | 1635 | 830 | 175 | 61.9% | 1.09 | 108.91 | 11.14 | 23994.31 | 0.45 |
| Random | random | 3200 | 2 | 12 | 3186 | 0.1% | 0.18 | 2.35 | 1.00 | 25103.83 | 0.0098 |
| RandomSafe | random | 3200 | 909 | 496 | 1795 | 28.4% | 0.84 | 70.32 | 3.73 | 25148.96 | 0.29 |

## Analiza środowiskowa i próg opłacalności (Break-Even) przy grze z człowiekiem

| wariant | bot odniesienia | CPU odniesienia/grę [ms] | CPU Q-Learning/grę [ms] | oszczędność CPU/grę [ms] | oszczędność energii/grę [mWh] | koszt treningu modelu [Wh] | próg zwrotu (1 model) [gier] | całkowity koszt R&D [Wh] | próg zwrotu (całe R&D) [gier] |
|---|---|---|---|---|---|---|---|---|---|
| bez fizyki | MonteCarlo | 3380.40 | 94.40 | 3286.00 | 13.69 | 21.69 | 1585 | 292.81 | 21386 |
| bez fizyki | Planner | 67.50 | 94.40 | -26.90 | -0.11 | 21.69 | -1 | 292.81 | -1 |
| bez fizyki + przeszkody | MonteCarlo | 5609.30 | 128.30 | 5481.00 | 22.84 | 21.69 | 950 | 292.81 | 12822 |
| bez fizyki + przeszkody | Planner | 109.40 | 128.30 | -18.90 | -0.0788 | 21.69 | -1 | 292.81 | -1 |
| z fizyką | MonteCarlo | 3099.60 | 226.90 | 2872.70 | 11.97 | 40.30 | 3367 | 292.81 | 24463 |
| z fizyką | Planner | 110.60 | 226.90 | -116.30 | -0.48 | 40.30 | -1 | 292.81 | -1 |
| z fizyką + przeszkody | MonteCarlo | 4953.30 | 302.90 | 4650.30 | 19.38 | 40.30 | 2080 | 292.81 | 15112 |
| z fizyką + przeszkody | Planner | 150.70 | 302.90 | -152.20 | -0.63 | 40.30 | -1 | 292.81 | -1 |

## E4: Monte Carlo (K, D) przeciw Plannerowi, bez fizyki

| wariant | gry | wygrane | remisy | porażki | samobójcze/100 t. | udane ucieczki | decyzja śr. [ms] | max decyzja [ms] |
|---|---|---|---|---|---|---|---|---|
| K=10 D=4 | 16 | 0.0% | 87.5% | 12.5% | 0.00 | 100.0% | 6.52 | 35.40 |
| K=10 D=8 | 16 | 0.0% | 93.8% | 6.2% | 0.0332 | 99.8% | 9.59 | 21.76 |
| K=10 D=12 | 16 | 0.0% | 93.8% | 6.2% | 0.0327 | 99.6% | 12.68 | 29.10 |
| K=30 D=4 | 16 | 0.0% | 56.2% | 43.8% | 0.0413 | 99.6% | 17.06 | 34.73 |
| K=30 D=8 | 16 | 0.0% | 81.2% | 18.8% | 0.0722 | 99.6% | 27.68 | 56.79 |
| K=30 D=12 | 16 | 0.0% | 100.0% | 0.0% | 0.00 | 100.0% | 37.78 | 77.80 |
| K=100 D=4 | 16 | 6.2% | 75.0% | 18.8% | 0.00 | 100.0% | 57.58 | 109.40 |
| K=100 D=8 | 16 | 0.0% | 87.5% | 12.5% | 0.00 | 100.0% | 91.87 | 185.69 |
| K=100 D=12 | 16 | 0.0% | 93.8% | 6.2% | 0.00 | 100.0% | 126.35 | 267.63 |

## E5: ucieczka z 500 losowych sytuacji zagrożenia

| wariant | bot | sytuacje | przeżyte | do uniknięcia | przeżyte (do uniknięcia) | bez wyjścia | przeżyte bez wyjścia | ticki do bezp. pola |
|---|---|---|---|---|---|---|---|---|
| bez fizyki | MonteCarlo | 500 | 63.6% | 319 | 99.7% | 181 | 0 | 1.96 |
| bez fizyki | Planner | 500 | 63.8% | 319 | 100.0% | 181 | 0 | 1.74 |
| bez fizyki | Q-Learning (AI) | 500 | 63.8% | 319 | 100.0% | 181 | 0 | 1.77 |
| bez fizyki | Random | 500 | 29.0% | 319 | 45.5% | 181 | 0 | 2.37 |
| bez fizyki | RandomSafe | 500 | 46.4% | 319 | 72.7% | 181 | 0 | 2.38 |
| bez fizyki + przeszkody | MonteCarlo | 500 | 79.8% | 401 | 99.5% | 99 | 0 | 2.09 |
| bez fizyki + przeszkody | Planner | 500 | 79.4% | 401 | 99.0% | 99 | 0 | 1.89 |
| bez fizyki + przeszkody | Q-Learning (AI) | 500 | 79.6% | 401 | 99.3% | 99 | 0 | 1.91 |
| bez fizyki + przeszkody | Random | 500 | 30.6% | 401 | 38.2% | 99 | 0 | 2.27 |
| bez fizyki + przeszkody | RandomSafe | 500 | 50.6% | 401 | 63.1% | 99 | 0 | 2.38 |
| z fizyką | MonteCarlo | 500 | 75.6% | 400 | 87.5% | 100 | 28 | 2.85 |
| z fizyką | Planner | 500 | 52.2% | 400 | 62.5% | 100 | 11 | 2.70 |
| z fizyką | Q-Learning (AI) | 500 | 66.2% | 400 | 76.0% | 100 | 27 | 2.81 |
| z fizyką | Random | 500 | 12.0% | 400 | 14.0% | 100 | 4 | 2.85 |
| z fizyką | RandomSafe | 500 | 30.6% | 400 | 34.8% | 100 | 14 | 3.33 |
| z fizyką + przeszkody | MonteCarlo | 500 | 82.2% | 433 | 88.0% | 67 | 30 | 2.52 |
| z fizyką + przeszkody | Planner | 500 | 70.6% | 433 | 78.3% | 67 | 14 | 2.35 |
| z fizyką + przeszkody | Q-Learning (AI) | 500 | 73.4% | 433 | 80.8% | 67 | 17 | 2.41 |
| z fizyką + przeszkody | Random | 500 | 17.0% | 433 | 18.7% | 67 | 4 | 2.66 |
| z fizyką + przeszkody | RandomSafe | 500 | 38.8% | 433 | 41.3% | 67 | 15 | 2.98 |

## Q-Learning (AI) - bezpośrednie pojedynki i koszty (wszystkie warianty)

| wariant | para | gry | W | R | P | wygrane | remisy | porażki | decyzja śr. [ms] | CPU/grę [ms] | ops/ruch | RAM śr. [KiB] | kopnięcia/grę |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bez fizyki | Q-Learning (AI) vs Random | 200 | 200 | 0 | 0 | 100.0% | 0.0% | 0.0% | 0.70 | 9.78 | 4.07 | 21941.46 | 0.00 |
| bez fizyki | Q-Learning (AI) vs RandomSafe | 200 | 147 | 53 | 0 | 73.5% | 26.5% | 0.0% | 0.76 | 101.51 | 4.61 | 21943.74 | 0.00 |
| bez fizyki | Q-Learning (AI) vs Planner | 160 | 0 | 157 | 3 | 0.0% | 98.1% | 1.9% | 0.78 | 156.93 | 4.57 | 21933.36 | 0.00 |
| bez fizyki | Q-Learning (AI) vs MonteCarlo | 120 | 4 | 97 | 19 | 3.3% | 80.8% | 15.8% | 0.78 | 139.99 | 4.59 | 21805.82 | 0.00 |
| bez fizyki + przeszkody | Q-Learning (AI) vs Random | 200 | 198 | 1 | 1 | 99.0% | 0.5% | 0.5% | 1.28 | 18.91 | 4.35 | 21557.65 | 0.00 |
| bez fizyki + przeszkody | Q-Learning (AI) vs RandomSafe | 200 | 134 | 27 | 39 | 67.0% | 13.5% | 19.5% | 1.32 | 128.28 | 4.46 | 21611.22 | 0.00 |
| bez fizyki + przeszkody | Q-Learning (AI) vs Planner | 160 | 20 | 87 | 53 | 12.5% | 54.4% | 33.1% | 1.39 | 222.37 | 4.44 | 21516.52 | 0.00 |
| bez fizyki + przeszkody | Q-Learning (AI) vs MonteCarlo | 120 | 4 | 49 | 67 | 3.3% | 40.8% | 55.8% | 1.35 | 185.34 | 4.45 | 21410.03 | 0.00 |
| z fizyką | Q-Learning (AI) vs Random | 200 | 200 | 0 | 0 | 100.0% | 0.0% | 0.0% | 2.10 | 23.69 | 4.16 | 34857.66 | 0.36 |
| z fizyką | Q-Learning (AI) vs RandomSafe | 200 | 166 | 31 | 3 | 83.0% | 15.5% | 1.5% | 1.71 | 206.57 | 4.50 | 34833.72 | 3.80 |
| z fizyką | Q-Learning (AI) vs Planner | 140 | 8 | 118 | 14 | 5.7% | 84.3% | 10.0% | 2.54 | 474.18 | 4.48 | 34673.11 | 8.60 |
| z fizyką | Q-Learning (AI) vs MonteCarlo | 100 | 22 | 57 | 21 | 22.0% | 57.0% | 21.0% | 2.09 | 328.00 | 4.54 | 33488.94 | 5.28 |
| z fizyką + przeszkody | Q-Learning (AI) vs Random | 200 | 199 | 1 | 0 | 99.5% | 0.5% | 0.0% | 3.73 | 44.23 | 4.46 | 34556.00 | 0.44 |
| z fizyką + przeszkody | Q-Learning (AI) vs RandomSafe | 200 | 151 | 19 | 30 | 75.5% | 9.5% | 15.0% | 2.91 | 278.20 | 4.54 | 34514.46 | 3.29 |
| z fizyką + przeszkody | Q-Learning (AI) vs Planner | 140 | 40 | 67 | 33 | 28.6% | 47.9% | 23.6% | 3.82 | 578.40 | 4.47 | 34437.46 | 6.39 |
| z fizyką + przeszkody | Q-Learning (AI) vs MonteCarlo | 100 | 9 | 50 | 41 | 9.0% | 50.0% | 41.0% | 3.48 | 484.18 | 4.57 | 33978.19 | 4.47 |

## Koszty przeciwników w pojedynkach z Q-Learning (AI)

| wariant | bot | rodzina | gry | wygrane | decyzja śr. [ms] | CPU/grę [ms] | ops/ruch | RAM śr. [KiB] |
|---|---|---|---|---|---|---|---|---|
| bez fizyki | MonteCarlo | search | 120 | 15.8% | 29.14 | 5185.21 | 848.23 | 21805.76 |
| bez fizyki | Planner | search | 160 | 1.9% | 0.63 | 127.36 | 11.05 | 21933.36 |
| bez fizyki | Random | random | 200 | 0.0% | 0.18 | 2.43 | 1.00 | 21941.46 |
| bez fizyki | RandomSafe | random | 200 | 0.0% | 0.48 | 62.45 | 3.86 | 21943.74 |
| bez fizyki + przeszkody | MonteCarlo | search | 120 | 55.8% | 55.38 | 7330.60 | 813.97 | 21410.03 |
| bez fizyki + przeszkody | Planner | search | 160 | 33.1% | 1.18 | 188.03 | 10.80 | 21516.52 |
| bez fizyki + przeszkody | Random | random | 200 | 0.5% | 0.20 | 2.91 | 1.00 | 21557.66 |
| bez fizyki + przeszkody | RandomSafe | random | 200 | 19.5% | 0.84 | 75.71 | 3.76 | 21611.22 |
| z fizyką | MonteCarlo | search | 100 | 21.0% | 32.95 | 5120.12 | 789.85 | 33488.94 |
| z fizyką | Planner | search | 140 | 10.0% | 1.15 | 215.02 | 9.71 | 34673.11 |
| z fizyką | Random | random | 200 | 0.0% | 0.18 | 2.06 | 1.00 | 34857.66 |
| z fizyką | RandomSafe | random | 200 | 1.5% | 0.89 | 106.70 | 3.73 | 34833.72 |
| z fizyką + przeszkody | MonteCarlo | search | 100 | 41.0% | 59.39 | 8086.83 | 798.33 | 33978.18 |
| z fizyką + przeszkody | Planner | search | 140 | 23.6% | 1.80 | 276.03 | 10.26 | 34437.46 |
| z fizyką + przeszkody | Random | random | 200 | 0.0% | 0.19 | 2.38 | 1.00 | 34556.00 |
| z fizyką + przeszkody | RandomSafe | random | 200 | 15.0% | 1.39 | 131.03 | 3.75 | 34514.46 |

