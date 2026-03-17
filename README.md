# Biography Extractor -- Scanned PDFs

Automated extraction pipeline that segments individual biographies from scanned PDF volumes of biographical dictionaries (e.g. *Biographie Nationale de Belgique*). These volumes contain hundreds of biography entries printed in a two-column layout with varying typographic conventions for entry headers.

## Project Structure

```
extract_biographies.py   <- CLI entry point + pipeline orchestrator
constants.py             <- Word lists, regex patterns, PyMuPDF font flag bits
config.py                <- ExtractionConfig dataclass (all tunable thresholds)
pdf_engine.py            <- PyMuPDF text extraction and page boundary detection
classifiers.py           <- Biography start detection, false positive / cross-ref filters
cleaner.py               <- Text cleaning, name extraction, filename generation
```

## Usage

```bash
# Single volume
python extract_biographies.py BiographieNationale_Volume1.pdf

# Multiple volumes (one subfolder per volume)
python extract_biographies.py Volume1.pdf Volume2.pdf Volume3.pdf

# Custom output directory
python extract_biographies.py -o output/ Volume1.pdf Volume2.pdf
```

With a single PDF, output goes to `biographies_finales/`. With multiple PDFs, each volume gets its own subfolder: `biographies_finales/<pdf_stem>/`. Each biography is one `.txt` file named after the person (e.g. `BENTHAM (Jérémie).txt`).

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

## How It Works

### Step 1 -- Page boundary detection (`pdf_engine.py`)

The PDF contains front matter (title page, preface, table of contents) and back matter (errata, index) surrounding the actual biography pages. Rather than hardcode page numbers, boundaries are auto-detected:

- **Forward scan**: iterates from page 0 onward. For each page, runs the full biography start detection logic and counts how many biography starts are found. The first page with `>= min_bio_starts_for_page_detection` (default 3) hits is selected as the start. The threshold of 3 avoids false positives from title pages that may contain one or two bold uppercase names incidentally (e.g. a publisher name like `THIRY-VAN BUGGENHOUDT, IMPRIMEUR-ÉDITEUR`).
- **Backward scan**: iterates backward from the last page, but only within the last `end_section_search_pages` (default 30) pages of the PDF. This avoids false matches on keywords like `ERRATA` or `TABLE DES` that appear incidentally in biography body text. Looks for end-section keywords (`ERRATA`, `TABLE DES`, `INDEX`) and stops at the first page that does *not* contain any keyword after a run of pages that do. If no end-section is found, uses the total page count.

### Step 2 -- Text extraction with font metadata (`pdf_engine.py`)

For each page in the detected range, `extract_page_data()` calls PyMuPDF's `page.get_text('dict')` to get every text span with its bounding box, font name, font size, and flag bits. The raw data is then processed:

1. **Header filtering**: lines with `y < header_y` (default 60pt) are discarded (running headers like page numbers and volume titles).
2. **Column assignment**: each line is assigned to left or right column based on whether its x-coordinate is below or above `col_boundary` (default 290pt).
3. **Y-merge**: PDF engines often split a single visual line into multiple span objects at slightly different y-coordinates. Lines within `y_merge_tolerance` (default 2pt) in the same column are merged into one logical line, preserving per-span font metadata.
4. **Ordering**: merged lines are sorted left-column-first, then by y-position within each column, producing a natural reading order.

Each logical line carries: `y`, `x`, `spans` (list of `{text, bold, italic, size, font}`), `full_text` (concatenated), and `page` index.

Bold and italic are detected via PyMuPDF's flag bits: `flags & (1 << 4)` for bold, `flags & (1 << 1)` for italic.

### Step 3 -- Biography start detection (`classifiers.py`)

This is the core of the pipeline. Each line is tested against a chain of 6 validators, stored in the `BIO_START_VALIDATORS` list. Each validator receives the current line, its neighbors (previous and next), and the config, and returns a tri-state result:

| Return | Meaning |
|--------|---------|
| `True` | This line is a biography start -- stop the chain |
| `False` | This line is definitely *not* a biography start -- stop the chain |
| `None` | Inconclusive -- pass to the next validator |

The `False` return is critical: it lets early validators block later ones. For example, if validator 1 (bold name) finds a bold span but determines it is a footnote attribution (small font at page bottom), it returns `False` to prevent validators 2-6 from incorrectly matching the same line.

**Validator 1 -- Bold uppercase name** (`_check_bold_name`): checks if the line starts with a bold span of sufficient size (`>= min_bold_name_size`, default 7pt) whose text is predominantly uppercase (at least `min_uppercase_ratio` = 50% and `min_uppercase_count` = 2 chars). Then checks for a continuation pattern: comma, parenthesis, or `ou` after the bold portion (either on the same line or the next). Returns `False` for attribution signatures (e.g. `A.-J. Nameche.`) based on font size and capitalization patterns.

**Validator 2 -- Spaced small-caps** (`_check_spaced_smallcaps`): detects names printed as spaced uppercase letters like `A B B É` (common in some volumes). Matched by regex `^[UC]( [UC]){2,}`, then checks for continuation on same/next line.

**Validator 3 -- Indented name pattern** (`_check_indented_name_pattern`): checks if the line's x-position falls within the biography indent range (`left_col_indent` or `right_col_indent`) and the text matches the uppercase name pattern `NAME, ...` or `NAME(...)`.

**Validator 4 -- Indented uppercase + italic** (`_check_indented_italic`): for volumes where the first name is in italic after an uppercase surname (e.g. `BENTHAM` *Jérémie*). Requires indentation, non-bold first span, uppercase surname, and italic or parenthesized continuation.

**Validator 5 -- Name alone on line** (`_check_name_alone`): catches cases where the surname sits alone on a line and the next line starts with `(` or `,`. Rejects Roman numeral sequences (`IVXLCDM`).

**Validator 6 -- After author attribution** (`_check_after_attribution`): detects a new biography that starts immediately after the previous one's author signature (e.g. `A.-J. Nameche.` followed by `BENTHAM, ...`). Requires the previous line to end with `.` and contain small bold text or a signature pattern.

### Step 4 -- Post-processing of starts (`extract_biographies.py`)

`collect_bio_starts()` applies two post-processing passes on the raw list of detected starts:

1. **Hyphenation filter**: if the previous line ends with `XX-` (uppercase hyphenation across lines, e.g. `BEAU-` / `MONT`), the start is a false positive caused by a broken word, not a new entry.
2. **Name continuation merge**: if two consecutive starts are within `max_merge_gap_lines` (default 2) lines of each other and the text between them ends with a name particle (`VAN`, `DE`, `DU`, `D'`, etc.), the second start is absorbed into the first. This handles multi-line names like `VAN DEN` / `BERGHE`.

### Step 5 -- Segmentation and text cleaning

**Segmentation**: the text between consecutive biography starts is extracted as one entry.

**Cleaning** (`cleaner.py`, `clean_biography_text()`):
1. Spaced uppercase names are collapsed (`A B B É` -> `ABBÉ`).
2. Hyphenated line breaks are rejoined: `biogra-\nphie` becomes `biographie` (only when the next line starts lowercase).
3. All lines are joined into a single flowing paragraph.
4. Multiple spaces are collapsed.
5. OCR corrections from `cfg.ocr_fixes` are applied (e.g. `ARIVOIIL` -> `ARNOUL`).

**Stub merging**: entries shorter than `stub_merge_max_chars` (default 60) are merged with the following entry, as they are typically incomplete first lines that got split.

**Voir-splitting**: entries that contain a cross-reference (`Voir ...`) followed by a new biography name are split into two separate entries.

### Step 6 -- Classification and output

Each entry is classified before writing:

- **Cross-references** (`is_cross_reference()`): entries containing `Voir` (or OCR variants like `VoirX`, `VO...`) under a length threshold are discarded.
- **False positives** (`is_false_positive()`): a battery of checks filters out fragments, Latin inscriptions (detected by uppercase ratio and known Latin words), footnotes, Roman numerals, author attribution lines, and entries starting with lowercase or fragment-starter words (`Il`, `Elle`, `Son`, `Les`, etc.).

Surviving entries get a filename derived from the extracted name (`extract_filename()`), with OCR spacing fixes, trailing phrase cleanup, and filesystem-unsafe character replacement. Duplicate filenames are suffixed with `(1)`, `(2)`, etc.

Each biography is written as a single `.txt` file. With a single PDF, files go to `biographies_finales/`. With multiple PDFs, each volume gets a subfolder: `biographies_finales/<pdf_stem>/`.

## Configuration

All thresholds live in `ExtractionConfig` (`config.py`). Key parameters:

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `header_y` | 60.0 | Y-coordinate below which lines are page headers |
| `col_boundary` | 290.0 | X-coordinate separating left/right columns |
| `y_merge_tolerance` | 2.0 | Max Y-distance (pt) to merge split line spans |
| `left_col_indent` | (146, 165) | X-range for biography start indentation (left col) |
| `right_col_indent` | (308, 330) | X-range for biography start indentation (right col) |
| `min_bold_name_size` | 7.0 | Min font size for bold name detection |
| `max_attribution_size` | 7.5 | Max font size to consider as author attribution |
| `min_bio_starts_for_page_detection` | 3 | Min biography starts on a page to accept it as start |
| `end_section_search_pages` | 30 | Only search for end-section keywords in last N pages |
| `ocr_fixes` | `{"ARIVOIIL": "ARNOUL"}` | Text-level OCR corrections |
| `filename_ocr_fixes` | ... | Filename-level OCR corrections |

## Adding Detection Rules

Biography start validators live in the `BIO_START_VALIDATORS` list (`classifiers.py`). To add a new rule, write a function with the standard signature and append it:

```python
def _check_custom(line_data, cfg, next_line_data, prev_line_data):
    """Custom detection rule."""
    # line_data keys: y, x, spans, full_text, page
    # Each span: {text, bold, italic, size, font}
    # Return True (match), False (block), or None (pass)
    ...

BIO_START_VALIDATORS.append(_check_custom)
```

The position in the list matters: validators are evaluated in order and the chain stops on the first `True` or `False`.

## Dependencies

- Python 3.10+
- [PyMuPDF](https://pymupdf.readthedocs.io/) (`pip install PyMuPDF`)
