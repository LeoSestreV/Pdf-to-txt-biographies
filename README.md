# Extracteur de biographies – PDF numérisés

Pipeline d'extraction automatique de biographies individuelles à partir de volumes PDF numérisés (type *Biographie Nationale de Belgique*).

## Structure du projet

```
extract_biographies.py   ← Point d'entrée CLI + orchestrateur
constants.py             ← Listes de mots, patterns regex, flags PyMuPDF
config.py                ← Dataclass ExtractionConfig + chargement JSON
pdf_engine.py            ← Extraction PyMuPDF (spans, lignes, colonnes)
classifiers.py           ← Détection de début de biographie, faux positifs, renvois
cleaner.py               ← Nettoyage du texte, extraction des noms, noms de fichiers
volume1_config.json      ← Configuration spécifique au Volume 1
```

## Utilisation

```bash
# Avec détection automatique des pages
python extract_biographies.py BiographieNationale_Volume1.pdf

# Avec configuration manuelle (pages, seuils, corrections OCR)
python extract_biographies.py volume1_config.json
```

Le type d'entrée est détecté par l'extension : `.json` charge une config complète, `.pdf` utilise les valeurs par défaut avec auto-détection des limites.

## Flux d'extraction

```
PDF
 │
 ▼
┌─────────────────────────────────┐
│  1. detect_boundaries()         │  pdf_engine.py
│     Scan avant : trouve la      │
│     première page avec ≥ N      │
│     débuts de biographie        │
│     Scan arrière : cherche      │
│     ERRATA / INDEX / TABLE DES  │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  2. extract_page_data()         │  pdf_engine.py
│     Pour chaque page :          │
│     - Extraire les spans avec   │
│       métadonnées (gras,        │
│       italique, taille, police) │
│     - Fusionner les lignes par  │
│       proximité Y (tolérance)   │
│     - Trier colonne gauche      │
│       puis droite               │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  3. is_biography_start()        │  classifiers.py
│     Chaîne de validateurs :     │
│     ┌──────────────────────┐    │
│     │ 1. Nom gras majuscule│    │
│     │ 2. Petites caps      │    │
│     │    espacées (A B B É)│    │
│     │ 3. Indenté + pattern │    │
│     │    NOM, ou NOM(      │    │
│     │ 4. Indenté + italique│    │
│     │ 5. Nom seul sur ligne│    │
│     │ 6. Après attribution │    │
│     │    d'auteur           │    │
│     └──────────────────────┘    │
│     Chaque validateur renvoie : │
│     True  → biographie          │
│     False → stop (pas une bio)  │
│     None  → essayer le suivant  │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  4. collect_bio_starts()        │  extract_biographies.py
│     - Filtrer les faux débuts   │
│       causés par la césure      │
│     - Fusionner les noms qui    │
│       continuent sur 2 lignes   │
│       (particules : VAN, DE…)   │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  5. Segmentation & nettoyage    │
│     - Découper le texte entre   │
│       chaque début détecté      │
│     - clean_biography_text()    │  cleaner.py
│       Recoller les césures,     │
│       joindre les lignes,       │
│       appliquer corrections OCR │
│     - Fusionner les stubs       │
│       (entrées < 60 car.)       │
│     - Séparer les entrées       │
│       fusionnées (Voir… + bio)  │
└────────────┬────────────────────┘
             ▼
┌─────────────────────────────────┐
│  6. Classification & écriture   │
│     - is_cross_reference()      │  classifiers.py
│       → écarter les "Voir X"    │
│     - is_false_positive()       │  classifiers.py
│       → écarter fragments,      │
│         latin, notes de bas     │
│         de page                 │
│     - extract_filename()        │  cleaner.py
│       → nom de fichier sûr     │
│     - Écrire chaque biographie  │
│       dans biographies_finales/ │
│     - Générer rapport_final.log │
└─────────────────────────────────┘
```

## Configuration

`ExtractionConfig` (`config.py`) centralise tous les paramètres ajustables. Créer un fichier JSON pour chaque volume :

```json
{
    "pdf_path": "BiographieNationale_Volume1.pdf",
    "output_dir": "biographies_finales",
    "start_page": 41,
    "end_page": 469,
    "header_y": 60.0,
    "col_boundary": 290.0,
    "ocr_fixes": {"ARIVOIIL": "ARNOUL"}
}
```

Les clés absentes du JSON prennent les valeurs par défaut. Passer `null` pour `start_page` / `end_page` active l'auto-détection.

## Ajout de règles de détection

Les validateurs de début de biographie sont dans la liste `BIO_START_VALIDATORS` (`classifiers.py`). Pour ajouter une règle :

```python
def _check_custom(line_data, cfg, next_line_data, prev_line_data):
    """Ma nouvelle règle de détection."""
    # return True / False / None
    ...

BIO_START_VALIDATORS.append(_check_custom)
```

## Dépendances

- Python 3.10+
- [PyMuPDF](https://pymupdf.readthedocs.io/) (`pip install PyMuPDF`)
