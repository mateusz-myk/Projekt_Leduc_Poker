import argparse
import itertools
import math
import statistics
import time

from .engine import SilnikGry
from .agents import AgentLosowy
from .agent_mcts import AgentMCTS
from .agent_reinforce import AgentReinforce

NAZWY = ["losowy", "mcts", "reinforce"]
ZIARNO_BAZOWE_GIER = 20_000_000  # wysokie aby nie pokrywało się z testami


def stworz_agentow(ziarno, iteracje_mcts, sciezka_modelu, zachlannie):
    return {
        "losowy": AgentLosowy(ziarno + 1),
        "mcts": AgentMCTS(ziarno + 2, iteracje_mcts),
        "reinforce": AgentReinforce(ziarno + 3, sciezka_modelu, zachlannie),
    }


def rozegraj_turniej(agenci, liczba_rozdan, ziarno):
    permutacje = list(itertools.permutations(NAZWY))  # 6 ustawien miejsc
    wyplaty = {nazwa: [] for nazwa in NAZWY}          # wyplata w kazdym rozdaniu
    czasy = {nazwa: 0.0 for nazwa in NAZWY}           # suma czasu decyzji
    decyzje = {nazwa: 0 for nazwa in NAZWY}           # liczba decyzji (bez wymuszonych)
    t_start = time.time()

    for r in range(liczba_rozdan):
        ustawienie = permutacje[r % len(permutacje)]  # ustawienie[miejsce] = nazwa agenta
        gra = SilnikGry(ziarno + r, 3)

        while not gra.koniec:
            g = gra.gracz_na_ruchu()
            nazwa = ustawienie[g]
            obs = gra.obserwuj(g)
            leg = gra.legalne_akcje(g)

            t0 = time.perf_counter()
            akcja = agenci[nazwa].wybierz_akcje(obs, leg)
            dt = time.perf_counter() - t0
            if len(leg) > 1:  # wymuszone ruchy nie sa decyzjami
                czasy[nazwa] += dt
                decyzje[nazwa] += 1
            gra.wykonaj_ruch(akcja)

        for miejsce, nazwa in enumerate(ustawienie):
            wyplaty[nazwa].append(float(gra.wyplaty[miejsce]))

        if (r + 1) % 60 == 0 or r + 1 == liczba_rozdan:
            uplynelo = time.time() - t_start
            srednie = "  ".join(f"{n}: {statistics.mean(wyplaty[n]):+.3f}" for n in NAZWY)
            print(f"  rozdanie {r + 1}/{liczba_rozdan} ({uplynelo:.0f}s)  {srednie}")

    return wyplaty, czasy, decyzje

# rozegraj_turniej gra zadaną liczbę rozdań, w których zawsze siedzą trzej gracze: losowy, MCTS i REINFORCE. 
# Kolejne rozdania biorą kolejne z 6 możliwych ustawień miejsc (r % 6), więc każdy agent siedzi na każdym miejscu tyle samo razy, 
# a przewaga pozycji się wyrównuje.

# w trakcie gry funkcja pyta agenta stojącego na ruchu o akcję i mierzy, ile to trwało. 
# Czas i liczbę decyzji zlicza tylko wtedy, gdy miał realny wybór stąd potem wychodzi “ms/decyzja”. 
# Po rozdaniu zapisuje wypłatę każdego agenta pod jego nazwą, a co 60 rozdań drukuje postęp i bieżące średnie.

# Zwraca trzy słowniki: wypłaty z każdego rozdania, sumy czasów i liczby decyzji. 
# Z nich drukuj_wyniki liczy średnie, przedziały ufności i porównania.

def blad_standardowy(x):
    if len(x) < 2:
        return float("nan")
    return statistics.stdev(x) / math.sqrt(len(x))

# SE = sd / sqrt(n)


def drukuj_wyniki(wyplaty, czasy, decyzje):
    n = len(wyplaty[NAZWY[0]])
    print("\n" + "=" * 72)
    print(f"WYNIKI ({n} rozdan, kazdy agent gral w kazdym rozdaniu)")
    print("=" * 72)
    print(f"{'agent':<11} {'sr. wyplata':>12} {'+-95% CI':>10} {'suma':>9} "
          f"{'ms/decyzja':>11} {'decyzji':>8}")
    for nazwa in NAZWY:
        w = wyplaty[nazwa]
        sr = statistics.mean(w)
        ci = 1.96 * blad_standardowy(w)
        ms = 1000 * czasy[nazwa] / decyzje[nazwa] if decyzje[nazwa] else float("nan")
        print(f"{nazwa:<11} {sr:>+12.3f} {ci:>10.3f} {sum(w):>+9.1f} "
              f"{ms:>11.3f} {decyzje[nazwa]:>8}")

    suma_srednich = sum(statistics.mean(wyplaty[nz]) for nz in NAZWY)
    print(f"\nKontrola zero-sumowosci: suma srednich wyplat = {suma_srednich:+.6f} (powinno byc 0)")

    # test sparowany: rozdania sa te same, wiec roznice wyplat maja mniejsza wariancje
    print("\nPorownania parami (sredna roznica wyplat na rozdanie, test sparowany):")
    for a, b in [("reinforce", "mcts"), ("reinforce", "losowy"), ("mcts", "losowy")]:
        roznice = [x - y for x, y in zip(wyplaty[a], wyplaty[b])]
        sr = statistics.mean(roznice)
        ci = 1.96 * blad_standardowy(roznice)
        werdykt = "istotnie lepszy" if sr - ci > 0 else ("istotnie gorszy" if sr + ci < 0 else "brak istotnej roznicy")
        print(f"  {a} - {b}: {sr:+.3f} +-{ci:.3f}  -> {a} {werdykt}")

    if all(decyzje[nz] for nz in ("mcts", "reinforce")) and czasy["reinforce"] > 0:
        ratio = (czasy["mcts"] / decyzje["mcts"]) / (czasy["reinforce"] / decyzje["reinforce"])
        print(f"\nKoszt decyzji: MCTS jest srednio ~{ratio:.0f}x wolniejszy od REINFORCE.")

#drukuj_wyniki bierze dane z turnieju i drukuje z nich czytelne podsumowanie w trzech częściach. 
# Najpierw tabela: dla każdego agenta średnia wypłata na rozdanie, 95% przedział ufności (1.96 · błąd standardowy), 
# suma żetonów, średni czas jednej decyzji w ms i liczba decyzji.

#Potem kontrola zero-sumowości (suma średnich wszystkich agentów powinna wynosić 0, bo ile ktoś wygrał, tyle ktoś przegrał)
#  oraz porównania parami. Dla każdej pary (np. REINFORCE vs MCTS) liczy różnicę wypłat w każdym rozdaniu, czyli na tych samych 
# kartach, i z tych różnic średnią i przedział ufności.

# Werdykt jest prosty: jeśli cały przedział leży nad zerem, pierwszy agent 
# jest “istotnie lepszy”, jeśli pod zerem, “istotnie gorszy”, a jeśli przedział obejmuje zero, “brak istotnej różnicy”.

#Na końcu drukuje, ile razy MCTS jest wolniejszy od REINFORCE na decyzję.


def rysuj_wykres(wyplaty, sciezka_png):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("Brak matplotlib (pip install matplotlib) - pomijam wykres.")
        return
    plt.figure(figsize=(8, 5))
    for nazwa in NAZWY:
        w = wyplaty[nazwa]
        biezaca, suma = [], 0.0
        for i, x in enumerate(w, 1):
            suma += x
            biezaca.append(suma / i)
        plt.plot(range(1, len(w) + 1), biezaca, label=nazwa)
    plt.axhline(0, color="gray", linewidth=0.8)
    plt.xlabel("liczba rozdan")
    plt.ylabel("srednia wyplata na rozdanie (zetony)")
    plt.title("Turniej 3-osobowy: losowy vs MCTS vs REINFORCE")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(sciezka_png, dpi=150)
    print(f"Wykres zapisany: {sciezka_png}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rozdan", type=int, default=1200)
    parser.add_argument("--mcts-iters", type=int, default=1000)
    parser.add_argument("--model", default="reinforce.pt")
    parser.add_argument("--zachlannie", action="store_true")
    parser.add_argument("--seed", type=int, default=0, help="ziarno agentow")
    parser.add_argument("--wykres", action="store_true")
    args = parser.parse_args()

    liczba_rozdan = math.ceil(args.rozdan / 6) * 6
    print(f"Turniej: {liczba_rozdan} rozdan, MCTS {args.mcts_iters} iteracji, "
          f"REINFORCE {'zachlanny' if args.zachlannie else 'stochastyczny'}, model: {args.model}")

    agenci = stworz_agentow(args.seed, args.mcts_iters, args.model, args.zachlannie)
    wyplaty, czasy, decyzje = rozegraj_turniej(agenci, liczba_rozdan, ZIARNO_BAZOWE_GIER)
    drukuj_wyniki(wyplaty, czasy, decyzje)
    if args.wykres:
        rysuj_wykres(wyplaty, "turniej.png")


if __name__ == "__main__":
    main()