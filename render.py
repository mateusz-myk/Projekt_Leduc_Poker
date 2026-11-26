SYMBOLE_KOLOROW = ["♡", "♧", "♢"]
RANGI = "JQK"
SZEROKOSC_EKRANU = 60

MAKS_PODBIC_W_RUNDZIE = 2
ROZMIARY_ZAKLADOW = (2, 4)
LICZBA_RANG = 3
LICZBA_KOLOROW = 3
ANTE = 1
MAX_GRACZY = 3

SKALA_WYPLAT = float(
    ANTE + MAKS_PODBIC_W_RUNDZIE * sum(ROZMIARY_ZAKLADOW)
)

#------------------------------------------------------------------------------------#

def karta_kompaktowa(karta):
    if karta is None:
        return "[??]"
    return "[" + RANGI[karta.ranga] + SYMBOLE_KOLOROW[karta.kolor] + "]"

#------------------------------------------------------------------------------------#

def rysuj_karte(karta):
    if karta is None:
        return "+-----+\n| ? ? |\n|  ?  |\n| ? ? |\n+-----+"
    ranga = RANGI[karta.ranga]
    kolor = SYMBOLE_KOLOROW[karta.kolor]
    return ("+-----+\n"
            f"| {ranga}   |\n"
            f"|  {kolor}  |\n"
            f"|   {ranga} |\n"
            "+-----+")

#------------------------------------------------------------------------------------#

# historia ruchow, zawijana zeby sie miescila na ekranie
def historia_tekst(gra, miejsca_ai):
    if len(gra.historia) == 0:
        return ["  (brak akcji)"]
    wynik = []
    for numer_rundy in [1, 2]:
        opisy = []
        for id_gracza, akcja, runda, do_wyrownania in gra.historia:
            if runda != numer_rundy:
                continue
            if akcja == "call" and do_wyrownania == 0:
                akcja = "check"
            if id_gracza in miejsca_ai:
                opisy.append(f"Gracz {id_gracza} (AI): {akcja}")
            else:
                opisy.append(f"Gracz {id_gracza}: {akcja}")
        if len(opisy) == 0:
            continue
        wiersz = f"  R{numer_rundy}: " + opisy[0]
        for opis in opisy[1:]:
            if len(wiersz) + 2 + len(opis) > SZEROKOSC_EKRANU:
                wynik.append(wiersz)
                wiersz = "       " + opis
            else:
                wiersz += ", " + opis
        wynik.append(wiersz)
    return wynik

#------------------------------------------------------------------------------------#

# rysowanie stolu z perspektywy jednego gracza
def rysuj_stol(obserwacja, gra, miejsca_ai, debug):
    karta_wspolna = rysuj_karte(obserwacja.karta_wspolna).split("\n")
    karta_gracza = rysuj_karte(obserwacja.karta_prywatna).split("\n")
    linie = []
    linie.append("=" * SZEROKOSC_EKRANU)
    linie.append(f" LEDUC | R{obserwacja.numer_rundy}/2 | Zaklad {gra.rozmiar_zakladu} | "
                 f"Pula {obserwacja.pula} | Podbicia: {gra.liczba_podbic}/2")
    linie.append("=" * SZEROKOSC_EKRANU)
    linie.append(" KARTA WSPOLNA          TWOJA KARTA (Gracz " + str(obserwacja.id_gracza) + ")")
    for i in range(5):
        linie.append(" " + karta_wspolna[i] + "                " + karta_gracza[i])

    # tabela graczy
    linie.append("-" * SZEROKOSC_EKRANU)
    linie.append(f"  {'Gracz':<14} {'Wplacono':>6}  {'Status':<8}  Karta")
    for i in range(gra.liczba_graczy):
        znacznik = " "
        if i == obserwacja.gracz_na_ruchu:
            znacznik = ">"
        status = "aktywny"
        if obserwacja.spasowali[i]:
            status = "FOLD"
        etykieta = f"Gracz {i}:"
        if i in miejsca_ai:
            etykieta = f"Gracz {i} (AI):"
        if debug:
            karta = karta_kompaktowa(gra.karty_prywatne[i])
        elif obserwacja.spasowali[i]:
            karta = "[--]"
        elif i == obserwacja.id_gracza:
            karta = karta_kompaktowa(obserwacja.karta_prywatna)
        else:
            karta = "[??]"
        linie.append(f"{znacznik} {etykieta:<14} {obserwacja.wplaty[i]:>6}  {status:<8}  {karta}")

    # historia
    linie.append("-" * SZEROKOSC_EKRANU)
    linie.append(" Historia:")
    linie += historia_tekst(gra, miejsca_ai)

    # dostepne akcje
    linie.append("-" * SZEROKOSC_EKRANU)
    do_wyrownania = obserwacja.do_wyrownania()
    opis = f" Do wyrownania: {do_wyrownania} zetonow"
    if do_wyrownania == 0:
        opis += " (mozesz czekac)"
    linie.append(opis)
    if do_wyrownania > 0:
        akcje = f" [f] fold (0)   [c] call (+{do_wyrownania})"
    else:
        akcje = " [c] check (0)"
    if gra.liczba_podbic < MAKS_PODBIC_W_RUNDZIE:
        akcje += f"   [r] raise (+{do_wyrownania + gra.rozmiar_zakladu})"
    linie.append(akcje)
    return "\n".join(linie)

#------------------------------------------------------------------------------------#

def rysuj_przekazanie(id_gracza):
    return f"Teraz Gracz {id_gracza} — naciśnij Enter"

#------------------------------------------------------------------------------------#

# wyplata ze znakiem, np. +3 albo -1/2
def formatuj_wyplate(wyplata):
    znak = "+"
    if wyplata < 0:
        znak = "-"
    kwota = abs(wyplata)
    if kwota.denominator == 1: # mianownik = 1
        return znak + str(kwota.numerator) # liczba całk
    return f"{znak}{kwota.numerator}/{kwota.denominator}"

#------------------------------------------------------------------------------------#

# ekran na koniec rozdania
def rysuj_showdown(gra, debug=False):
    aktywni = []
    for i in range(gra.liczba_graczy):
        if not gra.spasowali[i]:
            aktywni.append(i)

    linie = ["SHOWDOWN"]
    if len(aktywni) == 1:
        zwyciezcy = aktywni
        linie.append("Koniec po foldzie")
        linie.append(f"Wygrywa: Gracz {zwyciezcy[0]}")
    else:
        zwyciezcy = gra.zwyciezcy(aktywni)
        linie.append("Karta wspolna: " + karta_kompaktowa(gra.karta_wspolna))
        if len(zwyciezcy) > 1:
            opis = ""
            for i in zwyciezcy:
                opis += f"Gracz {i}, "
            linie.append("Remis: " + opis + "podzial puli po rowno")
        else:
            linie.append(f"Wygrywa: Gracz {zwyciezcy[0]}")

    # wiersz dla kazdego gracza
    for i in range(gra.liczba_graczy):
        karta = ""
        etykieta = ""
        if gra.spasowali[i]:
            status = "FOLD"
            if debug:
                karta = karta_kompaktowa(gra.karty_prywatne[i])
        elif len(aktywni) == 1:
            status = "AKTYWNY"
        else:
            ranga = gra.karty_prywatne[i].ranga
            karta = karta_kompaktowa(gra.karty_prywatne[i])
            if ranga == gra.karta_wspolna.ranga:
                status = f"PARA ({RANGI[ranga]})"
            else:
                status = f"wysoka karta ({RANGI[ranga]})"
        if i in zwyciezcy:
            etykieta = "WYGRYWA"
            if len(zwyciezcy) > 1:
                etykieta = "REMIS"
        linie.append(f"Gracz {i}: {karta:<6} {status:<20} {etykieta:<9} "
                     f"{formatuj_wyplate(gra.wyplaty[i])}")

    linie.append("Suma wyplat: " + str(sum(gra.wyplaty)))
    opis = ""
    for i in range(gra.liczba_graczy):
        opis += f"Gracz {i}: {formatuj_wyplate(gra.wyplaty[i])}, "
    linie.append("Wyplaty: " + opis[:-2])
    return "\n".join(linie)