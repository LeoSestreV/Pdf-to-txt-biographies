# Historique de Développement — Biography Extractor

## Vue d'ensemble du projet

Ce projet est un pipeline automatisé d'extraction de biographies individuelles à partir des volumes numérisés (PDF) de la *Biographie Nationale de Belgique*. Chaque volume contient des centaines d'entrées biographiques disposées en deux colonnes. Le résultat final : **4 328 biographies** extraites de **15 volumes PDF**, chacune sauvegardée dans un fichier `.txt` individuel.

---

## Chronologie du développement

### Phase 1 — Prototype initial (9 mars 2026)

**Commits :**
- `df5f923` — Upload du premier PDF (Volume 1)
- `7646233` — Premier script d'extraction fonctionnel

**Contexte :** Le projet démarre avec un unique fichier PDF du Volume 1 de la Biographie Nationale. Un premier script `extract_biographies.py` monolithique est créé. Il utilise la bibliothèque **PyMuPDF** (`fitz`) pour lire le PDF, extraire les spans de texte avec leurs métadonnées de police (gras, italique, taille), et identifier le début de chaque biographie.

**Approche initiale :**
- Détection des noms en gras majuscules comme marqueurs de début de biographie
- Extraction colonne par colonne (gauche puis droite)
- Nettoyage basique du texte (dé-césure, suppression des en-têtes)
- Écriture d'un fichier `.txt` par biographie

**Résultat :** Première extraction fonctionnelle des biographies du Volume 1, mais avec de nombreux faux positifs et des entrées manquantes.

---

### Phase 2 — Amélioration de la détection (11 mars 2026)

**Commits :**
- `abc17d4` — Correction des faux positifs, affinement de la détection
- `449ac9c` — Ajout du `.gitignore`
- `d70a5d0` — Abaissement du seuil de taille du gras, gestion des noms espacés avec "ou"
- `a5deba0` — Correction de la détection des noms, filtrage des renvois, dé-césure

**Problèmes résolus :**
- Les noms en petites capitales espacées (ex. `A B B É`) n'étaient pas détectés → ajout d'un validateur dédié
- Le seuil de taille de police pour le gras était trop élevé → abaissé pour capturer plus de noms
- Les renvois ("Voir X") étaient comptés comme des biographies → ajout d'un filtre `is_cross_reference`
- Les mots coupés en fin de ligne (césure) créaient de faux débuts → ajout d'un filtre de césure

**Techniques clés introduites :**
- Chaîne de validateurs (`BIO_START_VALIDATORS`) : chaque validateur retourne `True`, `False` ou `None` (indécis), le suivant prend le relais
- Filtrage par ratio de majuscules dans le nom
- Détection des indentations caractéristiques des débuts de biographie

---

### Phase 3 — Robustesse et nettoyage (13–16 mars 2026)

**Commits :**
- `528817f` — Meilleur découpage, noms de fichiers plus propres, fusion des entrées collées
- `311f274` — Nettoyage des noms de fichiers, suppression des faux positifs, séparation des entrées fusionnées
- `bd02ac3` — Scripts de vérification de complétude
- `821e0ac` — Script de classification des entrées manquantes
- `3b77106` — Corrections OCR : renommage ABANDA→ARANDA, ajout ABOLIN manquant
- `a2d0884` — Corrections OCR supplémentaires (biographie BAUTKEN)

**Problèmes résolus :**
- Certaines biographies étaient fusionnées (deux entrées collées dans un même fichier) → ajout de `split_merged_entries()` qui détecte les motifs "Voir ... NOM(" pour séparer
- Les noms de fichiers contenaient des caractères spéciaux ou des artefacts OCR → nettoyage avec `fix_ocr_spacing()` et `clean_filename_trailing()`
- Des scripts de vérification (`check_biographies.py`) permettent de comparer les biographies extraites avec la table des matières du PDF

**Nouvelles fonctionnalités :**
- Fusion des stubs (entrées < 100 caractères) avec l'entrée suivante
- Détection des attributions d'auteur (lignes courtes en gras petit, ex. "A.-J. Nameche.") comme délimiteur de fin
- Gestion des particules de nom (VAN, DE, DU, DER, DEN) pour la fusion multi-lignes

---

### Phase 4 — Refactorisation et modularisation (16–17 mars 2026)

**Commits :**
- `5c758e3` — Refactorisation de `extract_biographies.py` pour clarté et modularité
- `1b8dda0` — Suppression de toutes les constantes magiques, ajout de `ExtractionConfig` (dataclass) et CLI
- `016a3fe` — Détection automatique des bornes de pages, simplification à un seul argument CLI
- `3c2e1b8` — Correction de la détection de la page de début, suppression des commentaires
- `24b0a6b` — Modularisation en modules séparés, suppression des scripts obsolètes

**Restructuration du code :**

Le script monolithique est décomposé en **6 modules** :

| Module | Responsabilité |
|--------|---------------|
| `extract_biographies.py` | Point d'entrée, orchestration du pipeline |
| `config.py` | Dataclass `ExtractionConfig` avec tous les seuils configurables |
| `constants.py` | Listes de mots, patterns regex, constantes de flags PyMuPDF |
| `pdf_engine.py` | Extraction du texte PDF, détection de layout, détection des bornes |
| `classifiers.py` | Détection de début de biographie, filtres faux positifs / renvois |
| `cleaner.py` | Nettoyage du texte, extraction des noms, génération des noms de fichier |

**Principes de la refactorisation :**
- Toutes les constantes magiques (seuils, tailles, limites) centralisées dans `ExtractionConfig`
- La détection des bornes (page de début, page de fin) est entièrement automatique
- L'interface CLI est simplifiée : `python extract_biographies.py` suffit (aucun argument requis)

---

### Phase 5 — Documentation (17 mars 2026)

**Commits :**
- `6691e5a` — Ajout du README documentant la structure et le flux
- `0671028` — Traduction du README en anglais
- `5aab01b` — Suppression du mode JSON et du rapport de log
- `59caf77` — Documentation technique détaillée dans le README
- `48835f3` — Ajout du diagramme de flux d'extraction en ASCII

**Contenu du README :**
- Diagramme de flux complet du pipeline en ASCII art
- Description de chaque module et de son rôle
- Tableau des paramètres configurables avec valeurs par défaut
- Instructions d'utilisation

---

### Phase 6 — Support multi-volumes (17 mars 2026)

**Commits :**
- `f0a7c01` / `e1acd00` — Upload des PDFs des Tomes 2043 et 2044
- `91ffeef` — Support de l'extraction multi-volumes avec dossiers par chapitre
- `cb3d789` — Ajout de `biographies_finales/` au `.gitignore`
- `a815e37` — Modifications diverses
- `f46eed4` — Auto-détection du layout par volume, scan de `BioPdf/` sans arguments CLI

**Changements majeurs :**
- Le script parcourt automatiquement tous les fichiers `*.pdf` dans `BioPdf/`
- Chaque volume produit un sous-dossier dans `biographies_finales/` (ex. `biographies_finales/BiographieNationale_Volume3/`)
- La fonction `auto_detect_layout()` est introduite : elle échantillonne des pages du PDF pour détecter automatiquement :
  - La frontière entre les colonnes gauche/droite (`col_boundary`)
  - La zone d'en-tête à ignorer (`header_y`)
  - Les plages d'indentation pour chaque colonne (`left_col_indent`, `right_col_indent`)
- Algorithme de détection du layout : analyse statistique des positions X des lignes, recherche du plus grand gap entre les deux colonnes, calcul des quartiles des positions de noms en gras

---

### Phase 7 — Détection avancée des sections (18 mars 2026)

**Commit :**
- `e45e754` — Détection des lettres de section, filtre par plage de lettres, correction OCR

**Fonctionnalités critiques ajoutées :**

1. **Détection des lettres de section** : Le pipeline scanne chaque page à la recherche de lettres majuscules grandes (≥12pt), centrées et en gras (A, B, C...) qui marquent les sections alphabétiques. Fonction `_is_section_letter()`.

2. **Support des volumes "suite"** : Certains volumes commencent par "L (suite)" — ils sont la continuation d'un volume précédent. La lettre de départ est déduite du marqueur "suite".

3. **Correction OCR des lettres de section** : L'OCR peut confondre C/G ou B/Β (bêta grec). La fonction `_verify_section_letter()` vérifie la lettre détectée en la comparant avec les noms des biographies sur les pages voisines.

4. **Détection de la TABLE DES MATIÈRES** : Si un marqueur de section alphabétiquement antérieur à la lettre de départ apparaît, cela indique la table des matières. La plage est automatiquement tronquée.

5. **Filtre par plage de lettres** : Les entrées dont la première lettre tombe en dehors de la plage attendue du volume sont rejetées comme faux positifs. Cela élimine les scissions causées par du texte gras/majuscule au milieu d'une biographie.

6. **Conversion des lettres grecques** : Table de conversion `GREEK_TO_LATIN` pour les caractères Unicode grecs qui ressemblent à des lettres latines (Α→A, Β→B, etc.).

---

### Phase 8 — Upload des biographies et ajustements finaux (19–23 mars 2026)

**Commits :**
- `e34ce88` — Upload de toutes les biographies extraites
- `5cb1e98` — Amélioration de la qualité d'extraction sur les 15 volumes
- `4a2b7da` — Correction du filtre de césure pour les coupures mixtes (ex. Pays-BAS)

**Améliorations finales :**
- Ajout de nombreux mots descripteurs pour la détection des fins de noms (ex. "hagiographe", "luthiste", "escrimeur"...)
- Renforcement des filtres de faux positifs : détection de texte latin (épitaphes), détection de formules d'attribution ("sculp", "fecit", "pinxit"), détection de texte néerlandais ("sterf", "stierf")
- Correction du filtre de césure : le pattern `\w+-$` attrape désormais les mots composés en casse mixte comme "Pays-BAS" qui ne sont pas de vraies césures mais des noms propres

---

## Architecture technique

### Pipeline d'extraction

```
PDF → auto_detect_layout() → detect_boundaries() → extract_page_data()
    → is_biography_start() → collect_bio_starts() → Segmentation
    → Nettoyage → Classification → Écriture .txt
```

### Système de détection des débuts de biographie

La détection repose sur une **chaîne de 6 validateurs** (`BIO_START_VALIDATORS`), testés dans l'ordre :

| # | Validateur | Critère |
|---|-----------|---------|
| 1 | `_check_bold_name` | Nom en gras majuscule (≥7pt), suivi de `(`, `,` ou `ou` |
| 2 | `_check_spaced_smallcaps` | Nom en petites capitales espacées (ex. A B B É) |
| 3 | `_check_indented_name_pattern` | Ligne indentée + pattern de nom majuscule |
| 4 | `_check_indented_italic` | Ligne indentée + nom non-gras suivi d'italique |
| 5 | `_check_name_alone` | Nom seul sur la ligne + parenthèse ou virgule sur la suivante |
| 6 | `_check_after_attribution` | Pattern de nom après une attribution d'auteur |

Chaque validateur retourne :
- `True` → c'est un début de biographie (court-circuit)
- `False` → ce n'est PAS un début (court-circuit)
- `None` → indécis, passer au validateur suivant

### Système de filtrage

Après la détection, trois niveaux de filtrage :

1. **Filtre de césure** : Élimine les faux débuts causés par des mots coupés en fin de ligne (patterns `-$` sur la ligne précédente)
2. **Filtre de renvois** (`is_cross_reference`) : Détecte les entrées courtes contenant "Voir" et les élimine
3. **Filtre de faux positifs** (`is_false_positive`) : Élimine les fragments latins, les attributions d'auteur, les numéros romains isolés, le texte néerlandais, etc.
4. **Filtre de plage de lettres** : Rejette les entrées dont la première lettre n'appartient pas à la plage du volume

### Auto-détection du layout

La fonction `auto_detect_layout()` dans `pdf_engine.py` :

1. Échantillonne ~40 pages réparties entre le 1er et le 4ème cinquième du document
2. Collecte les positions X et Y de toutes les lignes de texte
3. Regroupe les positions X par buckets de 5pt et cherche le plus grand gap entre 180pt et 380pt → c'est la frontière des colonnes
4. Cherche le premier gap ≥15pt dans les positions Y en dessous de 100pt → c'est la limite d'en-tête
5. Calcule les quartiles des positions X des noms en gras (dans chaque colonne) pour déterminer la plage d'indentation attendue

---

## Statistiques finales

| Volume | Biographies extraites |
|--------|----------------------|
| Volume 1 | 456 |
| Volume 2 | 453 |
| Volume 3 | 235 |
| Volume 4 | 348 |
| Volume 5 | 134 |
| Volume 6 | 280 |
| Volume 7 | 180 |
| Volume 8 | 332 |
| Volume 9 | 323 |
| Volume 10 | 236 |
| Volume 11 | 243 |
| Volume 12 | 200 |
| Volume 13 | 271 |
| Volume 14 | 262 |
| Volume 15 | 375 |
| **Total** | **4 328** |

---

## Dépendances

- **Python 3.10+**
- **PyMuPDF** (`pip install PyMuPDF`) — bibliothèque de lecture PDF qui donne accès aux métadonnées de chaque span de texte (police, taille, flags gras/italique, position x/y)

---

## Défis techniques rencontrés

### 1. Variabilité du layout entre volumes
Chaque volume a un layout légèrement différent (largeur des colonnes, position des en-têtes, taille des polices). Résolu par l'auto-détection statistique du layout.

### 2. Artefacts OCR
Les PDFs sont des scans OCR avec des erreurs fréquentes : lettres grecques confondues avec des latines, mots mal segmentés, césures incorrectes. Résolu par des tables de correction OCR et la vérification croisée des lettres de section.

### 3. Faux positifs dans le corps du texte
Les biographies contiennent souvent des noms propres en gras majuscules (citations, références), créant de faux débuts. Résolu par le filtre de plage de lettres et la chaîne de validateurs.

### 4. Entrées fusionnées et renvois
Certaines entrées très courtes (renvois "Voir X") étaient collées à l'entrée suivante. Résolu par `split_merged_entries()` et le filtrage des renvois.

### 5. Noms multi-lignes
Certains noms avec des particules (VAN DER, DE LA) s'étendent sur deux lignes. Résolu par la détection des particules de nom et la fusion des lignes consécutives.

### 6. Volumes "suite"
Certains volumes sont la suite d'un précédent et commencent au milieu d'une lettre. Résolu par la détection du marqueur "(suite)" et l'inférence de la lettre de départ.
