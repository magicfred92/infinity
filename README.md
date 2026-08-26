# Infinity Job Radar

Un site personnel qui scrape automatiquement des offres d'emploi correspondant
au profil de Frédéric Crousaz (Event Officer / coordination d'événements et
d'opérations), les résume, les note par pertinence, et les affiche triées —
avec une cible géographique sur **Genève, Lausanne et la Suisse romande**
(GE, VD, FR, VS, NE, JU).

## Comment ça marche

```
scraper/               → le scraper Python (tourne dans GitHub Actions)
  profile.py            → le profil candidat + les listes de mots-clés de scoring
  sources_config.json   → la liste des sites à scraper (éditable depuis l'app !)
  common.py             → utilitaires partagés (robots.txt, extraction JSON-LD, scoring)
  sources/generic.py    → un scraper générique piloté par sources_config.json
  summarize.py          → résumé de chaque offre (IA optionnelle, sinon extractif)
  main.py               → orchestre tout et écrit docs/data/jobs.json

docs/                   → le site statique (servi par GitHub Pages)
  index.html / assets/  → l'interface (liste d'offres, filtres, panneau "Gérer les sites")
  data/jobs.json         → généré automatiquement à chaque run du scraper
  data/sources_config.json → copie en lecture seule de la config des sites

.github/workflows/scrape.yml → exécute le scraper chaque jour et publie le résultat
```

Chaque nuit (et à la demande), GitHub Actions :
1. Lit `scraper/sources_config.json` pour savoir quels sites scraper.
2. Charge chaque page de recherche dans un vrai navigateur headless (Playwright),
   pour ne pas dépendre de sites qui rendent leur contenu en JavaScript.
3. Sur chaque offre trouvée, essaie d'abord de lire le bloc structuré
   `schema.org/JobPosting` (le standard utilisé par la plupart des portails
   d'emploi pour être indexés par Google for Jobs) — plus stable que du
   scraping de classes CSS.
4. Calcule un score de pertinence (0–100) à partir des mots-clés de
   `profile.py` (titres de poste ciblés, compétences, secteur, localisation,
   fraîcheur de l'annonce).
5. Génère un résumé de chaque offre — via l'API Claude si `ANTHROPIC_API_KEY`
   est configuré (secret GitHub Actions), sinon un résumé extractif simple.
6. Écrit `docs/data/jobs.json` et le commit — GitHub Pages republie le site
   automatiquement.

## Mise en route (une seule fois)

1. **Active GitHub Pages** : Settings → Pages → Source = "Deploy from a
   branch" → Branch = `main`, dossier `/docs`.
2. **(Optionnel) Résumés par IA** : Settings → Secrets and variables →
   Actions → New repository secret → `ANTHROPIC_API_KEY`. Sans cette clé, le
   site fonctionne quand même (résumés extractifs, scoring par mots-clés).
3. **Lance un premier scraping** : onglet Actions → "Scrape jobs" →
   "Run workflow", ou attends l'exécution planifiée quotidienne.

## Ajouter un site depuis l'application

Le panneau **« ⚙️ Gérer les sites à scraper »** en bas de la page permet
d'ajouter, activer/désactiver ou retirer un site sans toucher au code : le
formulaire écrit directement dans `scraper/sources_config.json` via l'API
GitHub, et un bouton permet de déclencher un scraping immédiatement.

Pour que l'écriture fonctionne, il faut configurer un **token d'accès
personnel GitHub (fine-grained)**, limité à ce dépôt, avec les permissions
*Contents: Read and write* et *Actions: Read and write* — créé depuis
[github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new).
Ce token n'est stocké que dans le `localStorage` du navigateur qui l'a saisi
et n'est envoyé qu'à `api.github.com`.

**Ce qui marche bien comme nouveau site** : un portail d'emploi public,
consultable sans connexion, avec une page de recherche par texte libre, et
qui expose le format `schema.org/JobPosting` sur ses pages d'offre (c'est le
cas de la plupart des grands portails, pour être indexés par Google for
Jobs). **Ce qui ne marchera pas** : LinkedIn (bloqué + contraire à ses CGU),
la plupart des portails ATS d'entreprise (souvent une SPA sans lien
crawlable), tout ce qui est derrière une connexion.

## Calibration après le premier run réel

Ce projet a été écrit sans accès réseau en direct à jobs.ch / jobup.ch
(l'environnement où il a été rédigé bloque les requêtes sortantes vers des
domaines arbitraires). Le scraper est conçu pour être robuste malgré ça
(rendu JS complet, extraction JSON-LD plutôt que classes CSS, plusieurs
tentatives de sélecteurs), mais si les logs de l'Action affichent des
avertissements du type *"no job links found"* pour un site, c'est le signe
que `detail_link_hints` doit être ajusté pour ce site :

1. Ouvre l'artefact `scraper-debug` du run GitHub Actions concerné — il
   contient un export HTML de la page qui a posé problème.
2. Repère le vrai pattern d'URL des pages d'offre dans ce HTML.
3. Mets à jour `detail_link_hints` pour ce site, dans
   `scraper/sources_config.json` (directement, ou via le panneau "Gérer les
   sites").

Aucune autre partie du pipeline (scoring, résumé, site) n'a besoin de
changer quand on ajoute ou corrige un site.

## Développement local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
python -m scraper.main
# puis ouvrir docs/index.html avec un serveur local, p.ex. :
python -m http.server --directory docs 8000
```

## Éthique du scraping

Le scraper respecte le `robots.txt` de chaque site avant de charger une
page (recherche ou détail) et ne cible que des pages publiques, pour un
usage strictement personnel (une seule personne qui suit les offres qui la
concernent). Il ne scrape pas LinkedIn.
