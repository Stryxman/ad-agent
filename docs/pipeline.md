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
| 7 | Rendu HTML → PNG | copy + format + DA | `renders/*.html` (+ `.png`) | fait pour les 8 formats |
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
- **Détection avant action** : `has_transparent_background()` vérifie si l'image a déjà un fond transparent.
  Si oui, aucun détourage n'est lancé. Un fond uni mais opaque (packshot sur blanc) est détouré quand même :
  sinon ce blanc apparaît en rectangle sur les fonds colorés des gabarits.
- **Recadrage** : l'image détourée est recadrée sur le produit (le halo d'alpha infime laissé par le
  détourage est ignoré), pour qu'il occupe toute la zone utile du gabarit.
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

## Gabarits ajoutés (2026-09-27) : 6 formats sur 8 rendus

`titre_produit_en_situation`, `carte_produit_catalogue`, `spotlight_fonctionnalite` s'ajoutent aux 3
premiers. Le rendu distingue maintenant deux images possibles par produit :
- `product_img` : la version **détourée** (fond uni/dégradé, ex. `offre_prix_barre`, `spotlight_fonctionnalite`).
- `scene_img` : la photo **d'origine, non détourée** (scène plein cadre, ex. `titre_produit_en_situation`,
  `carte_produit_catalogue`) — un fond détouré serait incohérent en arrière-plan plein cadre.

Trois nouvelles zones factuelles, jamais reformulées par un rédacteur (`OfflineWriter` comme `ClaudeWriter`) :
`product_name` (nom exact du produit), `price_line` (« à partir de X € »), `offer_line` (l'offre telle quelle).

Un second brief d'exemple, `briefs/example_ecouteurs_tech.yaml` (niche tech, sans asset), permet de tester
les formats réservés à `mode`/`tech` sans les mélanger avec la niche beauté.

## Formats encore sans gabarit : pourquoi

- **`infographie_probleme`** : sa zone `items` attend 4 à 6 lignes distinctes. Le schéma actuel ne gère
  qu'un seul texte par zone — il faut d'abord faire évoluer `Zone`/`Writer` pour des zones à plusieurs
  lignes, pas seulement écrire du HTML.
- **`avant_apres_beaute`** : exige explicitement de vraies photos avant/après, jamais générées. Le brief
  ne sait référencer qu'une seule image produit, sans notion « avant »/« après ». Il faudrait étendre le
  schéma du brief pour accepter des assets étiquetés, ce que je n'ai pas voulu faire sans vraies photos
  à disposition pour tester.

## Zones à plusieurs lignes (2026-09-27)

Ajout d'un troisième type de zone : `role: list` (ex. `infographie_probleme`), avec `list_min`/`list_max` sur
`Zone`. `VariantCopy.zones` accepte donc `str` ou `list[str]` selon la zone.
- `OfflineWriter` ne remplit jamais ces zones (aucune source factuelle sans modèle) : la zone reste vide,
  honnêtement, plutôt que d'inventer des lignes.
- `ClaudeWriter` demande au modèle une ligne par idée (séparées par `\n`), vérifie chaque ligne comme un texte
  normal (longueur, promesses interdites, chiffres inventés), et laisse la zone vide si trop peu de lignes
  valides survivent au contrôle (`list_min`), plutôt que de livrer une liste tronquée trompeuse.
- Le nom de zone `items` a été évité au profit de `lines` : dans les gabarits Jinja2, `z.items` intercepterait
  la méthode `dict.items()` au lieu du contenu de la zone — un piège silencieux à connaître pour toute
  future zone de ce type.
- Testé en conditions réelles avec `--writer claude` (nécessite un brief à objectif `awareness`/`traffic`/`lead` :
  `infographie_probleme` ne cible pas la conversion).

## `avant_apres_beaute` : le dernier format (2026-09-27)

- **Assets étiquetés** : `AssetRef` gagne deux champs, `role` (ex. `"before"`, `"after"`) et `label`
  (ex. `"Jour 1"`). Un brief sans ces deux rôles voit le format exclu avec une raison explicite
  (`requires: [assets.before, assets.after]`), plutôt que de rendre deux cadres vides.
- **Jamais de détourage** sur les photos avant/après : ce sont de vraies photos de personnes, utilisées
  telles quelles (`generated_scene_ok: false` déjà présent dans la fiche).
- **`disclaimer` est un texte légal figé**, jamais laissé à un rédacteur (créatif ou hors ligne) : toujours
  la même phrase de prudence, dans la langue du brief.
- **Bug de couverture trouvé en testant en réel** : le prompt demandait « 4 angles parmi les types
  autorisés », ce qui pouvait ignorer un type au hasard (dont `before_after`), gaspillant un format pourtant
  disponible. Corrigé en demandant explicitement un angle par type, sans exception.
- **Testé avec de vraies images du produit de l'utilisateur, réutilisées deux fois** (pas une vraie
  démonstration avant/après, seulement une preuve de bon fonctionnement du mécanisme). Deux photos avant/après
  proposées par l'utilisateur (produit Dior) ont été écartées : marque concurrente réelle, photographie
  professionnelle sans doute protégée malgré l'absence de filigrane. Un vrai test de contenu attend de
  vraies photos avant/après consenties.

## Rendu soigné et conforme Meta (2026-09-27)

Règles et sources : [regles-et-design.md](regles-et-design.md). Décisions : [spec](specs/2026-09-27-rendu-et-textes-pub.md).

- **Fonds** (`agent/backgrounds.py`) : `lineaire`, `mesh` ou `uni`, calculés en Python depuis la palette
  (mélange OKLab), jamais saisis à la main. Chaque fond liste ses couleurs visibles : le texte (noir ou blanc)
  est choisi sur la **pire** d'entre elles, et un dégradé qui ne laisse aucun texte lisible (moins de 3:1)
  retombe en aplat avec un avertissement.
- **Choix du fond** : `ad-agent run … --fond mesh` > `da.fond` du brief > `fond` de la fiche de format
  (`mesh` pour les formats centrés produit, `lineaire` sinon). `auto` laisse la main au niveau suivant.
  Le fond retenu est inscrit dans `manifest.json`.
- **Polices** (`agent/fonts.py`) : un fichier dans `assets/fonts/` (non versionné, polices de marque) est
  embarqué dans la page ; sinon la police est demandée à Google Fonts. La capture vérifie que chaque police
  est réellement chargée et le signale dans `review.md` sinon. Un nom de police contenant autre chose que
  lettres, chiffres, espaces et tirets est refusé.
- **Résolution** : mise en page sur 1080 px de large, capture à l'échelle 4/3 : 4:5 → 1440 × 1800
  (recommandation Meta), 1:1 → 1440 × 1440, 9:16 → 1440 × 2560.
- **Zones de sécurité** : en 9:16, ni texte ni logo dans les 14 % du haut, les 35 % du bas et 6 % sur les
  côtés (bandes recouvertes par l'interface des stories et reels) ; 7 % de marge ailleurs.
  `--zones-securite` superpose ces bandes en rouge pour les vérifier (rendu de contrôle, à ne pas publier).

## Textes de publication (2026-09-27)

Pour chaque variante, jusqu'à 3 **textes principaux** (150 caractères maximum, avertissement sous 50) et
3 **titres** (27 caractères maximum, rejetés au-delà, jamais tronqués), dans `manifest.json`
(`variants[].publication`) et `review.md`.

- **Hors ligne** (`agent/publication.py`) : phrases entières du brief (accroche, bénéfices, description,
  offre), jamais coupées ni répétées ; le premier témoignage réel est cité mot pour mot avec son auteur.
- **Claude** : textes adaptés à l'angle de la variante, revérifiés comme le reste (longueur, promesses
  interdites, chiffres absents du brief) ; le témoignage reste ajouté par le code, jamais par le modèle ; si
  rien ne passe, repli sur les textes hors ligne.
