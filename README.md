# Biography Extractor -- Scanned PDFs

Automated extraction pipeline that segments individual biographies from scanned PDF volumes (e.g. *Biographie Nationale de Belgique*).

## Project Structure

```
extract_biographies.py   <- CLI entry point + orchestrator
constants.py             <- Word lists, regex patterns, PyMuPDF flags
config.py                <- ExtractionConfig dataclass
pdf_engine.py            <- PyMuPDF extraction (spans, lines, columns)
classifiers.py           <- Biography start detection, false positives, cross-refs
cleaner.py               <- Text cleaning, name extraction, filename generation
```

## Usage

```bash
python extract_biographies.py BiographieNationale_Volume1.pdf
```

Page boundaries are auto-detected: forward scan finds the first page with multiple biography starts, backward scan looks for ERRATA/INDEX sections.

## Extraction Flow

```
PDF
 |
 v
+----------------------------------+
|  1. detect_boundaries()          |  pdf_engine.py
|     Forward scan: find first     |
|     page with >= N biography     |
|     starts                       |
|     Backward scan: look for      |
|     ERRATA / INDEX / TABLE DES   |
+--------------+-------------------+
               v
+----------------------------------+
|  2. extract_page_data()          |  pdf_engine.py
|     For each page:               |
|     - Extract spans with font    |
|       metadata (bold, italic,    |
|       size, font name)           |
|     - Merge lines by Y-proximity |
|       (configurable tolerance)   |
|     - Sort left column then      |
|       right column               |
+--------------+-------------------+
               v
+----------------------------------+
|  3. is_biography_start()         |  classifiers.py
|     Validator chain:             |
|     +-------------------------+  |
|     | 1. Bold uppercase name  |  |
|     | 2. Spaced small-caps    |  |
|     |    (A B B E)            |  |
|     | 3. Indented + name      |  |
|     |    pattern (NAME, ...)  |  |
|     | 4. Indented + italic    |  |
|     | 5. Name alone on line   |  |
|     | 6. After author         |  |
|     |    attribution          |  |
|     +-------------------------+  |
|     Each validator returns:      |
|     True  -> biography start     |
|     False -> stop (not a bio)    |
|     None  -> try next validator  |
+--------------+-------------------+
               v
+----------------------------------+
|  4. collect_bio_starts()         |  extract_biographies.py
|     - Filter false starts caused |
|       by hyphenation             |
|     - Merge names spanning       |
|       2 lines (particles:        |
|       VAN, DE, DU...)            |
+--------------+-------------------+
               v
+----------------------------------+
|  5. Segmentation & cleaning      |
|     - Split text between each    |
|       detected start             |
|     - clean_biography_text()     |  cleaner.py
|       Rejoin hyphens, merge      |
|       lines, apply OCR fixes     |
|     - Merge stubs                |
|       (entries < 60 chars)       |
|     - Split merged entries       |
|       (cross-ref + bio)          |
+--------------+-------------------+
               v
+----------------------------------+
|  6. Classification & output      |
|     - is_cross_reference()       |  classifiers.py
|       -> discard "Voir X"        |
|     - is_false_positive()        |  classifiers.py
|       -> discard fragments,      |
|         latin text, footnotes    |
|     - extract_filename()         |  cleaner.py
|       -> safe filename           |
|     - Write each biography to    |
|       biographies_finales/       |
+----------------------------------+
```

## Adding Detection Rules

Biography start validators live in the `BIO_START_VALIDATORS` list (`classifiers.py`). To add a rule:

```python
def _check_custom(line_data, cfg, next_line_data, prev_line_data):
    """Custom detection rule."""
    # return True / False / None
    ...

BIO_START_VALIDATORS.append(_check_custom)
```

## Dependencies

- Python 3.10+
- [PyMuPDF](https://pymupdf.readthedocs.io/) (`pip install PyMuPDF`)
