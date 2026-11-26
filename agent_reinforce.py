import random
import torch
import torch.nn as nn

AKCJE = ["fold", "call", "raise"]
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

def koduj_obserwacje(obs, legalne_akcje):
    n = len(obs.wplaty)
    ja = obs.id_gracza
    x = []

    # moja karta i karta wspolna
    x += [1.0 if obs.karta_prywatna.ranga == r else 0.0 for r in range(3)] 
    # Rangi to 0, 1, 2 (J, Q, K), więc np. dla damy dostaję [0, 1, 0]. 
    # jest to lepsze niż jedna liczba 0/1/2, bo 
    # (sieć nie zakłada że Q jest “w połowie drogi” między J i K)

    if obs.karta_wspolna is None:
        x += [0.0, 0.0, 0.0]
        para = 0.0
    else:
        x += [1.0 if obs.karta_wspolna.ranga == r else 0.0 for r in range(3)]
        para = 1.0 if obs.karta_wspolna.ranga == obs.karta_prywatna.ranga else 0.0
    x += [para]
    x += [1.0 if obs.numer_rundy == 2 else 0.0] # numer rundy

    # liczba graczy i moja pozycja
    x += [n / MAX_GRACZY] # furtka na przyszłość
    x += [1.0 if ja == i else 0.0 for i in range(MAX_GRACZY)] # [1.0, 0.0, 0.0]

    # pula, do wyrownania
    x += [obs.pula / SKALA_WYPLAT, obs.do_wyrownania() / SKALA_WYPLAT]

    # wplaty i foldy – wzgledem mnie (offset 0 = ja, 1 = nastepny...), padding zerami
    wplaty = [0.0] * MAX_GRACZY
    foldy = [0.0] * MAX_GRACZY
    for p in range(n):
        off = (p - ja) % n # 0 to ja, 1 to po lewej, 2 to po prawej
        wplaty[off] = obs.wplaty[p] / SKALA_WYPLAT
        foldy[off] = 1.0 if obs.spasowali[p] else 0.0
    x += wplaty + foldy

    # historia: liczniki akcji [runda][offset gracza][fold/call/raise]
    hist = [[[0.0] * 3 for _ in range(MAX_GRACZY)] for _ in range(2)] # 2 rundy × 3 graczy × 3 akcje,
    podbicia_w_rundzie = 0
    for gracz, akcja, runda, _ in obs.historia:
        hist[runda - 1][(gracz - ja) % n][AKCJE.index(akcja)] += 1.0
        if runda == obs.numer_rundy and akcja == "raise":
            podbicia_w_rundzie += 1
    for r in range(2):
        for o in range(MAX_GRACZY):
            x += hist[r][o]
    #Spłaszczamy tablicę do listy (2 × 3 × 3 = 18 liczb)

    x += [podbicia_w_rundzie / MAKS_PODBIC_W_RUNDZIE]

    x += [1.0 if a in legalne_akcje else 0.0 for a in AKCJE] # Trzy liczby mówiące, które akcje są legalne
    return torch.tensor(x, dtype=torch.float32)

#zamienia to, co widzi jeden gracz, na stały wektor liczb dla sieci
# swoją kartę i kartę wspólną (one-hot rang, plus flaga pary i rundy 2),
# liczbę graczy i swoją pozycję, pulę oraz ile trzeba dołożyć. 
# Dalej wpłaty i foldy wszystkich graczy, licznik akcji fold/call/raise z historii w obu rundach, 
# liczba podbić w bieżącej rundzie i maska legalnych akcji.


def maska(legalne_akcje):
    return torch.tensor([a in legalne_akcje for a in AKCJE]) # [True/False, True/False, True/False]

#------------------------------------------------------------------------------------#

class SiecPolitykiBaseline(nn.Module):
    def __init__(self, wymiar_wejscia, ukryte=128):
        super().__init__()
        self.pien = nn.Sequential(
            nn.Linear(wymiar_wejscia, ukryte), nn.ReLU(),
            nn.Linear(ukryte, ukryte), nn.ReLU(),
        )
        self.glowa_polityki = nn.Linear(ukryte, 3)
        self.glowa_wartosci = nn.Linear(ukryte, 1)

    def forward(self, x, maska_legalnych):
        h = self.pien(x)
        logity = self.glowa_polityki(h)
        logity = logity.masked_fill(~maska_legalnych, -1e9)
        return logity, self.glowa_wartosci(h).squeeze(-1)

# Sieć neuronowa z jednym wspólnym "pniem" 
# (dwie warstwy ukryte po 128 neuronów z ReLU), 
# z którego wychodzą dwie głowy: polityk (3 dla fold/call/raise) i **wartości** 

#W forward nielegale akcje są zastępowane przez -1e9, 
# więc po softmaxie mają prawdopodobieństwo 0 i agent ich nigdy nie wybierze. 
# maska_legalnych odwraca maskę (True tam, gdzie akcja jest nielegalna), 
# a .squeeze(-1) zamienia wyjście wartości z kształtu [1] na zwykły skalar.

#------------------------------------------------------------------------------------#

# tak samo jak w losowym i mcts
class AgentReinforce:
    def __init__(self, ziarno, sciezka_modelu, zachlannie=False):
        self.generator = random.Random(ziarno)
        self.zachlannie = zachlannie
        dane = torch.load(sciezka_modelu, map_location="cpu")
        self.siec = SiecPolitykiBaseline(dane["wymiar"])
        self.siec.load_state_dict(dane["wagi"])
        self.siec.eval()

    def wybierz_akcje(self, obserwacja, legalne_akcje):
        if len(legalne_akcje) == 1:
            return legalne_akcje[0]
        with torch.no_grad():
            x = koduj_obserwacje(obserwacja, legalne_akcje)
            logity, _ = self.siec(x, maska(legalne_akcje))
            if self.zachlannie:                                 # wybieramy akcję z największym prawdopodobieństwem
                return AKCJE[int(torch.argmax(logity))]
            probs = torch.softmax(logity, dim=-1).tolist()
        return self.generator.choices(AKCJE, weights=probs)[0]