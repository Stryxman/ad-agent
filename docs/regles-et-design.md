# Règles Meta et design des ads statiques : ce qu'on retient, et ce que ça change dans Ad Agent

Synthèse de recherche du 2026-09-27. Objectif : fonder les choix de rendu (fonds, polices, marges, résolution)
et les textes de publication sur des règles vérifiables plutôt que sur l'intuition. Même principe que
[curation.md](curation.md) : on garde des **règles et des structures**, jamais les visuels ni les textes des
annonces citées.

## Sources et limites

| Source | Nature | Ce qu'on en tire | Limite |
|---|---|---|---|
| [Guide des pubs Meta — image, fil Facebook, trafic](https://www.facebook.com/business/ads-guide/update/image/facebook-feed/traffic) | Officielle | Tailles, ratios, longueurs de texte | Ne couvre ni les marges ni le texte dans l'image |
| [Meta — superpositions de texte et zones de sécurité](https://www.facebook.com/business/help/980593475366490/) | Officielle | Zones de sécurité par placement | Plus de pourcentages chiffrés dans la version actuelle |
| [Meta — recommandations pour les publicités avec image](https://www.facebook.com/business/help/388369961318508) | Officielle | Texte, couleurs, logo, fin de la règle des 20 % | Recommandations générales |
| [Foreplay — exemples de pubs image Facebook](https://www.foreplay.co/post/facebook-image-ads-examples) | Éditeur d'outil publicitaire | 9 annonces décortiquées, bonnes pratiques de design | Analyses qualitatives, pas de chiffres de performance |
| [Pinterest — « creative static ads »](https://fr.pinterest.com/ideas/creative-static-ads/922188946004/) | Tendances visuelles | Structures récurrentes | Seul le premier écran (6 épingles) a été vu : mur de connexion, non contourné |
| [Reddit r/FacebookAds — 1 370 créas testées en 30 jours](https://www.reddit.com/r/FacebookAds/comments/1o7bc98/we_tested_1370_static_ad_creatives_in_the_last_30/) | Retour d'agence | 4 concepts gagnants | **Aucun chiffre** (ni CTR ni CPA) malgré le volume annoncé : témoignage qualitatif |

## 1. Règles techniques Meta

**Fichier et taille (fil Facebook)**
- JPG ou PNG, 30 Mo maximum.
- Ratio recommandé **4:5** (tolérance de 3 %) ; 1:1 accepté pour le fil, 9:16 pour stories et reels.
- Résolution recommandée **1440 × 1800 px** en 4:5, minimum 600 × 750 px.
- Images en haute résolution, « pas trop retouchées ».

**Texte hors de l'image (champs d'Ads Manager)**
- Texte principal : **50 à 150 caractères** recommandés.
- Titre : **27 caractères maximum** recommandés.

**Texte dans l'image**
- Plus aucune limite de quantité : la règle des 20 % et l'outil de vérification ont disparu.
- Recommandations : police moderne et épurée, **grande taille**, **couleur contrastée** avec l'arrière-plan,
  peu de messages, **un seul appel à l'action**.

**Zones de sécurité** (bords où l'interface masque ou rogne le contenu)
- 9:16 (stories, reels, fil) : garder **haut, bas et côtés** libres de texte, logo et éléments clés.
  La page actuelle ne chiffre plus ces bords. Les valeurs couramment reprises de l'ancienne version sont
  d'environ **14 % en haut, 35 % en bas et 6 % sur les côtés** : on les adopte comme valeur de travail.
- 1:1 et 4:5 dans le fil Instagram : garder **le bas et les côtés** libres.
- Reel avec avertissement légal : garder **les 40 % inférieurs** libres.
- Sur les écrans plus hauts que 9:16, Meta peut agrandir l'image (et rogner hors zone de sécurité) ou ajouter
  des bandes noires : seule la zone de sécurité est garantie.

**Contenu**
- Montrer la marque ou le logo, montrer le produit en usage.
- Choisir des couleurs adaptées au contenu : vives pour des soldes, pastel pour un spa.

## 2. Enseignements design

- **Dégradés plutôt qu'aplats.** Ils reviennent souvent dans les exemples (un fond vert dégradé pour un produit
  de santé, un encart promotionnel orange dégradé) et dans les tendances Pinterest (fonds doux, halos, taches
  de couleur).
- **Un contraste fort** reste la condition de base de la lisibilité dans le fil, surtout pour le bouton d'action.
- **La couleur porte le positionnement** : tons doux (pêche, sauge, crème) pour le premium et le soin, couleurs
  saturées (vert vif, orange, bordeaux) pour les promotions et le SaaS.
- **Une idée par visuel**, pas d'encombrement. Le produit est le point focal : fond neutre ou lumière derrière lui.
- **Les polices de la marque comptent** : une police de secours générique (Georgia, Helvetica) efface
  l'identité de la DA.

## 3. Structures créatives repérées (pour la suite de la base de formats)

À documenter plus tard avec la méthode de [curation.md](curation.md), en vérifiant qu'elles tournent depuis plus
de 30 jours sur Meta Ad Library.

| Structure | Source | Mécanisme | Compatible avec nos garde-fous ? |
|---|---|---|---|
| « Vos problèmes / Notre solution » en écran partagé | Pinterest | Liste de problèmes cochés en rouge face au produit | Oui : les problèmes viennent du brief |
| « Eux vs nous » (N produits vs un seul) | Pinterest | Contraste de quantité et de simplicité | Oui, si le brief fournit la comparaison |
| Statistique mise en exergue (cercle, gros chiffre) | Foreplay | Le chiffre sert d'accroche | Seulement avec un chiffre du brief, jamais inventé |
| Comparatif de prix (gratuit vs 400 $) | Foreplay | Valeur perçue immédiate | Seulement avec des prix réels du brief |
| Interface imitée (conversation de chat) | Pinterest | Format natif, familier | **À vérifier** : Meta interdit de simuler des fonctionnalités inexistantes |
| Bénéfices en étoile autour d'une dose | Reddit | Cause → effets multiples, plusieurs publics touchés | Oui : bénéfices du brief, sans promesse médicale |
| Faux avertissement « contenu sensible » | Reddit | Interruption du défilement | **Risqué** : imitation d'un avertissement système, même règle Meta |
| Avis d'acheteur rationnel, à la première personne | Reddit | Ressemble à un avis honnête plutôt qu'à une pub | Oui, avec un **vrai** témoignage du brief uniquement |
| Mur de texte de bénéfices, résultat visualisé | Reddit | Interruption par la densité | À étudier : lisibilité mobile |

Le fil conducteur du retour Reddit est l'**interruption de schéma** : plus une annonce se démarque, plus vite elle
performe. C'est une piste pour les futurs formats, pas une règle démontrée (voir les limites ci-dessus).

## 4. Ce que ça change dans Ad Agent

| Règle ou enseignement | Avant | Fait (voir la [spec](specs/2026-09-27-rendu-et-textes-pub.md)) |
|---|---|---|
| Dégradés | 7 gabarits sur 8 en aplat | Fonds `lineaire` / `mesh` / `uni` calculés depuis la palette, choisis par format, brief ou CLI |
| Contraste | Vérifié sur une couleur de fond | Vérifié sur chaque couleur du dégradé |
| Polices de la DA | Jamais chargées : repli silencieux sur Georgia/Helvetica | Fichier local, puis Google Fonts, sinon avertissement |
| 1440 × 1800 en 4:5 | 1080 × 1350 | Capture à l'échelle 4/3 : 1440 × 1800 (et 1440 × 1440, 1440 × 2560) |
| Zones de sécurité 9:16 | Marge uniforme de 7 % | Marges par ratio, repère visuel optionnel |
| Texte principal 50–150, titre ≤ 27 | Non produits | Jusqu'à 3 de chaque par variante, contrôlés comme le reste |
| Un seul appel à l'action | Déjà le cas | Inchangé |
| Nouvelles structures (section 3) | — | Roadmap : base de formats |
