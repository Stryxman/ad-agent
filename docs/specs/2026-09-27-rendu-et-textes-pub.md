# Spec — qualité du rendu (A) et textes de publication (B)

Date : 2026-09-27 · Statut : implémentée · Recherche associée : [regles-et-design.md](../regles-et-design.md)

## Contexte

Les rendus actuels sont corrects mais plats et pas tout à fait conformes à Meta :
- 7 gabarits sur 8 sont en aplat ;
- les polices de la DA ne sont jamais chargées (repli silencieux sur Georgia/Helvetica) ;
- le 4:5 sort en 1080 × 1350 au lieu des 1440 × 1800 recommandés ;
- le 9:16 n'a pas de zones de sécurité ;
- aucun texte de publication (texte principal, titre) n'est produit pour Ads Manager.

## Objectifs et critères de réussite

- **A.** Des fonds en dégradé calculés depuis la palette, les vraies polices de la DA, la résolution
  recommandée par Meta, et des marges qui respectent les zones de sécurité de chaque ratio.
- **B.** Jusqu'à 3 textes principaux et 3 titres par variante, contrôlés comme les textes de l'image.
- **Contrainte de compatibilité** : les briefs et fiches de format existants restent valides sans modification.
- **Réussite** :
  - tous les tests passent, avec de nouveaux tests pour chaque règle ci-dessous ;
  - comparaison visuelle avant/après sur les deux briefs d'exemple ;
  - aucun texte inventé ;
  - un contraste du texte vérifié sur chaque couleur réellement présente sous lui.

## Hors périmètre

Nouveaux formats (roadmap, section 3 de la recherche), export CSV, finition Canva, génération d'image.

## Décisions prises avec l'utilisateur

| Question | Décision |
|---|---|
| Qui décide du fond ? | Automatique par défaut, surchargeable |
| Style de fond préféré | `lineaire` (B), puis `mesh` (D) ; `uni` reste disponible |
| Fond unique ou par gabarit ? | Par gabarit (défaut déclaré dans la fiche de format) |
| Où l'utilisateur choisit-il ? | Dans le brief (`da.fond`) et en CLI (`--fond`), la CLI l'emportant |
| Chargement des polices | Fichier local d'abord, puis Google Fonts, sinon avertissement |
| Textes de publication | Jusqu'à 3 textes principaux et 3 titres par variante |
| Où calculer les dégradés ? | En Python (pas en CSS `color-mix`) pour que le contraste reste vérifiable |

## A. Qualité du rendu

### A1. Fonds — nouveau module `agent/backgrounds.py`

- `build(kind, base, tint, extra) -> Background(css: str, stops: list[str])`.
  - `base` est la couleur de la surface, `tint` la couleur vers laquelle on teinte, `extra` la couleur de la
    troisième tache du `mesh`.
  - `stops` liste les couleurs **réellement visibles** sur la surface, qui servent au contrôle de contraste.
- Les mélanges se font en espace **OKLab**, perceptuellement uniforme, pour éviter les teintes grises au
  milieu du dégradé. Les couleurs produites sont des hex opaques.
- Les traitements (proportions reprises de la maquette validée) :
  - `uni` : `base` seule.
  - `lineaire` : `linear-gradient(160deg, base, mix(base, tint, 32 %))`.
  - `mesh` : `base` plus trois taches radiales floues (`tint` à 55 % en haut à gauche, `tint` à 35 % en bas à
    droite, `extra` à 10 % en haut à droite). Les stops sont `base` et les mélanges obtenus au centre de
    chaque tache.
- **Deux surfaces** sont calculées pour chaque rendu :
  - la surface **fond** (`base = bg`, `tint = accent`, `extra = fg`), qui sert à la grande majorité des
    gabarits ;
  - la surface **accent** (`base = accent`, `tint = fg`, `extra = bg`), pour les gabarits dont le canevas est
    la couleur d'accent (`fond_uni_packshots_prix`, et le repère de `titre_produit_en_situation`).
- **Texte sur une surface** : on garde, entre `#111111` et `#FFFFFF`, celui dont le **pire** contraste sur les
  stops est le plus élevé. Si ce pire contraste est inférieur à 3:1 (seuil WCAG du texte large, déjà utilisé
  par `readable_on`), la surface retombe en `uni` et un avertissement est consigné pour la variante.
- Les blocs posés sur la couleur d'accent pure (boutons d'action, pastilles) gardent `on_accent`, inchangé.

### A2. Choix du fond

- Nouveau champ `AdFormat.fond: Literal["lineaire", "mesh", "uni"] = "lineaire"`.
  - `mesh` pour `fond_uni_packshots_prix` et `spotlight_fonctionnalite` (formats centrés produit).
  - `lineaire` pour les autres.
  - `titre_produit_en_situation` : son canevas est une photo, le fond ne s'applique qu'à son repère sans photo.
- Nouveau champ `DA.fond: Literal["auto", "lineaire", "mesh", "uni"] = "auto"`.
- Nouvelle option `ad-agent run … --fond {auto,lineaire,mesh,uni}`.
- **Priorité** : `--fond` (si différent de `auto`), puis `da.fond` (si différent de `auto`), puis `AdFormat.fond`.
- Le fond retenu est inscrit dans `manifest.json` pour chaque variante.
- Les gabarits remplacent `background: var(--bg)` et `var(--accent)` de leur canevas par
  `{{ bg_surface_css }}` et `{{ accent_surface_css }}`, et `on_bg` par la couleur calculée en A1. Le
  contexte de rendu fournit : `bg_surface_css`, `accent_surface_css`, `on_accent_surface` et `fond` ; `on_bg`
  et `accent_text` sont désormais calculés sur toute la surface fond.

### A3. Polices — nouveau module `agent/fonts.py`

- `resolve(families) -> FontPlan(head: str, sources: dict[str, "local" | "google"], warnings: list[str])`.
- **Fichier local** : `assets/fonts/<famille>.{woff2,woff,ttf,otf}`. On compare en ignorant les espaces et la
  casse, et on accepte aussi un nom suffixé (`PlayfairDisplay-Bold.ttf`). Le fichier est **embarqué en data URI**
  dans un `@font-face` : Firefox refuse de charger une police par `file://` depuis un autre dossier.
- **Google Fonts** : deux `<link>` **par famille**, l'un sans graisse (`css2?family=<Nom>&display=swap`, toujours
  valide), l'autre pour le gras (`:wght@700`) : une famille sans gras (ex. Bebas Neue) ou introuvable ne casse
  pas les autres.
- `assets/fonts/*` n'est pas versionné (polices de marque sous licence) ; un `.gitkeep` garde le dossier.
- **Vérification à la capture** : après le chargement de la page et `document.fonts.ready`, chaque famille
  doit avoir au moins une `FontFace` au statut `loaded`.
  - Ne **pas** utiliser `document.fonts.check()`, qui renvoie vrai pour une famille jamais déclarée.
  - Une police non chargée donne un avertissement dans `review.md` (« police X non chargée, rendu en police
    de secours »).
  - Sans capture (`--no-png`), les polices sont notées « non vérifiées ».

### A4. Résolution

- La capture utilise `device_scale_factor = 4/3`, ce qui donne 1:1 → 1440 × 1440, 4:5 → **1440 × 1800** et
  9:16 → 1440 × 2560.
- La mise en page CSS (conçue sur 1080 px de large) ne change pas.
- Les tailles de sortie sont exposées par une fonction `capture_size(ratio)`, testée sans navigateur.

### A5. Zones de sécurité

- `SAFE_ZONES` donne les marges (haut, droite, bas, gauche) en fraction de la hauteur ou de la largeur :
  - 9:16 → 14 %, 6 %, 35 %, 6 % ;
  - 1:1, 4:5 et 16:9 → 7 % partout (la valeur actuelle).
- Le gabarit de base expose `--safe-top/right/bottom/left`, et `.canvas` les utilise comme marges intérieures.
- Les gabarits qui définissent leurs propres marges (notamment la zone de contenu de
  `titre_produit_en_situation`) passent par ces variables. Le fond et les photos peuvent déborder dans les
  bandes ; **texte, logo et bouton non**.
- L'option `--zones-securite` superpose des bandes rouges translucides sur ces marges. Le `review.md` du run
  précise alors « rendu de contrôle, ne pas publier ».

## B. Textes de publication

### B1. Schéma et interface

- `PublicationCopy(primary_texts: list[str] = [], headlines: list[str] = [])`, rattaché par
  `VariantCopy.publication` (vide par défaut).
- Le protocole `Writer` gagne une méthode `write_publication(brief, hook) -> tuple[PublicationCopy, list[str]]`.
  Les faux rédacteurs des tests sont mis à jour en conséquence.
- `write_all_copy` l'appelle pour chaque variante et fusionne les avertissements.

### B2. Règles communes

- Titre : **27 caractères maximum**. Un titre plus long est **rejeté**, jamais tronqué.
- Texte principal : **150 caractères maximum**. En dessous de 50, il est gardé avec un avertissement
  (recommandation Meta, pas une règle).
- Chaque texte passe par `check_text` (promesses interdites, chiffres absents du brief), **y compris ceux du
  rédacteur hors ligne** : un bénéfice du brief qui contiendrait une promesse interdite n'est pas repris.
- Les doublons sont retirés ; au plus 3 textes principaux et 3 titres.

### B3. Rédacteur hors ligne

- **Titres** : parmi l'accroche de la variante, l'offre et le nom du produit, ceux qui tiennent en 27 caractères.
- **Textes principaux**, assemblés **par phrases entières** sans jamais couper une phrase :
  1. l'accroche puis les bénéfices ;
  2. la description puis l'offre ;
  3. si le brief contient un témoignage, le premier cité **tel quel** entre guillemets avec son auteur, à
     condition qu'il tienne en 150 caractères.
- Si aucun texte ne passe les règles, la liste reste vide et un avertissement est consigné. Rien n'est inventé.

### B4. Rédacteur Claude

- Appel structuré dédié (`PublicationDraft(primary_texts, headlines)`), avec les faits du brief, l'accroche
  de la variante, le ton de la DA, la langue et les limites de longueur. L'effort reste faible, comme pour
  les autres appels.
- Le texte issu d'un témoignage n'est **jamais** demandé au modèle : il est ajouté par le code (B3.3), comme
  les prix et les avis dans les zones de l'image.
- Chaque texte du modèle est revérifié par B2. S'il ne reste aucun texte valide dans une catégorie, on reprend
  les textes hors ligne pour cette catégorie, avec un avertissement.

### B5. Sorties

- `copy.json` et `manifest.json` : un champ `publication` par variante.
- `review.md` : une section « Textes de publication » par variante, avec le nombre de caractères de chaque texte.

## Erreurs et cas limites

| Cas | Comportement |
|---|---|
| Pas de réseau pour Google Fonts | Police de secours et avertissement ; le run ne s'arrête pas |
| Palette où aucun texte n'est lisible sur le dégradé | Repli sur `uni` et avertissement |
| `--fond` invalide | Refusé par argparse (liste fermée) |
| Brief sans offre ni témoignage | Moins de textes de publication, jamais de texte inventé |
| Réponse Claude inexploitable | `WriterError` comme aujourd'hui (le dossier du run est supprimé) |

## Tests à ajouter

- **Fonds** : stops de chaque traitement, mélange OKLab (noir et blanc à 50 % donnent un gris moyen), choix du
  texte sur le pire stop, repli `uni` quand rien n'est lisible, priorité CLI > brief > format.
- **Polices** : fichier local trouvé (nom exact ou suffixé) et embarqué, repli Google, `sources` correct.
  Le script de vérification à la capture est isolé dans une fonction testable.
- **Résolution et marges** : `capture_size` par ratio, variables `--safe-*` présentes dans le HTML rendu en
  9:16 et en 4:5.
- **Publication** : titres ≤ 27 et textes principaux ≤ 150, chaque phrase hors ligne présente dans le brief,
  témoignage repris mot pour mot, promesse interdite rejetée, repli après rejet Claude, `manifest` rempli.
- **Non-régression** : les 50 tests actuels passent sans modification de leurs attentes, sauf l'adaptation
  des faux rédacteurs à la nouvelle méthode.

## Documentation

- `docs/pipeline.md` : les étapes 5 (textes de publication) et 7 (fonds, polices, résolution, marges).
- `README.md` : l'état actuel et la roadmap (sous-projet C : nouvelles structures).
- `formats/_template.yaml` et `briefs/_template.yaml` : les nouveaux champs `fond`, commentés.
- `.gitignore` : `assets/fonts/*`.
