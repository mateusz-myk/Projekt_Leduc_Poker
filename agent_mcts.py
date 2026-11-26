import copy
import math
import random

from .engine import (
    SilnikGry,
    Karta,
    LICZBA_RANG,
    LICZBA_KOLOROW,
    SKALA_WYPLAT
)

#------------------------------------------------------------------------------------#

# wezel drzewa: dzieci (po akcji) + statystyki zbiorow informacyjnych
# statystyki[ranga_karty_gracza_na_ruchu][akcja] = [liczba_odwiedzin, suma_nagrod]
class _Wezel:
    __slots__ = ("dzieci", "statystyki")

    def __init__(self):
        self.dzieci = {}
        self.statystyki = {}

#------------------------------------------------------------------------------------#

# Information Set MCTS z determinizacja:
# w kazdej iteracji losujemy ukryte karty zgodne z obserwacja i gramy jedna symulacje.
# Drzewo jest indeksowane publiczna sekwencja akcji, a statystyki kazdego wezla
# sa osobne dla kazdej rangi karty gracza ktory ma ruch (gracz nie wie, co maja inni,
# wiec jego decyzja moze zalezec tylko od jego karty).
class AgentMCTS:
    def __init__(self, ziarno, liczba_iteracji=1000, stala_c=0.5):
        if liczba_iteracji < 1:
            raise ValueError("Liczba iteracji musi byc dodatnia")

        if stala_c < 0:
            raise ValueError("Stala eksploracji nie moze byc ujemna")

        self.generator = random.Random(ziarno)
        self.liczba_iteracji = liczba_iteracji
        self.stala_c = stala_c

    #------------------------------------------------------------------------------------#

    def wybierz_akcje(self, obserwacja, legalne_akcje):
        if len(legalne_akcje) == 1:
            return legalne_akcje[0]

        baza = self._odtworz_stan(obserwacja)
        korzen = _Wezel()
        for _ in range(self.liczba_iteracji):
            gra = self._determinizuj(baza, obserwacja)
            self._iteracja(korzen, gra)

        statystyki = korzen.statystyki[obserwacja.karta_prywatna.ranga]
        najlepsza = None
        najwiecej_odwiedzin = -1
        for akcja in legalne_akcje:
            if statystyki[akcja][0] > najwiecej_odwiedzin:
                najwiecej_odwiedzin = statystyki[akcja][0]
                najlepsza = akcja
        return najlepsza

    #------------------------------------------------------------------------------------#

    # stan gry odtworzony z historii (karty to na razie atrapy)
    def _odtworz_stan(self, obserwacja):
        gra = SilnikGry(0, len(obserwacja.wplaty))
        if obserwacja.karta_wspolna is not None:
            gra.ukryta_karta = obserwacja.karta_wspolna
        for gracz, akcja, runda, do_wyrownania in obserwacja.historia:
            gra.wykonaj_ruch(akcja)
        return gra

    #------------------------------------------------------------------------------------#

    # losowe rozdanie ukrytych kart zgodne z tym co widzi agent
    def _determinizuj(self, baza, obserwacja):
        znane = [(obserwacja.karta_prywatna.ranga, obserwacja.karta_prywatna.kolor)]
        if obserwacja.karta_wspolna is not None:
            znane.append((obserwacja.karta_wspolna.ranga, obserwacja.karta_wspolna.kolor))
        talia = []
        for ranga in range(LICZBA_RANG):
            for kolor in range(LICZBA_KOLOROW):
                if (ranga, kolor) not in znane:
                    talia.append((ranga, kolor))
        self.generator.shuffle(talia)

        gra = copy.copy(baza)
        gra.wplaty = list(baza.wplaty)
        gra.spasowali = list(baza.spasowali)
        gra.zagrali = list(baza.zagrali)
        gra.historia = list(baza.historia)

        karty = []
        indeks = 0
        for i in range(baza.liczba_graczy):
            if i == obserwacja.id_gracza:
                karty.append(obserwacja.karta_prywatna)
            else:
                karty.append(Karta(*talia[indeks]))
                indeks += 1
        gra.karty_prywatne = karty
        if obserwacja.karta_wspolna is None:
            gra.ukryta_karta = Karta(*talia[indeks])
        return gra

    #------------------------------------------------------------------------------------#

    # jedna iteracja: selekcja -> ekspansja -> symulacja -> propagacja wsteczna
    def _iteracja(self, korzen, gra):
        wezel = korzen
        sciezka = [] # (slownik statystyk, akcja, gracz)

        while not gra.koniec:
            gracz = gra.gracz_na_ruchu()
            ranga = gra.karty_prywatne[gracz].ranga
            legalne = gra.legalne_akcje(gracz)
            if ranga not in wezel.statystyki:
                wezel.statystyki[ranga] = {a: [0, 0.0] for a in legalne}
            statystyki = wezel.statystyki[ranga]

            nieprobowane = [a for a in legalne if statystyki[a][0] == 0]
            if nieprobowane:
                akcja = self.generator.choice(nieprobowane)
                rozszerzono = True
            else:
                akcja = self._wybierz_ucb(statystyki, legalne)
                rozszerzono = False

            sciezka.append((statystyki, akcja, gracz))
            runda_przed = gra.numer_rundy
            gra.wykonaj_ruch(akcja)

            # po odkryciu karty wspolnej drzewo sie rozgalezia (wezel losowy)
            klucz = akcja
            if not gra.koniec and gra.numer_rundy != runda_przed:
                klucz = (akcja, gra.karta_wspolna.ranga)
            if klucz not in wezel.dzieci:
                wezel.dzieci[klucz] = _Wezel()
            wezel = wezel.dzieci[klucz]

            if rozszerzono:
                break

        # symulacja losowa do konca rozdania
        while not gra.koniec:
            gracz = gra.gracz_na_ruchu()
            gra.wykonaj_ruch(self.generator.choice(gra.legalne_akcje(gracz)))

        # propagacja: kazdy gracz dostaje swoja wyplate
        for statystyki, akcja, gracz in sciezka:
            wpis = statystyki[akcja]
            wpis[0] += 1
            wpis[1] += float(gra.wyplaty[gracz]) / SKALA_WYPLAT

    #------------------------------------------------------------------------------------#

    def _wybierz_ucb(self, statystyki, legalne):
        lacznie = sum(statystyki[a][0] for a in legalne)
        najlepsza = None
        najlepsza_wartosc = -float("inf")
        for akcja in legalne:
            odwiedziny, suma = statystyki[akcja]
            wartosc = suma / odwiedziny + self.stala_c * math.sqrt(math.log(lacznie) / odwiedziny)
            if wartosc > najlepsza_wartosc:
                najlepsza_wartosc = wartosc
                najlepsza = akcja
        return najlepsza

#------------------------------------------------------------------------------------#