# Pipeline de l'agent

Chaque exécution crée `outputs/run_<date>/`. Chaque étape lit le fichier de la précédente et écrit le sien :
tout est traçable et rejouable.

| # | Étape | Entrée | Sortie | Statut |
|---|---|---|---|---|
| 1 | Lecture du brief | `brief.yaml` + images | `brief.normalized.json` | schéma prêt |
| 2 | Analyse des assets | images produit | `assets.report.json` | à faire |
| 3 | Stratégie (angles + hooks) | brief normalisé | `angles.json` | à faire |
| 4 | Sélection des formats | angles + base de formats | `variant_plan.json` | à faire |
| 5 | Copywriting | plan de variantes | `copy.json` | à faire |
| 6 | Composition visuelle | copy + assets + format | `layouts/*.json` + scènes générées | à faire |
| 7 | Rendu HTML → PNG | layouts | `renders/*.png` | à faire |
| 8 | Contrôle qualité | rendus + brief | `qa.report.json` | à faire |
| 9 | Export et packaging | rendus validés | `manifest.json`, `review.md`, Canva | à faire |
| 10 | Retour terrain (v2) | choix + performances | mise à jour des scores de formats | à faire |

## Points de validation humaine
- Après l'étape 3 : garder/écarter des angles.
- Après l'étape 4 : valider le plan de variantes avant de dépenser de la génération d'image.

## Principes
- **Le texte n'est jamais généré par le modèle d'image** : il est posé par le rendu HTML (accents exacts, net, gratuit).
  Le modèle d'image (Nano Banana) ne sert qu'à produire fonds et mises en scène à partir des assets produit.
- **La base de formats décrit des structures**, pas des copies de visuels concurrents.
- **Boucle de contrôle qualité limitée** à 2 itérations par variante (retour aux étapes 5 ou 6).

## Détail des sorties

### 1. `brief.normalized.json`
Brief validé par `agent/schemas.py::Brief`, champs par défaut remplis, liste des champs manquants signalés.

### 2. `assets.report.json`
Par image : type (packshot / lifestyle), résolution, fond détourable, couleurs dominantes, zones libres,
verdict `ok | à détourer | à régénérer`.

### 3. `angles.json`
3 à 5 angles (problème/solution, preuve sociale, offre, comparaison, bénéfice unique), chacun avec 2-3 hooks
candidats et son lien avec l'objectif du brief.

### 4. `variant_plan.json`
6 à 10 variantes : `{id, angle, format, hook, ratio}`. Filtres durs (ratio, assets, objectif) puis score
(adéquation hook/format, performance connue), sans doublon angle × format.

### 5. `copy.json`
Par variante, 1-2 versions de texte pour chaque zone du format, dans les limites `max_chars`.

### 6. `layouts/<variant>.json`
Positions, tailles, couleurs, traitement de l'image ; références vers les scènes générées.

### 7. `renders/<variant>_<ratio>.png`
Rendu déterministe (Playwright).

### 8. `qa.report.json`
Débordements, contraste, zones de sécurité (9:16), cohérence DA, conformité aux règles pub Meta,
note d'un modèle de vision vs brief, nombre de boucles effectuées.

### 9. `manifest.json` + `review.md`
Classement des variantes avec justification, liens Canva, tout ce qui a été produit.
