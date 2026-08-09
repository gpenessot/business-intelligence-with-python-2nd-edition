# Business Intelligence avec Python, 2e édition

Dépôt compagnon du livre **Business Intelligence avec Python**, 2e édition, publié aux Éditions ENI.

Vous y trouverez les scripts de préparation des données, le code de chaque chapitre et les corrigés des exercices.

La 1re édition reste disponible sur [gpenessot/business_intelligence_with_python](https://github.com/gpenessot/business_intelligence_with_python).

## Un seul jeu de données

Tous les chapitres du livre travaillent sur **le même jeu de données réel**, du premier chargement au tableau de bord final. Vous n'avez donc pas de contexte métier à réapprendre à chaque chapitre, et les chiffres se recoupent d'un bout à l'autre du livre.

Il s'agit d'**Online Retail II**, deux ans de transactions d'une boutique en ligne britannique vendant des cadeaux et des articles de décoration, expédiés dans une quarantaine de pays.

- Source : [UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
- Citation : Chen, D. (2019). *Online Retail II*. UCI Machine Learning Repository.
- Licence : Creative Commons Attribution 4.0 International (CC BY 4.0)
- 1 067 371 lignes de commande, 5 942 clients identifiés, 43 pays

Les dates ont été décalées de 5 110 jours, soit exactement 730 semaines, afin de situer le récit sur une période récente sans altérer les données. Le multiple de sept garantit que chaque transaction conserve son jour de la semaine, et donc les effets de week-end.

Le fichier produit n'est **pas nettoyé**, volontairement : ses doublons, ses identifiants clients manquants et ses quantités négatives sont ceux du jeu réel. Les corriger est l'objet du chapitre 3.

## Démarrage

Le livre utilise [uv](https://docs.astral.sh/uv/) pour gérer l'environnement et les dépendances. Si vous ne l'avez pas encore installé, le chapitre 1 détaille la procédure sur macOS, Ubuntu et Windows.

```bash
git clone https://github.com/gpenessot/business-intelligence-with-python-2nd-edition.git
cd business-intelligence-with-python-2nd-edition
uv sync
```

Téléchargez ensuite le jeu de données, puis générez les fichiers dérivés utilisés par le chapitre 2 :

```bash
uv run python scripts/prepare_dataset.py
uv run python scripts/build_chapter2_sources.py
```

Le premier script télécharge environ 45 Mo depuis le dépôt UCI et met le fichier source en cache : les exécutions suivantes ne retéléchargent rien. Comptez au total quelques minutes et environ 335 Mo sur votre disque. Le dossier `data/` n'est jamais versionné.

## Structure du dépôt

```
scripts/      préparation des données, à exécuter une fois
exercises/    corrigés des exercices, un dossier par chapitre
data/         créé par les scripts, ignoré par Git
```

## Les fichiers produits

`prepare_dataset.py` télécharge la source et écrit :

| Fichier | Contenu |
|:---|:---|
| `data/raw/sales.csv` | le jeu complet, brut, 1 067 371 lignes |
| `data/raw/sales_sample.csv` | extrait propre de 12 543 lignes, pour le chapitre 1 |

`build_chapter2_sources.py` décline ensuite ce même jeu dans tous les formats abordés au chapitre 2 :

| Fichier | Section |
|:---|:---|
| `data/raw/sales_fr.csv` | 2.1.1, export à la française (`;` et `,` décimale) |
| `data/raw/annual_report_2024.xlsx` | 2.1.2, quatre feuilles trimestrielles |
| `data/raw/monthly_reports/` | 2.1.2, douze classeurs mensuels |
| `data/raw/orders.json` | 2.1.3, enregistrements JSON |
| `data/raw/customers.json` | 2.1.3, structures imbriquées |
| `data/raw/products.xml` | 2.1.4, catalogue produits |
| `data/processed/sales.parquet` | 2.1.5 |
| `data/raw/sales.db` | 2.2.4 et 2.6.1, base SQLite |

## Versions

Le code est écrit et testé pour **Python 3.12 ou supérieur** et **pandas 3**. Il fonctionne avec pandas 2, à deux détails d'affichage près que le livre signale au fil du texte, notamment le type `str` qui s'affichait `object`.

## Licence

Le code de ce dépôt est publié sous licence MIT. Le jeu de données reste soumis à sa licence d'origine, CC BY 4.0, qui impose d'en citer la source.
