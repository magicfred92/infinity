"""Candidate profile used to score and summarise scraped job offers.

This is a hardcoded snapshot of Frédéric Crousaz's CV/LinkedIn profile.
Edit the values below (and the keyword lists) if the target role or
skill set changes — nothing here is read from an external file.
"""
from __future__ import annotations

PROFILE = {
    "name": "Frédéric Crousaz",
    "headline": "Event Officer / Coordinateur d'événements & opérations",
    "location": "Genève, Suisse",
    "mobility": "Ouvert aux déplacements",
    "languages": {
        "français": "langue maternelle",
        "anglais": "courant",
        "espagnol": "intermédiaire",
    },
    "summary": (
        "Professionnel de la gestion opérationnelle d'événements avec cinq années "
        "d'expérience dans l'organisation de grandes conférences internationales, "
        "la mise en place des inscriptions et la conclusion de contrats "
        "fournisseurs jusqu'à la livraison sur site. Expérience auprès "
        "d'organisations internationales (IUCN, CICR, Swiss-African Business "
        "Circle). Bonne connaissance de la gestion des plates-formes "
        "d'inscription, du suivi des budgets, de la coordination des sponsors, "
        "exposants et lieux, et du suivi d'un programme à jour. Disponible pour "
        "les déplacements sur site."
    ),
    "target_regions": ["Genève", "Lausanne", "Suisse romande"],
}

# Target job titles / role families — weight 3 per match in the scorer.
TITLE_KEYWORDS = [
    "event officer",
    "event coordinator",
    "event manager",
    "event planner",
    "meeting planner",
    "responsable événementiel",
    "coordinateur événementiel",
    "coordinatrice événementielle",
    "coordinateur d'événements",
    "chargé d'événementiel",
    "chargée d'événementiel",
    "conference coordinator",
    "conference officer",
    "programme officer",
    "program officer",
    "operations officer",
    "operations coordinator",
    "logistics coordinator",
    "logistics officer",
    "project assistant",
    "project coordinator",
    "chef de projet événementiel",
    "coordinateur logistique",
    "coordinatrice logistique",
]

# Skills / tools / domain vocabulary from the CV — weight 2 per match.
SKILL_KEYWORDS = [
    "salesforce",
    "hubspot",
    "microsoft dynamics",
    "crm",
    "airtable",
    "gestion des inscriptions",
    "registration management",
    "sponsoring",
    "sponsorship",
    "exposants",
    "exhibitors",
    "webex events",
    "zoom events",
    "hubilo",
    "cvent",
    "evenium",
    "infomaniak",
    "budget",
    "fournisseurs",
    "vendors",
    "logistique",
    "logistics",
    "stakeholder",
    "parties prenantes",
    "reporting",
    "tableau",
    "qualtrics",
    "sharepoint",
    "wordpress",
    "mailchimp",
    "canva",
    "gestion de projet",
    "project management",
    "conférence internationale",
    "international conference",
    "gestion des participants",
    "participant management",
]

# Sector / employer vocabulary — weight 1 per match.
SECTOR_KEYWORDS = [
    "organisation internationale",
    "international organization",
    "ong",
    "ngo",
    "nations unies",
    "united nations",
    "humanitaire",
    "humanitarian",
    "diplomatie",
    "diplomatic",
    "onu",
    "association",
    "fondation",
    "foundation",
]

# Free-text location needle -> canton/region code. Used both to tag a
# job's region for filtering and to score it (French-speaking cantons are
# rewarded, clearly German-/Italian-speaking-only locations are
# penalised). Keys must be lowercase.
LOCATION_KEYWORDS = {
    "genève": "GE",
    "geneve": "GE",
    "geneva": "GE",
    "gland": "GE",
    "lausanne": "VD",
    "vaud": "VD",
    "nyon": "VD",
    "montreux": "VD",
    "vevey": "VD",
    "yverdon": "VD",
    "morges": "VD",
    "fribourg": "FR",
    "freiburg": "FR",
    "neuchâtel": "NE",
    "neuchatel": "NE",
    "la chaux-de-fonds": "NE",
    "valais": "VS",
    "wallis": "VS",
    "sion": "VS",
    "martigny": "VS",
    "jura": "JU",
    "delémont": "JU",
    "delemont": "JU",
    "romandie": "ROMANDIE",
    "suisse romande": "ROMANDIE",
    # Clearly non-French-speaking Swiss regions — matching one of these
    # (and nothing above) triggers a penalty in the scorer.
    "zürich": "OTHER",
    "zurich": "OTHER",
    "bern": "OTHER",
    "berne": "OTHER",
    "basel": "OTHER",
    "bâle": "OTHER",
    "luzern": "OTHER",
    "lucerne": "OTHER",
    "lugano": "OTHER",
    "ticino": "OTHER",
    "st. gallen": "OTHER",
    "winterthur": "OTHER",
    "zug": "OTHER",
}

# Default search queries used by any source config (built-in or added
# through the app's "Gérer les sites" panel) that doesn't specify its own
# `search_terms` / `regions`. Kept short: each term is run once per
# region, and every extra term multiplies the number of requests made.
DEFAULT_SEARCH_TERMS = [
    "event officer",
    "coordinateur événementiel",
    "operations officer",
    "conference coordinator",
]

DEFAULT_REGIONS = ["Genève", "Lausanne"]

