# Biography Extractor

Automated extraction pipeline that segments individual biographies from scanned PDF volumes of the *Biographie Nationale de Belgique*. Each volume contains hundreds of biography entries in a two-column layout.

## Project Structure

```
extract_biographies.py   <- Entry point and pipeline orchestrator
constants.py             <- Word lists, regex patterns, font flag constants
config.py                <- ExtractionConfig dataclass (all tunable thresholds)
pdf_engine.py            <- PDF text extraction, layout detection, boundary detection
classifiers.py           <- Biography start detection, false positive / cross-ref filters
cleaner.py               <- Text cleaning, name extraction, filename generation
BioPdf/                  <- Input: place PDF volumes here
biographies_finales/     <- Output: one subfolder per volume (auto-created)
```

## Usage

```bash
pip install PyMuPDF

python extract_biographies.py

python extract_biographies.py -i my_pdfs/ -o my_output/
```

The script auto-detects all `*.pdf` files in `BioPdf/`, processes each one, and writes biographies to `biographies_finales/<pdf_stem>/`. Each biography becomes one `.txt` file named after the person (e.g. `BENTHAM (Jérémie).txt`).

All layout parameters are automatically detected per volume.

## Pipeline

```
BioPdf/*.pdf
 |
 v  (for each PDF)
+----------------------------------+
|  auto_detect_layout()            |  pdf_engine.py
|  Samples pages to detect:       |
|  - Column boundary (gap)        |
|  - Header Y zone                |
|  - Left/right indent ranges     |
+--------------+-------------------+
               v
+----------------------------------+
|  detect_boundaries()             |  pdf_engine.py
|  1. Scan for section letter      |
|     markers (centered A, B...)   |
|  2. Detect suite volumes         |
|     ("L (suite)")                |
|  3. Find front matter end        |
|  4. Detect TABLE DES boundary    |
|  5. Infer letter range           |
+--------------+-------------------+
               v
+----------------------------------+
|  extract_page_data()             |  pdf_engine.py
|  Per page:                       |
|  - Extract spans with font data  |
|  - Merge lines by Y-proximity   |
|  - Sort left col then right col  |
+--------------+-------------------+
               v
+----------------------------------+
|  is_biography_start()            |  classifiers.py
|  Validator chain (6 rules):      |
|  1. Bold uppercase name          |
|  2. Spaced small-caps (A B B E)  |
|  3. Indented + name pattern      |
|  4. Indented + italic            |
|  5. Name alone on line           |
|  6. After author attribution     |
|  Returns True/False/None         |
+--------------+-------------------+
               v
+----------------------------------+
|  collect_bio_starts()            |  extract_biographies.py
|  - Filter hyphenation breaks     |
|  - Merge multi-line names        |
|    (VAN, DE, DU particles)       |
+--------------+-------------------+
               v
+----------------------------------+
|  Segmentation & cleaning         |
|  - Split at each detected start  |
|  - Clean text (cleaner.py)       |
|  - Merge stubs (<60 chars)       |
|  - Split merged cross-refs       |
+--------------+-------------------+
               v
+----------------------------------+
|  Classification & output         |
|  - Skip cross-references (Voir)  |
|  - Skip false positives          |
|  - Filter by volume letter range |
|  - Write .txt files              |
+----------------------------------+
```

## Key Features

### Section Letter Detection
The pipeline scans for large, centered, bold letters (A, B, C...) that mark alphabetic sections. These determine:
- Where biographies begin (first section marker)
- The expected letter range for false positive filtering

### Suite Volume Support
Volumes continuing from a previous one (e.g. "L (suite)") are automatically detected. The starting letter is inferred from the suite marker.

### OCR Correction
Section letter markers are verified against actual biography names on nearby pages. OCR confusions (C/G, B/Β) are automatically corrected.

### TABLE DES / TABLE ALPHABÉTIQUE Detection
End-of-volume sections (TABLE ALPHABÉTIQUE DES NOTICES, ERRATA, TABLE DES MATIÈRES) are detected using two strategies:
1. **Forward header scan**: pages from 50% onward are checked for standalone section headers (short lines matching known keywords)
2. **Section letter regression**: if a section marker appears that is alphabetically before the volume's starting letter, it signals a TABLE section

Additionally, if section markers regress alphabetically, the biography range is truncated before that point.

### Letter Range Filtering
The volume's letter range is determined from section markers AND the actual last biography near the end of the volume. Entries whose first letter falls outside this range are rejected. Name particles (DE, VAN, DU, etc.) followed by an uppercase surname are never rejected by the standalone particle filter.

## Results

**5 132 biographies** extracted from **15 volumes** (letters A–N), each saved as an individual `.txt` file.

| Volume | Letters | Biographies |
|--------|---------|-------------|
| Volume 1 | A–B | 456 |
| Volume 2 | B | 453 |
| Volume 3 | B–C | 235 |
| Volume 4 | C–D | 426 |
| Volume 5 | D | 419 |
| Volume 6 | D–F | 383 |
| Volume 7 | F–G | 409 |
| Volume 8 | G–H | 332 |
| Volume 9 | H | 324 |
| Volume 10 | I–K | 236 |
| Volume 11 | L | 337 |
| Volume 12 | L (suite) | 214 |
| Volume 13 | M | 271 |
| Volume 14 | M (suite) | 262 |
| Volume 15 | M–N | 375 |
| **Total** | **A–N** | **5 132** |

## Configuration

All thresholds are in `ExtractionConfig` (`config.py`). Layout parameters are auto-detected per volume.

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `header_y` | 60.0 | Y below which lines are page headers (auto-detected) |
| `col_boundary` | 290.0 | X separating left/right columns (auto-detected) |
| `y_merge_tolerance` | 2.0 | Max Y-distance (pt) to merge split line spans |
| `min_bold_name_size` | 7.0 | Min font size for bold name detection |
| `section_letter_min_size` | 12.0 | Min font size for section letter markers |
| `end_section_search_pages` | 30 | Search range for end-section keywords |

## Dependencies

- Python 3.10+
- [PyMuPDF](https://pymupdf.readthedocs.io/) (`pip install PyMuPDF`)
