# Protocole de curation (Meta Ad Library)

Objectif : transformer des pubs observées en **fiches de formats** (structure, zones, hooks) dans `formats/`.
On documente la structure, jamais le visuel : aucune image de concurrent n'est stockée dans le repo.

## Principes
- La curation est **manuelle et ponctuelle** : elle alimente une base interne, l'agent ne fait aucune
  recherche à l'exécution. On rafraîchit la base de temps en temps (par exemple chaque trimestre).
- Site public gratuit de la bibliothèque : aucun compte, aucune API, aucun abonnement.
- Marché de référence : **États-Unis**. Les créations y sont nettement plus conçues qu'en France, où les
  recherches ramènent surtout des advertorials à texte long et des photos brutes sans texte incrusté.

## Méthode

1. Ouvrir <https://www.facebook.com/ads/library/> ; choisir le pays (États-Unis), « Toutes les publicités »,
   statut **Actives**, type de média **Images**. Les filtres apparaissent dans l'URL
   (`active_status=active&ad_type=all&country=US&media_type=image`), donc la recherche est reproductible.
2. **Chercher par annonceur, pas par mot-clé.** Taper le nom de la marque puis cliquer l'entrée vérifiée de la
   liste « Annonceurs » (l'URL passe en `search_type=page`). La recherche par mot-clé cherche dans le texte
   des pubs : « Glossier » ramenait des pubs de chiens et de coiffeurs.
3. Relever, pour chaque pub : **ID dans la bibliothèque**, **date de début de diffusion**, annonceur.
   La durée de diffusion se calcule à partir de la date de début.
4. Garder en priorité les pubs actives depuis **plus de 30 jours** : un annonceur coupe vite ce qui ne
   rapporte pas. Une série récente au gabarit très régulier est un signal plus faible (à reconfirmer).
5. Regrouper les pubs qui partagent la même structure. Un format n'est retenu que s'il apparaît chez
   **plusieurs annonceurs ou plusieurs pubs**.
6. Écrire la fiche (`formats/_template.yaml`) : zones avec `max_chars`, ratios, hooks, `niches_fit`,
   `when_to_use` / `when_to_avoid`, et la source (`ad_library_ids`, `advertisers`, `observed_on`,
   `observed_running_days`). Statut `draft` jusqu'à relecture humaine.
7. Vérifier : `ad-agent validate` puis `pytest`.

## Limites connues
- Certaines marques n'ont pas de page sélectionnable dans la liste (constaté : Oura, Ritual, OLLY, AG1) ou
  la liste propose une autre page (Purple → Purplehecate). Vérifier toujours le nom de l'annonceur sur les
  résultats.
- Un format peut venir d'un seul gros annonceur : la durée de diffusion ne prouve pas la performance.
- Certaines pubs observées contiennent des promesses (santé, résultats corporels) que Meta refuse souvent.
  Le fait qu'elles tournent ne prouve pas leur conformité. Ne reprendre que la structure, jamais les
  allégations, et documenter le risque dans `when_to_avoid`.

## Rappel juridique
Ne pas versionner de visuels de concurrents (droits d'auteur). Référencer uniquement les IDs de la
bibliothèque et décrire la structure avec ses propres mots.

## Suite prévue
- Compléter la base : comparatif (« nous vs eux »), bénéfices en légendes autour du produit, faux pop-up
  d'avis, formats bien-être.
- Cartographie problème → produits (par exemple sommeil : oreiller, complément, couverture, lampe), à
  partir du texte des pubs, une fois l'agent complet fonctionnel.
