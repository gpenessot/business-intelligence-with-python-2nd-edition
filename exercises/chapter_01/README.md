# Chapitre 1 : exercices

Ces exercices reprennent le projet `ecommerce-sales-analysis` de la section 1.7 du livre. Ils s'appuient sur `data/raw/sales_sample.csv`, produit par le script de préparation :

```bash
uv run python scripts/prepare_dataset.py
```

## Exercice 1 : mettre votre projet sous Git

Votre projet d'analyse n'est pas encore versionné. Initialisez un dépôt, rédigez un `.gitignore` adapté (les données brutes et l'environnement virtuel ne doivent pas être versionnés) et créez un premier commit avec un message descriptif. Vérifiez ensuite avec `git status` qu'aucun fichier du dossier `data/` n'apparaît.

## Exercice 2 : le jour le plus performant

La section 1.7 a agrégé le chiffre d'affaires par mois. Calculez maintenant le chiffre d'affaires par **jour de la semaine**, en utilisant la méthode `day_name()` de l'accesseur `dt`. Quel jour génère le plus de chiffre d'affaires ? Cette information change-t-elle une décision, et laquelle ?

## Exercice 3 : le top 10 des produits

Identifiez les dix produits qui génèrent le plus de chiffre d'affaires, puis les dix les plus vendus en quantité. Les deux listes se recouvrent-elles ? Que dit ce recouvrement, ou son absence, sur la stratégie tarifaire de la boutique ?

## Exercice 4 : une fonction réutilisable

Écrivez une fonction `compute_country_metrics()` qui prend un DataFrame et retourne les métriques par pays de la section 1.7.3. Ajoutez-y des type hints et une docstring au format Google, conformément à la section 1.6.3. Vérifiez que la fonction `help()` affiche bien votre documentation.

## Exercice 5 : la question piège

Un responsable marketing vous demande : « Est-ce que nos ventes augmentent ? ». Avec les seules données de `sales_sample.csv`, pouvez-vous répondre honnêtement ? Formulez en trois lignes ce que vous répondriez, en précisant la donnée qui vous manque.
