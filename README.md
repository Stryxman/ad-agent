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
```

## Règles de la base de formats
- On documente la **structure** d'un format (zones, hiérarchie, hooks adaptés), jamais le visuel d'un concurrent.
- Une pub source est référencée par son ID Meta Ad Library / son URL, avec sa durée de diffusion observée
  (une pub active depuis plus de 30 jours est probablement rentable).
- `status: draft` tant qu'un format n'a pas été relu et testé ; `validated` ensuite.

## Niches
La niche est un **paramètre du brief** (`niche:`), pas une limite de l'agent. Niches gérées : `tech`, `beaute`, `mode`,
`sante_bien_etre`, `animaux` (et `autre`). Les formats sont génériques par défaut ; `niches_fit` restreint un format
aux niches où il excelle (liste vide = universel).

## Feuille de route

- [x] Structure du projet, schémas brief et format (avec niches), CLI de validation
- [ ] **Session de curation Meta Ad Library** : 8 à 12 fiches de formats réparties sur les 5 niches (à faire avec Claude)
- [ ] Étapes 1, 3, 4, 5, 7, 9 avec 3 formats, sans génération d'image (boucle brief → PNG)
- [ ] Analyse des assets, génération de scènes (Nano Banana), contrôle qualité
- [ ] Intégration Canva (Connect API, à vérifier avec le compte Pro)
- [ ] Retour terrain : scores de formats selon les performances réelles
