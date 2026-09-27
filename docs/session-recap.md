# Reprise de session — état au 27/09/2026

Ce fichier existe pour qu'une session qui n'a pas le contexte de celle qui a construit ce projet puisse
reprendre correctement : d'où on vient, où on en est, avec quels outils, et par quoi commencer.

## 1. D'où on vient

Chronologie des décisions structurantes, dans l'ordre :

1. **Structure du projet** : agent Python (pas d'app web) qui transforme un brief YAML en variantes d'ads
   statiques, à partir d'une base de formats. Schémas Pydantic, CLI, tests dès le départ.
2. **Curation Meta Ad Library** : 8 formats documentés à partir de vraies publicités (marché US, plus
   abouti que le marché FR pour ce type de contenu). Méthode reproductible dans
   [`curation.md`](curation.md). Règle non négociable : on documente la structure d'un format, jamais le
   visuel d'un concurrent — aucune image de pub tierce n'entre dans le dépôt.
3. **Pipeline brief → PNG** : sélection des formats (ratio, objectif, niche, promesses interdites),
   rédaction, rendu HTML→PNG (Jinja2 + Playwright).
4. **Rédacteur Claude sous contrôle** : sorties structurées (`client.messages.parse`), jamais de prix ou
   d'avis inventés — ces zones restent toujours factuelles, jamais réécrites par le modèle. Chaque texte
   généré est revérifié par du code (longueur, promesses interdites, chiffres inventés).
5. **Détourage automatique (étape 2)** : `rembg` + modèle `u2net` fixé explicitement en dur — le modèle par
   défaut de `rembg` ≥ 2.0 a changé pour `bria-rmbg`, sous licence **non commerciale** et dix fois plus
   lourd. Détecté et évité pendant le développement ; ne jamais retirer ce verrou en retouchant
   `agent/assets.py`.
6. **Les 8 gabarits de rendu**, dont deux plus tardifs : zones à plusieurs lignes (`infographie_probleme`,
   piège Jinja évité — `z.items` capterait `dict.items()`, la zone s'appelle `lines`) et assets étiquetés
   avant/après (`avant_apres_beaute`, jamais détourés, jamais générés).
7. **Finition et publication** : README orienté portfolio, licence MIT, dépôt public
   [`Stryxman/ad-agent`](https://github.com/Stryxman/ad-agent).

Le détail technique de chaque étape est dans [`pipeline.md`](pipeline.md) ; ceci n'en est qu'un résumé de
décisions, pas une redite.

## 2. Où on en est (vérifié le 27/09/2026)

- **10 commits**, arbre de travail propre, **43 tests verts** (`pytest` depuis la racine, avec `.venv`
  activé).
- **Les 8 formats ont un rendu réel**, testés avec de vrais appels à Claude — sauf `avant_apres_beaute`,
  testé uniquement en structure (même photo dupliquée des deux côtés), faute de vraies photos avant/après
  libres de droits.
- **Roadmap non traitée**, reprise du README : formats manquants (comparatif, callouts, formats
  bien-être), génération de scènes avec un modèle d'image (repoussée volontairement, voir plus bas),
  retour terrain (scores de formats selon performances réelles).
- Le fichier `.env` contient une vraie clé API Anthropic active — ne jamais l'afficher, la committer, ou la
  faire circuler.

## 3. Outils installés cette session — quoi, pourquoi, comment s'en servir

Installés au niveau du **compte claude.ai** (donc disponibles dans toute session future, pas seulement ce
projet) :

| Outil | Type | Ce qu'il apporte ici | Comment s'en servir |
|---|---|---|---|
| **Canva** (`canva:*`) | Plugin + connecteur, connecté | La finition manuelle voulue dès l'idée d'origine du projet. `canva:bulk-create` génère un design par variante à partir d'un `manifest.json` et d'un gabarit Canva ; `canva:edit-design` pour ajuster ; `canva:brand-check` pour vérifier la cohérence de marque ; `canva:resize-for-social-media` pour les formats plateforme. | Le demander explicitement, ex. « prends le manifest.json du dernier run et fais un bulk-create Canva ». Le serveur interne `plugin:canva:canva` peut redemander une autorisation propre au premier usage réel, distincte de la connexion déjà faite. |
| **Figma** (`figma:*`) | Plugin, actif mais non demandé | Sans objet pour ce projet (pas de maquette Figma). | À ignorer, sauf si une maquette Figma entre un jour dans le flux. |
| **Superpowers** (`superpowers:*`) | Plugin, aucun compte externe | Discipline de développement : débogage systématique avant tout correctif, TDD avant tout nouveau code, revue de code avant de considérer une étape finie, aide à structurer un travail à plusieurs étapes. | Se déclenche seul selon le contexte, ou en le nommant. |
| **Security Guidance** | Plugin à crochets | Relit automatiquement les diffs (injections, secrets en dur, XSS/SSRF) — pertinent car le projet manipule une clé API et des chemins fournis par l'utilisateur. | Rien à faire, s'exécute seul à chaque fin de tâche et démarrage de session. |
| **`/code-review`** (déjà présent avant cette session) | Skill officiel | Revue de correction ciblée, effort réglable. | `/code-review` avec un niveau (low/medium/high/max/ultra). |

**Cherchés puis abandonnés — ne pas supposer leur présence dans une future session :**
- `prism`, `Prompt Brain`, `Marketing` : introuvables dans l'interface de réglages utilisée, malgré des
  noms exacts vérifiés. Leur valeur (bonnes pratiques Python, optimisation de prompt, SEO/brief
  concurrentiel) est déjà partiellement couverte par Superpowers et par le skill existant
  `veille-ecommerce-fr`.
- **GitHub et Playwright (plugins)** : désinstallés volontairement — redondants avec `gh` CLI (déjà
  authentifié) et Playwright Python (déjà installé pour le projet, moteur Firefox).

**Évalué mais non connecté :**
- **Motion (Creative Analytics)**, `motionapp.com` — à ne pas confondre avec `usemotion.com` (agenda IA,
  sans rapport). Utile uniquement pour la partie bibliothèque concurrentielle Meta Ad Library ; produit
  payant. À reconsidérer seulement au moment de compléter la base de formats, après vérification du tarif
  face à la méthode manuelle déjà documentée (gratuite).

## 4. Par où commencer la prochaine session, dans l'ordre

1. **Passe de revue outillée**, jamais faite avec un outil dédié jusqu'ici : `/code-review` (effort medium)
   sur `agent/`, en laissant Security Guidance faire sa relecture automatique dès la première
   modification. Corriger ce qui remonte avant d'ajouter quoi que ce soit de nouveau.
2. **Tester Canva pour de vrai** : un `bulk-create` depuis un `manifest.json` réel d'un run, pour valider
   l'idée de finition manuelle d'origine. Vérifier d'abord l'autorisation de `plugin:canva:canva`.
3. **Formats manquants** (comparatif, callouts, bien-être) : reprendre la méthode de
   [`curation.md`](curation.md), en comparant éventuellement avec Motion si son tarif le justifie.
4. **`avant_apres_beaute` en vrai contenu** : dès que de vraies photos avant/après libres de droits (ou les
   vôtres, consenties) sont disponibles.
5. **Génération de scènes (Nano Banana/Gemini)** : en dernier, et seulement si la finition Canva ne suffit
   pas à combler le besoin de mise en situation du produit — c'est un second fournisseur d'IA, une vraie
   friction (clé, SDK, coûts) à ne pas rouvrir sans raison.
