import random

#------------------------------------------------------------------------------------#

class AgentLosowy:
    def __init__(self, ziarno):
        self.generator = random.Random(ziarno)

    def wybierz_akcje(self, obserwacja, legalne_akcje):
        return self.generator.choice(legalne_akcje)

#------------------------------------------------------------------------------------#

class AgentHeurystyczny:
    def wybierz_akcje(self, obserwacja, legalne_akcje):
        ranga = obserwacja.karta_prywatna.ranga
        wspolna = obserwacja.karta_wspolna

        para = (
            wspolna is not None
            and wspolna.ranga == ranga
        )

        if para:
            if "raise" in legalne_akcje:
                return "raise"
            return "call"

        if ranga == 0 and "fold" in legalne_akcje:
            return "fold"

        return "call"

#------------------------------------------------------------------------------------#