# Ad Agent

Agent IA qui lit un **brief** (objectif, DA, hook, produit, images) et une **base de formats d'ads statiques**,
puis produit plusieurs variantes prêtes à retoucher dans Canva.

Détail des étapes et des fichiers produits : [docs/pipeline.md](docs/pipeline.md).

## Structure

```
formats/     base de formats : une fiche YAML par format (structure, zones, hooks, objectifs)
briefs/      template de brief + exemples
agent/       code : schémas, chargement, CLI (puis les étapes du pipeline)
assets/      images produit (non versionnées)
outputs/     runs générés (non versionnés)
docs/        documentation
tests/       tests
```

## Démarrage

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ad-agent validate     # valide briefs et formats
pytest
ad-agent run briefs/example_soin_peau.yaml --no-png   # génère un run dans outputs/ (HTML)
```

Rédacteur Claude (optionnel) : `pip install -e ".[llm]"`, copier `.env.example` en `.env`, y mettre sa clé API, puis
`ad-agent run briefs/example_soin_peau.yaml --writer claude`. Sans clé, le rédacteur hors ligne reste utilisable.

Pour les captures PNG : `pip install -e ".[render]"` puis `playwright install chromium` (ou `firefox`, `webkit`), et lancer sans `--no-png`
(`--browser firefox` pour choisir le moteur).

## Règles de la base de formats
- On documente la **structure** d'un format (zones, hiérarchie, hooks adaptés), jamais le visuel d'un concurrent.
- Une pub source est référencée par son ID Meta Ad Library, avec sa durée de diffusion observée
  (une pub active depuis plus de 30 jours est probablement rentable).
- `status: draft` tant qu'un format n'a pas été relu et testé ; `validated` ensuite.

## Niches
La niche est un **paramètre du brief** (`niche:`), pas une limite de l'agent. Niches gérées : `tech`, `beaute`, `mode`,
`sante_bien_etre`, `animaux` (et `autre`). Les formats sont génériques par défaut ; `niches_fit` restreint un format
aux niches où il excelle (liste vide = universel).

## Feuille de route

- [x] Structure du projet, schémas brief et format (avec niches), CLI de validation
- [x] Première curation Meta Ad Library (US) : 8 fiches `draft`, protocole dans [docs/curation.md](docs/curation.md)
- [ ] Compléter la base : comparatif, callouts, faux pop-up d'avis, formats bien-être
- [x] Boucle brief → variantes → HTML avec les 8 formats (voir docs/pipeline.md pour le détail de chacun), PNG via Playwright
- [x] Rédacteur Claude (angles et textes) : `--writer claude`, testé avec un faux client (premier essai réel à faire avec une clé)
- [ ] Analyse des assets, génération de scènes (Nano Banana), contrôle qualité
- [ ] Intégration Canva (Connect API, à vérifier avec le compte Pro)
- [ ] Retour terrain : scores de formats selon les performances réelles
