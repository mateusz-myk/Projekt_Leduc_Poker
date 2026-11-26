import random
import torch

from torch.distributions import Categorical

from .engine import (
    SilnikGry,
    MIN_GRACZY,
    MAX_GRACZY,
    AKCJE,
    SKALA_WYPLAT
)

from .agent_reinforce import (
    SiecPolitykiBaseline,
    koduj_obserwacje,
    maska
)

def rozegraj_rozdanie(siec, n, ziarno):
    gra = SilnikGry(ziarno, n)
    kroki = [[] for _ in range(n)]          # na gracza: (log_prob, entropia, wartosc)
    while not gra.koniec:
        g = gra.gracz_na_ruchu()
        legalne = gra.legalne_akcje(g)
        if len(legalne) == 1:               # brak decyzji to nie uczymy sie na tym
            gra.wykonaj_ruch(legalne[0])
            continue
        x = koduj_obserwacje(gra.obserwuj(g), legalne)
        logity, v = siec(x, maska(legalne))
        dist = Categorical(logits=logity)
        a = dist.sample()
        kroki[g].append((dist.log_prob(a), dist.entropy(), v))
        gra.wykonaj_ruch(AKCJE[int(a)])
    zwroty = [float(w) / SKALA_WYPLAT for w in gra.wyplaty]
    return kroki, zwroty

# Ta funkcja gra jedno rozdanie pokera od początku do końca, a za wszystkich graczy gra ta sama sieć.
# Przy każdej decyzji sieć mówi, z jakimi szansami zagrać fold, call albo raise, a kod losuje akcję 
# według tych szans i zapamiętuje, co zagrał i jak bardzo był tego pewny. Ruchy, w których i tak była 
# tylko jedna możliwość, wykonuje bez zapisywania, bo nie ma w nich żadnego wyboru, więc nie ma się czego uczyć.

# Po końcu rozdania sprawdza, ile każdy gracz wygrał albo przegrał
# Zwraca te wyniki razem z zapisem decyzji każdego gracza. Potem trening robi z tego prostą rzecz: jeśli gracz
# wygrał, to wszystkie jego decyzje z tego rozdania stają się trochę bardziej prawdopodobne, a jeśli przegrał,
# trochę mniej.

def trenuj(liczba_batchy=5000, rozdan_w_batchu=64, lr=1e-3,
    beta=0.01, zakres_graczy=(MIN_GRACZY, MAX_GRACZY),
    sciezka="reinforce.pt", ziarno=0
):
    rng = random.Random(ziarno)
    torch.manual_seed(ziarno)

    # wymiar wejscia z przykladowego stanu
    gra0 = SilnikGry(0, MAX_GRACZY)
    wymiar = len(koduj_obserwacje(gra0.obserwuj(0), gra0.legalne_akcje(0)))
    siec = SiecPolitykiBaseline(wymiar)
    opt = torch.optim.Adam(siec.parameters(), lr=lr)

    for batch in range(liczba_batchy):
        n = rng.randint(*zakres_graczy)     # zmienna liczba graczy
        strata_pol, strata_wart, entropia, liczba_krokow = 0.0, 0.0, 0.0, 0
        for _ in range(rozdan_w_batchu):
            kroki, zwroty = rozegraj_rozdanie(siec, n, rng.randrange(10**9))
            for g in range(n):
                G = zwroty[g]
                for logp, ent, v in kroki[g]:
                    przewaga = G - v.detach()
                    strata_pol = strata_pol - logp * przewaga
                    strata_wart = strata_wart + (v - G) ** 2
                    entropia = entropia + ent
                    liczba_krokow += 1
        if liczba_krokow == 0:
            continue
        strata = (strata_pol + 0.5 * strata_wart - beta * entropia) / liczba_krokow
        opt.zero_grad()
        strata.backward()
        torch.nn.utils.clip_grad_norm_(siec.parameters(), 1.0)
        opt.step()

        if batch % 100 == 0:
            print(f"batch {batch}  strata {float(strata):.4f}  "
                  f"entropia {float(entropia)/liczba_krokow:.3f}")
            torch.save({"wymiar": wymiar, "wagi": siec.state_dict()}, sciezka)

    torch.save({"wymiar": wymiar, "wagi": siec.state_dict()}, sciezka)


#trenuj to główna pętla uczenia: 
# w każdym batchu losuje liczbę graczy (2-3), rozgrywa 64 rozdania w self-play i zbiera z nich wszystkie decyzje wraz z wynikiem gracza
# Potem robi jeden krok poprawiania sieci na podstawie całego batcha, więc 5000 batchy to 5000 małych poprawek wag

# Dla każdej decyzji liczy przewagę = (ile gracz faktycznie wygrał) − (ile sieć się spodziewała wygrać, czyli baseline v).
# Jeśli wypadło lepiej niż oczekiwano, ta akcja staje się bardziej prawdopodobna, a jeśli gorzej, mniej
# Osobna strata uczy głowę wartości, żeby jej przewidywania były trafniejsze, a bonus entropii (beta) lekko nagradza niepewność, 
# żeby sieć nie zaczęła grać zawsze tego samego.

# clip_grad_norm_ ucina zbyt duże gradienty, 
# Adam robi sam krok, a co 100 batchy kod wypisuje postęp i zapisuje model do reinforce.pt. v.detach()
# w przewadze sprawia, że ta część straty nie psuje głowy wartości, tylko uczy politykę.

if __name__ == "__main__":
    trenuj()