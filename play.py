import argparse
import os
import sys
import random

from fractions import Fraction

from .engine import (
    SilnikGry,
    MIN_GRACZY,
    MAX_GRACZY
)

from .render import (
    rysuj_stol,
    rysuj_showdown,
    rysuj_przekazanie,
    formatuj_wyplate
)

from .agents import AgentLosowy, AgentHeurystyczny
from .agent_mcts import AgentMCTS
from .agent_reinforce import AgentReinforce

#------------------------------------------------------------------------------------#

def wyczysc_ekran():
    os.system("cls" if os.name == "nt" else "clear")

#------------------------------------------------------------------------------------#

# zamiana tekstu "1,2" na liste [1, 2]

def wczytaj_miejsca_ai(tekst):
    miejsca = []
    if tekst != "":
        for fragment in tekst.split(","):
            miejsca.append(int(fragment))
    return miejsca


#------------------------------------------------------------------------------------#

def stworz_agenta(typ, ziarno, iteracje_mcts):
    if typ == "losowy":
        return AgentLosowy(ziarno)

    if typ == "mcts":
        return AgentMCTS(ziarno, iteracje_mcts)

    if typ == "reinforce":
        return AgentReinforce(ziarno, "reinforce.pt")

    if typ == "heurystyczny":
        return AgentHeurystyczny()

    raise ValueError(f"nieznany typ agenta: {typ}")

#------------------------------------------------------------------------------------#

# rozegranie sesji z ludzmi i agentami

def graj(liczba_graczy, ziarno, debug, przydzial, ziarno_agentow, bez_pauz, iteracje_mcts):
    if ziarno_agentow is None:
        ziarno_agentow = ziarno
    sys.stdout.reconfigure(encoding="utf-8") # zeby dzialaly symbole kart

    miejsca_ai = sorted(przydzial)
    miejsca_ludzi = []
    for i in range(liczba_graczy):
        if i not in miejsca_ai:
            miejsca_ludzi.append(i)
    tryb_obserwatora = len(miejsca_ludzi) == 0

    wyniki_sesji = [Fraction(0)] * liczba_graczy
    numer_rozdania = 0
    ostatnia_gra = None
    try:
        while True:
            gra = SilnikGry(ziarno + numer_rozdania, liczba_graczy)
            ostatnia_gra = gra

            # kazdy agent dostaje inne ziarno
            agenci = {}
            for miejsce, typ in przydzial.items():
                ziarno_ag = ziarno_agentow + numer_rozdania * 10 + miejsce
                agenci[miejsce] = stworz_agenta(typ, ziarno_ag, iteracje_mcts)
            oczekujace_linie = []

            # kolejne tury
            while not gra.koniec:
                id_gracza = gra.gracz_na_ruchu()
                obserwacja = gra.obserwuj(id_gracza)
                legalne_akcje = gra.legalne_akcje(id_gracza)

                # tura agenta
                if id_gracza in agenci:
                    if tryb_obserwatora:
                        wyczysc_ekran()
                        print(rysuj_stol(obserwacja, gra, miejsca_ai, debug))
                    do_wyrownania = gra.do_wyrownania(id_gracza)
                    akcja = agenci[id_gracza].wybierz_akcje(obserwacja, legalne_akcje)
                    gra.wykonaj_ruch(akcja)
                    if akcja == "call" and do_wyrownania == 0:
                        akcja = "check"
                    wiersz = f"Gracz {id_gracza} (AI): {akcja}"
                    if tryb_obserwatora:
                        print(wiersz)
                        if not bez_pauz:
                            input("Enter — nastepna akcja")
                    else:
                        oczekujace_linie.append(wiersz)
                    continue

                # tura czlowieka
                wyczysc_ekran()
                if len(miejsca_ludzi) > 1:
                    print(rysuj_przekazanie(id_gracza))
                    input()
                    wyczysc_ekran()
                for wiersz in oczekujace_linie:
                    print(wiersz)
                oczekujace_linie = []
                print(rysuj_stol(obserwacja, gra, miejsca_ai, debug))
                skroty = {"f": "fold", "c": "call", "r": "raise"}
                while True:
                    wpisane = input(" Akcja: ").strip().lower()
                    akcja = skroty.get(wpisane, wpisane)
                    if akcja in legalne_akcje:
                        break
                    print("Nielegalna akcja")
                gra.wykonaj_ruch(akcja)

            # podsumowanie rozdania
            for wiersz in oczekujace_linie:
                print(wiersz)
            print(f"Rozdanie {numer_rozdania + 1}")
            print(rysuj_showdown(gra, debug))
            if len(miejsca_ludzi) > 0:
                opis = ""
                for i in miejsca_ludzi:
                    wyniki_sesji[i] += gra.wyplaty[i]
                    opis += f"Gracz {i}: {formatuj_wyplate(wyniki_sesji[i])}, "
                print("Wynik sesji: " + opis[:-2])
            numer_rozdania += 1
            if input("Kolejne rozdanie? [t/N] ").strip().lower() != "t":
                return ostatnia_gra
    except KeyboardInterrupt:
        print("\nSesja przerwana.")
        return ostatnia_gra

#------------------------------------------------------------------------------------#

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--players", type=int, choices=range(MIN_GRACZY, MAX_GRACZY + 1), default=MAX_GRACZY)
    parser.add_argument("--seed", dest="ziarno", type=int, default=None)
    parser.add_argument("--agent-seed", dest="ziarno_agentow", type=int, default=None)
    parser.add_argument("--no-pause", dest="bez_pauz", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--random-seats", default="")
    parser.add_argument("--mcts-seats", default="")
    parser.add_argument("--ai-seats", default="")  # stare: te miejsca = losowi, jesli nie przypisano inaczej
    parser.add_argument("--mcts-iters", type=int, default=1000)
    parser.add_argument("--reinforce-seats", default="")
    parser.add_argument("--heuristic-seats", default="")
    argumenty = parser.parse_args()

    przydzial = {}
    for typ, tekst in [
    ("losowy", argumenty.random_seats),
    ("mcts", argumenty.mcts_seats),
    ("reinforce", argumenty.reinforce_seats),
    ("heurystyczny", argumenty.heuristic_seats)
]:
        for miejsce in wczytaj_miejsca_ai(tekst):
            if miejsce in przydzial:
                parser.error(f"miejsce {miejsce} przypisane do dwoch typow agentow")
            przydzial[miejsce] = typ
    for miejsce in wczytaj_miejsca_ai(argumenty.ai_seats):
        przydzial.setdefault(miejsce, "losowy")
    for miejsce in przydzial:
        if not 0 <= miejsce < argumenty.players:
            parser.error(f"miejsce {miejsce} poza zakresem 0..{argumenty.players - 1}")

    # czyli z: "--players 4 --random-seats 0 --mcts-seats 1,2" robi: random_seats = "0", mcts_seats = "1,2", ai_seats = "" 
    # czyli {0: "losowy", 1: "mcts", 2: "mcts"}.

    ziarno = argumenty.ziarno
    if ziarno is None:
        ziarno = random.randint(0, 999999)

    graj(argumenty.players, ziarno, argumenty.debug, przydzial,
         argumenty.ziarno_agentow, argumenty.bez_pauz, argumenty.mcts_iters)

if __name__ == "__main__":
    main()
