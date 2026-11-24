# Holo – interaktywna holograficzna Droga Mleczna

Program na Raspberry Pi wyświetlający **Drogę Mleczną** do projekcji „holograficznej”:
ekran leży na dole, a obraz odbija się w plexi ustawionym pod kątem 45° (efekt
**Pepper's ghost**). Widz wybiera myszą obiekty, a kamera płynnie do nich podlatuje
i pokazuje kartę z prawdziwymi parametrami.

![podgląd](docs/preview.png)

## Co jest w środku

- **Droga Mleczna** – 20 000 gwiazd: poprzeczka, 4 ramiona spiralne, Ramię Oriona ze
  Słońcem, pasy pyłu, różowe obszary narodzin gwiazd.
- **Sagittarius A\*** – animowana czarna dziura w centrum (dysk akrecyjny, pierścień
  fotonowy, soczewkowanie).
- **Trzy poziomy**: Droga Mleczna → Okolica Słońca → Układ Słoneczny.
  Klikasz Słońce dwa razy, żeby zejść poziom niżej.
- **28 obiektów** z prawdziwymi danymi: mgławice (Carina, Orzeł, Laguna, Oriona), gromady
  (Omega Centauri, M13, Plejady), gwiazdy (Syriusz, Betelgeza, Rigel, Proxima…), planety.
- **Tryb pokazowy** – po minucie bez ruchu myszy program sam oprowadza po obiektach.

## Obsługa

| Akcja | Działanie |
|---|---|
| lewy przycisk na obiekcie | wybór: przybliżenie i karta z parametrami |
| ponowne kliknięcie (Słońce) | wejście poziom niżej |
| klik w pustą przestrzeń | odznaczenie |
| prawy przycisk / `Esc` | wstecz |
| kółko myszy | przybliżanie / oddalanie |
| `c` | ekran kalibracji odbicia (`h`, `v` – odbicia) |
| `spacja` | pauza |
| `+` / `-` | prędkość animacji |
| `g` | poświata wł./wył. |
| `f` | licznik FPS |
| `q` | wyjście |

## Uruchomienie na komputerze (do testów)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m holo --windowed
```

## Uruchomienie na Raspberry Pi

```bash
sudo apt update
sudo apt install -y git python3-pygame python3-numpy
git clone https://github.com/Dnsflr/holo.git
cd holo
python3 -m holo --calibrate
```

Na ekranie kalibracji wciskaj `h` / `v`, aż napisy w odbiciu na plexi będą czytelne.
Program pokaże opcje, z którymi trzeba go potem uruchamiać (np. `--flip-v`).

Jeśli animacja jest za wolna (sprawdź klawiszem `f`), zmniejsz obciążenie:

```bash
python3 -m holo --flip-v --render-scale 0.4 --stars 12000
```

## Opcje

`python3 -m holo --help` pokazuje wszystkie. Najważniejsze:

| Opcja | Opis |
|---|---|
| `--flip-h`, `--flip-v` | odbicie obrazu pod plexi (ustal przez `--calibrate`) |
| `--stars 20000` | liczba gwiazd galaktyki |
| `--render-scale 0.5` | rozdzielczość renderowania gwiazd (mniej = szybciej) |
| `--tour-after 60` | po ilu sekundach bezczynności startuje tryb pokazowy (0 = nigdy) |
| `--windowed` | okno zamiast pełnego ekranu |

## Własne obiekty

Wszystkie obiekty i ich opisy są w pliku `holo/data/milky_way.json`. Możesz dopisać
nowy, kopiując istniejący wpis i zmieniając jego `id`, nazwę, pozycję i parametry.
Pozycję w galaktyce podaje się we współrzędnych galaktycznych (`l`, `b` w stopniach)
i odległości w kiloparsekach (`dist_kpc`, 1 kpc ≈ 3 260 lat świetlnych) – takie dane
znajdziesz w Wikipedii przy każdym obiekcie.

## Testy

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

## Struktura kodu

```
holo/
  main.py       – pętla główna, nawigacja (wybór, przejścia między poziomami, tryb pokazowy)
  levels.py     – poziomy: Droga Mleczna, Okolica Słońca, Układ Słoneczny
  galaxy.py     – generator Drogi Mlecznej
  blackhole.py  – animacja Sagittarius A*
  catalog.py    – wczytywanie katalogu obiektów, przeliczanie współrzędnych
  camera.py     – kamera 3D z płynnymi lotami
  render.py     – szybkie rysowanie gwiazd (numpy) i poświata
  sprites.py    – obrazki gwiazd, mgławic, gromad, planet
  ui.py         – kursor, karta informacji, podpisy, kalibracja
  picking.py    – wybór obiektu kursorem
  output.py     – odbicie obrazu pod plexi
  data/milky_way.json – katalog obiektów
```
