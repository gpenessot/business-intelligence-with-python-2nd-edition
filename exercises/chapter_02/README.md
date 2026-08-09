# Chapitre 2 : exercices

Tous ces exercices s'appuient sur les fichiers produits par les deux scripts de préparation :

```bash
uv run python scripts/prepare_dataset.py
uv run python scripts/build_chapter2_sources.py
```

## Exercice 1 : diagnostic de chargement

Chargez `sales.csv` sans aucun paramètre, puis affichez l'attribut `dtypes`. Identifiez les deux colonnes mal typées et proposez l'appel à `read_csv()` qui les corrige dès la lecture. Vérifiez ensuite que la colonne `InvoiceDate` permet bien d'extraire une année avec l'accesseur `dt`.

## Exercice 2 : consolidation partielle

Modifiez la fonction `load_monthly_reports()` pour qu'elle n'accepte qu'une plage de mois, passée en paramètre. Consolidez le seul quatrième trimestre 2024 et vérifiez que le total correspond bien à la feuille `Q4` du classeur annuel.

## Exercice 3 : le bon format

Convertissez `sales.csv` en Parquet, puis mesurez avec le module `time` le temps de lecture des trois colonnes `InvoiceDate`, `Quantity` et `Price` dans les deux formats. Combien de rechargements faut-il pour que la conversion soit rentable, en comptant le temps d'écriture du fichier Parquet ?

## Exercice 4 : requête paramétrée

En repartant de la fonction `get_sales_by_country()`, écrivez une fonction qui retourne le chiffre d'affaires total d'un pays pour un mois donné, en calculant la multiplication directement en SQL. Comparez son temps d'exécution avec la version qui charge toutes les lignes puis agrège en pandas.

## Exercice 5 : extraction incrémentale

Exécutez le code de la section 2.6.1 deux fois de suite et vérifiez que la seconde exécution ne ramène rien. Supprimez ensuite le fichier `.watermark.json` et observez le comportement. Que se passerait-il si le marqueur était sauvegardé avec `datetime.now()` et qu'une ligne datée d'hier était insérée pendant l'extraction ?
