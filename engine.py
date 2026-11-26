import random
from fractions import Fraction

#------------------------------------------------------------------------------------#

LICZBA_RANG = 3
LICZBA_KOLOROW = 3

MIN_GRACZY = 2
MAX_GRACZY = 3

ANTE = 1
MAKS_PODBIC_W_RUNDZIE = 2
ROZMIARY_ZAKLADOW = (2, 4)
LICZBA_RUND = len(ROZMIARY_ZAKLADOW)

AKCJE = ["fold", "call", "raise"]

SKALA_WYPLAT = float(
    ANTE + MAKS_PODBIC_W_RUNDZIE * sum(ROZMIARY_ZAKLADOW)
)

#------------------------------------------------------------------------------------#

class Karta:
    def __init__(self, ranga, kolor):
        self.ranga = ranga
        self.kolor = kolor

#------------------------------------------------------------------------------------#

# to co widzi jeden gracz (bez cudzych kart)
class Obserwacja:
    def __init__(self, id_gracza, karta_prywatna, karta_wspolna, pula, wplaty,
                 spasowali, numer_rundy, historia, gracz_na_ruchu):
        self.id_gracza = id_gracza
        self.karta_prywatna = karta_prywatna
        self.karta_wspolna = karta_wspolna # w pierwszej rundzie None
        self.pula = pula
        self.wplaty = wplaty
        self.spasowali = spasowali
        self.numer_rundy = numer_rundy
        self.historia = historia
        self.gracz_na_ruchu = gracz_na_ruchu

    # ile trzeba dolozyc zeby wyrownac
    def do_wyrownania(self):
        najwyzsza = 0
        for i in range(len(self.wplaty)):
            if not self.spasowali[i] and self.wplaty[i] > najwyzsza:
                najwyzsza = self.wplaty[i]
        return najwyzsza - self.wplaty[self.id_gracza]

#------------------------------------------------------------------------------------#

class SilnikGry:
    # nowe rozdanie
    def __init__(self, ziarno=0, liczba_graczy=MAX_GRACZY):
        if not MIN_GRACZY <= liczba_graczy <= MAX_GRACZY:
            raise ValueError("Nieprawidlowa liczba graczy")

        self.liczba_graczy = liczba_graczy
        generator = random.Random(ziarno)

        talia = []
        for ranga in range(LICZBA_RANG):
            for kolor in range(LICZBA_KOLOROW):
                talia.append(Karta(ranga, kolor))

        generator.shuffle(talia)

        self.karty_prywatne = talia[:liczba_graczy]
        self.karta_wspolna = None
        self.ukryta_karta = talia[liczba_graczy]

        self.wplaty = [ANTE] * liczba_graczy
        self.pula = ANTE * liczba_graczy
        self.spasowali = [False] * liczba_graczy
        self.numer_rundy = 1
        self.rozmiar_zakladu = ROZMIARY_ZAKLADOW[0]
        self.liczba_podbic = 0
        self.zagrali = []
        self.aktualny = 0
        self.historia = [] # (gracz, akcja, numer rundy, ile bylo do wyrownania)
        self.koniec = False
        self.wyplaty = None

    #------------------------------------------------------------------------------------#

    # co moze zagrac gracz
    def legalne_akcje(self, id_gracza):
        akcje = ["call"]
        if self.do_wyrownania(id_gracza) > 0:
            akcje.insert(0, "fold")
        if self.liczba_podbic < MAKS_PODBIC_W_RUNDZIE:
            akcje.append("raise")
        return akcje

    #------------------------------------------------------------------------------------#

    def obserwuj(self, id_gracza):
        return Obserwacja(
            id_gracza,
            self.karty_prywatne[id_gracza],
            self.karta_wspolna,
            self.pula,
            self.wplaty.copy(),
            self.spasowali.copy(),
            self.numer_rundy,
            self.historia.copy(),
            self.aktualny
        )

    #------------------------------------------------------------------------------------#

    # wykonanie ruchu
    def wykonaj_ruch(self, akcja):
        gracz = self.aktualny

        if self.koniec:
            raise ValueError("Rozdanie jest zakonczone")

        if akcja not in self.legalne_akcje(gracz):
            raise ValueError("Nielegalna akcja")
        
        self.historia.append((gracz, akcja, self.numer_rundy, self.do_wyrownania(gracz)))

        if akcja == "fold":
            self.spasowali[gracz] = True
        elif akcja == "call":
            kwota = self.do_wyrownania(gracz)
            self.wplaty[gracz] += kwota
            self.pula += kwota
        elif akcja == "raise":
            kwota = self.do_wyrownania(gracz) + self.rozmiar_zakladu
            self.wplaty[gracz] += kwota
            self.pula += kwota
            self.liczba_podbic += 1
            self.zagrali = []
        self.zagrali.append(gracz)

        # kto jeszcze gra
        aktywni = []
        for i in range(self.liczba_graczy):
            if not self.spasowali[i]:
                aktywni.append(i)

        # wszyscy spasowali oprocz jednego
        if len(aktywni) == 1:
            self.zakoncz_rozdanie(aktywni)
            return

        # sprawdzam czy runda sie skonczyla
        najwyzsza = self.najwyzsza_wplata()
        koniec_rundy = True
        for i in aktywni:
            if i not in self.zagrali or self.wplaty[i] != najwyzsza:
                koniec_rundy = False

        if koniec_rundy:
            if self.numer_rundy == 1:
                # druga runda
                self.numer_rundy = 2
                self.rozmiar_zakladu = ROZMIARY_ZAKLADOW[1]
                self.liczba_podbic = 0
                self.zagrali = []
                self.karta_wspolna = self.ukryta_karta
                self.aktualny = min(aktywni)
            else:
                self.zakoncz_rozdanie(self.zwyciezcy(aktywni))
        else:
            self.aktualny = self.nastepny_gracz(aktywni)

    #------------------------------------------------------------------------------------#

    # nastepny aktywny gracz ktory jeszcze nie zagral
    def nastepny_gracz(self, aktywni):
        for przesuniecie in range(1, self.liczba_graczy + 1):
            kandydat = (self.aktualny + przesuniecie) % self.liczba_graczy
            if kandydat in aktywni and kandydat not in self.zagrali:
                return kandydat

    #------------------------------------------------------------------------------------#

    # wygrywa para ze wspolna karta, potem wyzsza ranga
    def zwyciezcy(self, aktywni):
        oceny = {}
        for i in aktywni:
            ranga = self.karty_prywatne[i].ranga
            para = 0
            if ranga == self.karta_wspolna.ranga:
                para = 1
            oceny[i] = (para, ranga)
        najlepsza = max(oceny.values())
        wygrani = []
        for i in aktywni:
            if oceny[i] == najlepsza:
                wygrani.append(i)
        return wygrani

    #------------------------------------------------------------------------------------#

    # podzial puli
    def zakoncz_rozdanie(self, zwyciezcy):
        udzial = Fraction(self.pula, len(zwyciezcy))
        wyplaty = []
        for i in range(self.liczba_graczy):
            if i in zwyciezcy:
                wyplaty.append(udzial - self.wplaty[i])
            else:
                wyplaty.append(Fraction(-self.wplaty[i]))
        self.wyplaty = wyplaty
        self.koniec = True

    #------------------------------------------------------------------------------------#

    def najwyzsza_wplata(self):
        najwyzsza = 0
        for i in range(self.liczba_graczy):
            if not self.spasowali[i] and self.wplaty[i] > najwyzsza:
                najwyzsza = self.wplaty[i]
        return najwyzsza

    #------------------------------------------------------------------------------------#

    def do_wyrownania(self, id_gracza):
        return self.najwyzsza_wplata() - self.wplaty[id_gracza]

    #------------------------------------------------------------------------------------#

    def gracz_na_ruchu(self):
        if self.koniec:
            return None
        return self.aktualny

    #------------------------------------------------------------------------------------#