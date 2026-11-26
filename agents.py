import random

# agent ktory gra nie calkiem losowo
class AgentLosowy:
    def __init__(self, ziarno):
        self.generator = random.Random(ziarno)

    def wybierz_akcje(self, obserwacja, legalne_akcje):
        return self.generator.choice(legalne_akcje)