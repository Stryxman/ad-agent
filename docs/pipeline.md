# Pipeline de l'agent

Chaque exécution crée `outputs/run_<date>/`. Chaque étape lit le fichier de la précédente et écrit le sien :
tout est traçable et rejouable.

| # | Étape | Entrée | Sortie | Statut |
|---|---|---|---|---|
| 1 | Lecture du brief | `brief.yaml` + images | `brief.normalized.json` | fait |
| 2 | Analyse des assets | images produit | `assets.report.json` | fait |
| 3 | Stratégie (angles + hooks) | brief normalisé | `angles.json` | fait (rédacteur hors ligne ou Claude) |
| 4 | Sélection des formats | angles + base de formats | `variant_plan.json` | fait |
| 5 | Copywriting | plan de variantes | `copy.json` | fait (rédacteur hors ligne ou Claude) |
| 6 | Composition visuelle | copy + assets + format | `layouts/*.json` + scènes générées | à faire |
| 7 | Rendu HTML → PNG | copy + format + DA | `renders/*.html` (+ `.png`) | fait pour 3 formats |
| 8 | Contrôle qualité | rendus + brief | `qa.report.json` | à faire |
| 9 | Export et packaging | rendus | `manifest.json`, `review.md` | fait (Canva à venir) |
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


## Ce qui est implémenté (premier jet)
- Une **variante** est un concept (angle + format + accroche), rendu dans tous les ratios communs au brief et au format.
- **Sélection** : un format est écarté, avec sa raison écrite dans `variant_plan.json`, s'il n'a aucun ratio commun avec
  le brief, si l'objectif ne correspond pas, si la niche n'est pas adaptée, s'il exige un champ du brief absent
  (`requires`, ex. avis réels pour le témoignage, ancien prix pour le prix barré), si une promesse interdite
  du brief l'exclut (avant/après) ou s'il n'a pas encore de gabarit de rendu.
- **Textes** : `OfflineWriter` reformule uniquement le contenu du brief (bénéfices, offre, avis réels, prix) et
  respecte les `max_chars`. Il n'invente ni avis, ni chiffres.
- **Rendu** : gabarits Jinja2 dans `agent/templates/` pour `fond_uni_packshots_prix`, `offre_prix_barre` et
  `temoignage_citation`. Couleurs d'accent automatiquement remplacées si leur contraste est insuffisant.
- **PNG** : Playwright est optionnel (`pip install -e ".[render]"` puis `playwright install chromium`).
  Sans lui, le pipeline produit les HTML et le signale.

## Le rédacteur Claude (`agent/claude_writer.py`)
Activé avec `--writer claude` ; nécessite `pip install -e ".[llm]"` et une clé API (voir `.env.example`).
- **Sorties structurées** : l'API reçoit un schéma Pydantic et renvoie un objet validé (`client.messages.parse`).
- **Ce que le modèle écrit** : les angles et accroches, sous-titres, appels à l'action, titres facultatifs.
- **Ce qu'il n'écrit jamais** : les prix, les avis clients et leurs signatures. Ils viennent du brief tels quels.
- **Contrôles en code sur chaque texte du modèle** : longueur maximale de la zone, promesses interdites du
  brief, chiffres absents du brief. Un texte rejeté est remplacé par celui du brief, avec un avertissement
  dans `copy.json` et `review.md`.
- **Confidentialité** : le modèle ne reçoit ni chemins de fichiers ni couleurs, seulement les faits du brief.
- **Coût** : le nombre de tokens par run est affiché et consigné dans `manifest.json` (`usage`).
- **Modèle** : `claude-opus-5` par défaut ; `--model` ou la variable `AD_AGENT_MODEL` pour en changer.

## Le détourage automatique (`agent/assets.py`)
- **Détection avant action** : `looks_isolated()` regarde si le bord de l'image est déjà une couleur quasi
  uniforme, ou si un canal alpha existe déjà. Si oui, aucun détourage n'est lancé.
- **Détourage local avec `rembg`**, uniquement si nécessaire : `pip install -e ".[assets]"`. Aucune clé,
  aucun envoi réseau après le téléchargement (unique) du modèle.
- **Modèle figé explicitement sur `u2net`** (Apache 2.0, réutilisable commercialement, ~176 Mo). Le défaut
  de rembg ≥ 2.0 est `bria-rmbg` (~1 Go, licence NON commerciale, accord payant requis auprès de BRIA AI) :
  ne jamais appeler `rembg.remove()` / `new_session()` sans préciser `u2net`.
- **Mise en cache par empreinte du fichier source** (`assets/.cache/`), donc calculé une seule fois.
- **Canva n'a pas d'API de détourage** : son « Background Remover » n'existe que dans son éditeur, pas dans
  l'API pour développeurs (vérifié sur canva.dev).
- **Limite connue** : sur un produit avec des reflets ou une part de transparence (verre, plastique brillant),
  un léger halo peut rester sur le contour. Acceptable pour une démo, à revoir avant une vraie campagne.
