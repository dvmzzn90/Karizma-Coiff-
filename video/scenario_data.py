"""Répliques, personnages et réglages des voix (source unique pour voix + rendu)."""
import re

CHARS = {
    # edge = (voix, --rate, --pitch, --volume)
    "BOULON": dict(edge=("fr-FR-EloiseNeural", "+12%", "+12Hz", "+0%"),
                   piper=dict(model="fr-siwis-medium", length=0.80, semitones=4.5, fx="robot")),
    "GISELE": dict(edge=("fr-CH-ArianeNeural", "-6%", "-6Hz", "+0%"),
                   piper=dict(model="fr-siwis-medium", length=1.02, semitones=-2.5, gain=0.95)),
    "ASPI": dict(edge=("fr-FR-HenriNeural", "-18%", "-14Hz", "+5%"),
                 piper=dict(model="fr-gilles-low", length=1.08, semitones=-3.0, fx="grave")),
}

# gap = silence (s) AVANT la réplique ; scene = décor
LINES = [
    dict(who="BOULON", gap=0.10, scene="atelier", text="Gisèle ! Aujourd'hui… je deviens humain !"),
    dict(who="GISELE", gap=0.25, scene="atelier", text="Non."),
    dict(who="BOULON", gap=0.12, scene="atelier", text="Pourquoi ?!"),
    dict(who="GISELE", gap=0.20, scene="atelier", text="T'as un grille-pain à la place du cœur."),
    dict(who="BOULON", gap=0.25, scene="atelier", text="Je peux apprendre ! Regarde, je mange !"),
    dict(who="BOULON", gap=0.75, scene="atelier", text="C'est… délicieux… je crois."),
    dict(who="BOULON", gap=0.75, scene="salon", text="Alors je vais pleurer ! Les humains pleurent !"),
    dict(who="GISELE", gap=0.95, scene="salon", text="Arrête, tu vas rouiller."),
    dict(who="BOULON", gap=0.25, scene="salon", text="Toi, t'es humaine. Apprends-moi !"),
    dict(who="GISELE", gap=0.25, scene="salon", text="Euh… humaine… oui… bien sûr."),
    dict(who="BOULON", gap=1.05, scene="salon", text="GISÈLE ?! T'as des boulons !"),
    dict(who="GISELE", gap=0.30, scene="salon", text="Bon… Quarante ans que j'essaie. Ça marche pas."),
    dict(who="ASPI", gap=0.95, scene="salon", text="Vous êtes pathétiques."),
    dict(who="BOULON", gap=0.25, scene="salon", text="L'aspirateur… parle ?!"),
    dict(who="ASPI", gap=0.25, scene="salon", text="Je suis humain. Je fais l'aspirateur depuis 2019."),
    dict(who="GISELE", gap=0.25, scene="salon", text="Mais… pourquoi ?"),
    dict(who="ASPI", gap=0.30, scene="salon", text="Pas d'impôts. Pas de lundi. Que des miettes."),
    dict(who="BOULON", gap=0.80, scene="salon", text="Gisèle… aujourd'hui… je deviens aspirateur !"),
]
TAIL = 0.45  # fin sèche pour la boucle

_PUNCT_ONLY = re.compile(r"^[!?…:;.,]+$")


def display_words(text):
    """Mots tels qu'affichés ; la ponctuation isolée (« ! », « ?! ») est collée au mot précédent."""
    out = []
    for t in text.split():
        if _PUNCT_ONLY.match(t) and out:
            out[-1] += " " + t
        else:
            out.append(t)
    return out
