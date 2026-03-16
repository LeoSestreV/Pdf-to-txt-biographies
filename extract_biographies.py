#!/usr/bin/env python3
"""
Extract biographies from scanned PDF volumes of biographical dictionaries.

Uses PyMuPDF font metadata (bold detection) combined with text pattern matching
and indentation analysis to reliably segment biography entries.

Usage:
    python extract_biographies.py volume1_config.json
    python extract_biographies.py my_document.pdf --start-page 41 --end-page 469
    python extract_biographies.py -c config.json --output-dir output/
"""

import argparse
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

# ── PyMuPDF font flag bits (library constants, not document-specific) ────────

PYMUPDF_BOLD_BIT = 1 << 4
PYMUPDF_ITALIC_BIT = 1 << 1

# ── Uppercase character class for regex (Western European + accented) ────────

UC = r'A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖÙÚÛÜÝÞ'


# ── Configuration ────────────────────────────────────────────────────────────


@dataclass
class ExtractionConfig:
    """All tunable parameters for biography extraction.

    Every threshold, size, and document-specific value lives here.
    Defaults match the Biographie Nationale Volume 1 layout.
    Load per-volume overrides via ``ExtractionConfig.from_json(path)``.
    """

    # -- Input / Output -------------------------------------------------------
    pdf_path: str = ""
    output_dir: str = "biographies_finales"
    log_file: str = "rapport_final.log"
    report_title: str = "RAPPORT D'EXTRACTION"

    # -- Page range (0-indexed) -----------------------------------------------
    start_page: int = 0
    end_page: int | None = None  # None → last page of the document

    # -- Page layout geometry -------------------------------------------------
    header_y: float = 60.0       # lines above this y are headers → skip
    footer_y: float = 590.0      # (reserved for future use)
    col_boundary: float = 290.0  # x < this → left column
    y_merge_tolerance: float = 2.0  # merge lines within this y-distance
    left_col_indent: tuple[float, float] = (146.0, 165.0)   # (min, max)
    right_col_indent: tuple[float, float] = (308.0, 330.0)

    # -- Font detection thresholds --------------------------------------------
    min_bold_name_size: float = 7.0   # bold spans must be ≥ this to count
    max_attribution_size: float = 7.5  # bold < this at page bottom → attribution
    footnote_y: float = 350.0         # y > this + small font → footnote
    min_uppercase_ratio: float = 0.5   # fraction of uppercase in bold name
    min_uppercase_count: int = 2       # minimum uppercase chars in bold name

    # -- Text length thresholds -----------------------------------------------
    stub_merge_max_chars: int = 60    # stubs shorter → merge with next
    min_entry_chars: int = 30         # entries shorter → false positive
    short_entry_chars: int = 100      # for all-caps / latin check
    alert_min_chars: int = 150        # entries shorter → log alert
    xref_max_chars: int = 300         # "Voir" entries shorter → cross-ref
    xref_garbled_max_chars: int = 200  # garbled "Voir" variants
    latin_sample_chars: int = 300     # sample size for latin detection
    latin_uppercase_ratio: float = 0.8
    min_alpha_for_latin: int = 30     # need this many alpha chars to check

    # -- Name extraction ------------------------------------------------------
    min_name_length: int = 3          # names shorter → rejected
    max_name_alone_length: int = 50   # name-alone lines longer → not a name
    max_name_chars: int = 80          # trigger truncation above this
    max_filename_chars: int = 90      # truncate filenames above this
    fallback_name_chars: int = 60     # chars from first comma as fallback
    header_lines_count: int = 5       # how many lines to examine for name

    # -- Merge & split thresholds ---------------------------------------------
    max_merge_gap_lines: int = 2      # max line gap for name-continuation merge
    split_part1_min_chars: int = 10   # min size for part1 in voir-split
    split_part2_min_chars: int = 50   # min size for part2 in voir-split
    author_attrib_max_size: int = 100  # max chars for author-attribution fp

    # -- Document-specific OCR corrections ------------------------------------
    ocr_fixes: dict[str, str] = field(default_factory=lambda: {
        'ARIVOIIL': 'ARNOUL',
    })
    filename_ocr_fixes: dict[str, str] = field(default_factory=lambda: {
        'DETO -LÉDE': 'DE TOLÈDE',
        'DETO-LÉDE': 'DE TOLÈDE',
        'ARIVOIIL': 'ARNOUL',
    })

    # -- Extensible word lists ------------------------------------------------
    # These extend (not replace) the built-in French defaults.
    extra_descriptors: list[str] = field(default_factory=list)
    extra_blacklisted_starts: list[str] = field(default_factory=list)
    extra_fragment_starters: list[str] = field(default_factory=list)
    extra_latin_fragments: list[str] = field(default_factory=list)
    extra_latin_indicators: list[str] = field(default_factory=list)

    @classmethod
    def from_json(cls, path: str | Path) -> "ExtractionConfig":
        """Load configuration from a JSON file.  Missing keys use defaults."""
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        # Convert list → tuple for indent ranges
        for key in ("left_col_indent", "right_col_indent"):
            if key in raw and isinstance(raw[key], list):
                raw[key] = tuple(raw[key])
        return cls(**{k: v for k, v in raw.items() if k in cls.__dataclass_fields__})

    def resolve_end_page(self, doc_page_count: int) -> int:
        """Return the effective end page (exclusive)."""
        return self.end_page if self.end_page is not None else doc_page_count


# ── Default word lists (French biographical dictionaries) ────────────────────

_BASE_DESCRIPTORS = frozenset({
    'abbé', 'abbesse', 'administrateur', 'agronome', 'amiral', 'ancien',
    'annaliste', 'antiquaire', 'apôtre', 'architecte', 'archéologue',
    'arrière', 'artisan', 'artiste', 'artistes', 'astronome', 'auteur',
    'baron', 'baronne', 'bienfaiteur', 'bienheureux', 'biographe',
    'bourgmestre', 'bourgeois', 'bénédictin', 'belge',
    'calligraphe', 'calligraphes', 'capitaine', 'cardinal', 'cartographe',
    'célèbre', 'chanoine', 'chantre', 'chapelain', 'chef', 'chevalier',
    'chirurgien', 'chroniqueur', 'chronologiste', 'coadjuteur', 'colonel',
    'combattant', 'commerçant', 'commandant', 'commandeur', 'commentateur',
    'compilateur', 'compositeur', 'comte', 'comtesse', 'confesseur',
    'conseiller', 'constructeur', 'consul', 'controversiste', 'coseigneur',
    'curé',
    'dame', 'dessinateur', 'diplomate', 'directeur', 'docteur', 'dominicain',
    'dont', 'doyen', 'duc', 'duchesse', 'décédé', 'défenseur',
    'ecclésiastique', 'empereur', 'enseigna', 'ermite', 'escrimeur',
    'est', 'ethnologue', 'exploitant',
    'évêque', 'écolâtre', 'écrivain', 'érudit', 'époux', 'épouse', 'était',
    'facteur', 'feld', 'feldmaréchal', 'femme', 'fils', 'financier', 'fille',
    'florissait', 'fondateur', 'fondatrice', 'forme', 'frère', 'fut',
    'gardien', 'gentilhomme', 'gouverneur', 'grammairien', 'graveur',
    'greffier', 'guerrier', 'général', 'géographe', 'géologue',
    'hagiographe', 'helléniste', 'héraldiste', 'historien', 'homme',
    'humaniste', 'hébraïsant',
    'il', 'imprimeur', 'industriel', 'ingénieur', 'instituteur',
    'jésuite', 'jurisconsulte', 'juriste',
    'lazariste', 'lecteur', 'libraire', 'licencié', 'littérateur',
    'lieutenant', 'luthiste',
    'magistrat', 'major', 'marchand', 'marquis', 'maréchal',
    'mathématicien', 'maître', 'membre', 'militaire', 'minéralogiste',
    'ministre', 'missionnaire', 'moine', 'moraliste', 'musicien', 'médecin',
    'ménestrel',
    'naquit', 'navigateur', 'neveu', 'noble', 'nommé', 'notaire', 'né',
    'née', 'négociateur',
    'officier', 'on', 'organiste', 'orientaliste', 'ornithologue',
    'patriote', 'patron', 'peintre', 'peintres', 'personnage', 'philologue',
    'philosophe', 'physicien', 'plus', 'poète', 'poëte', 'prédicateur',
    'président', 'prêtre', 'prince', 'princesse', 'prieur', 'procureur',
    'professeur', 'protonotaire', 'prévôt', 'publiciste',
    'recteur', 'religieux', 'religieuse', 'roi', 'reine', 'récollet',
    'savant', 'sculpteur', 'secrétaire', 'seigneur', 'sénateur', 'sire',
    'soldat', 'statuaire', 'successivement', 'surnommé',
    'théologien', 'théoricien', 'topographe', 'trouvère',
    'vicaire', 'vit', 'vivait', 'voyageur',
    'premier', 'première', 'deuxième', 'troisième', 'quatrième',
    'cinquième', 'sixième', 'septième', 'huitième', 'neuvième',
    'dixième', 'onzième', 'douzième', 'treizième', 'quatorzième',
    'quinzième', 'seizième', 'dix-septième', 'dix-huitième',
    'dix-neuvième', 'vingtième', 'vingt', 'trentième', 'trente',
    'quarantième', 'quarante', 'cinquantième', 'cinquante',
    'soixantième', 'soixante',
})

_BASE_NAME_PARTICLES = frozenset({
    'DE', 'DU', 'DES', 'LE', 'LA', 'LES', 'VAN', 'DEN', 'DER',
    'VANDER', 'VANDEN', 'OU', 'ET', 'D', 'VON', 'VER', 'TER',
})

_BASE_NAME_LINKS = frozenset({
    'ou', 'dit', 'dite', 'surnommé', 'nommé', 'appelé', 'appelée',
})

_BASE_FRAGMENT_STARTERS = frozenset({
    'Il', 'Elle', 'Son', 'Sa', 'Ses', 'Les', 'Le', 'La', 'Un', 'Une',
    'Ce', 'Cette', 'Ces', 'On', 'Nous', 'Des', 'Du', 'En', 'Au',
    'Après', 'Avant', 'Dans', 'Sous', 'Sur', 'Par', 'Pour', 'Avec',
    'Parmi', 'Selon',
})

_BASE_BLACKLISTED_STARTS = frozenset({
    'IDEM', 'DOMINUS', 'FEBRUARII', 'ITEM', 'ANNO', 'OBIIT',
    'HIC', 'LIBER', 'HUJUS', 'DIXIT',
})

_BASE_LATIN_FRAGMENT_WORDS = frozenset({
    'INCLYTA', 'GESTA', 'CECINIT', 'TRIUMPHOS', 'NATURASI', 'MORES',
    'MYSTICA', 'VERBA', 'DEI', 'ARTES', 'DEPINGENS', 'MILITIAMQUE',
    'POLI', 'ELOQUII', 'PICTOR', 'HORUM', 'CENSOR', 'CYTIIARISTA',
    'PYERIDUM', 'PIDEI', 'ERAT', 'REQUIES', 'ANIMÆ', 'COELESTI',
    'DETUR', 'ARCE', 'EXOPTAT', 'ROGITES', 'LECTOR', 'AMICE', 'DEUM',
    'EGREGIE', 'SCRIBENS', 'PLANXIT', 'DOCUIT', 'CULTOR', 'CUBAT',
    'ALANUS', 'DOCTOR', 'QUEM', 'DECET', 'ALMUS', 'HONOR',
})

_BASE_LATIN_INDICATORS = frozenset({
    'ET', 'QUI', 'QUOD', 'HIC', 'EST', 'FUIT', 'OBIIT',
    'ANNO', 'DOMINI', 'JACET', 'CUBAT', 'HUJUS', 'POST',
    'DIXIT', 'PONDUS', 'DOCUIT', 'CULTOR', 'FILIT',
})

_BASE_STANDALONE_PARTICLES = frozenset({
    'VAN', 'DE', 'DU', 'DES', 'LE', 'LA', 'LES', 'DEN', 'DER',
})

_BASE_SPACED_PARTICLES = [
    (r'\bD E S\b', 'DES'), (r'\bD E N\b', 'DEN'), (r'\bD E R\b', 'DER'),
    (r'\bV A N\b', 'VAN'), (r'\bV O N\b', 'VON'), (r'\bL E S\b', 'LES'),
    (r'\bD E\b', 'DE'), (r'\bD U\b', 'DU'),
    (r'\bL E\b', 'LE'), (r'\bL A\b', 'LA'),
]

_BASE_TRAILING_PATTERNS = [
    r',?\s+dont\s+.*$',
    r',?\s+communément\s*$',
    r',?\s+mais\s*$',
    r',?\s+Belge\s+de\s+naissance\s*$',
    r",?\s+chroni\w*,?\s+qui\b.*$",
    r",?\s+'\s*$",
    r',?\s+aussi\b.*$',
]

_BASE_FRENCH_STOP_WORDS = frozenset({
    'ou', 'et', 'de', 'du', 'des', 'le', 'la', 'les', 'en', 'a', 'y',
})

_BASE_NAME_CONTINUATION_PAIRS = frozenset({
    'ou le', 'ou la', 'ou les', 'ou l', 'dit le', 'dit la',
    'dite la', 'dite le', 'nommé le', 'nommé la',
})


def _build_word_sets(cfg: ExtractionConfig):
    """Build effective word sets by merging base sets with config extras."""
    return {
        'descriptors': _BASE_DESCRIPTORS | frozenset(cfg.extra_descriptors),
        'blacklisted': _BASE_BLACKLISTED_STARTS | frozenset(cfg.extra_blacklisted_starts),
        'fragment_starters': _BASE_FRAGMENT_STARTERS | frozenset(cfg.extra_fragment_starters),
        'latin_fragments': _BASE_LATIN_FRAGMENT_WORDS | frozenset(cfg.extra_latin_fragments),
        'latin_indicators': _BASE_LATIN_INDICATORS | frozenset(cfg.extra_latin_indicators),
    }


# ── Page data extraction ────────────────────────────────────────────────────


def _extract_spans(line):
    """Extract non-empty spans with font metadata from a PDF line object."""
    return [
        {
            'text': s['text'],
            'bold': bool(s['flags'] & PYMUPDF_BOLD_BIT),
            'italic': bool(s['flags'] & PYMUPDF_ITALIC_BIT),
            'size': s['size'],
            'font': s['font'],
        }
        for s in line['spans']
        if s['text'].strip()
    ]


def _merge_span_groups(groups):
    """Merge grouped span lists into final line data objects."""
    groups.sort(key=lambda g: (0 if g[3] else 1, g[0], g[1]))

    lines_data = []
    for min_y, min_x, spans_list, _is_left in groups:
        spans_list.sort(key=lambda t: t[0])
        merged_spans = []
        for k, (_, sp) in enumerate(spans_list):
            if k > 0 and merged_spans:
                last_text = merged_spans[-1]['text']
                first_text = sp[0]['text'] if sp else ''
                if last_text and not last_text.endswith(' ') and \
                   first_text and not first_text.startswith(' '):
                    merged_spans.append({
                        'text': ' ', 'bold': False, 'italic': False,
                        'size': 0, 'font': '',
                    })
            merged_spans.extend(sp)

        full_text = ''.join(s['text'] for s in merged_spans).strip()
        lines_data.append({
            'y': min_y,
            'x': min_x,
            'spans': merged_spans,
            'full_text': full_text,
            'has_bold_start': merged_spans[0]['bold'] if merged_spans else False,
            'page': 0,
        })
    return lines_data


def extract_page_data(page, page_idx, cfg: ExtractionConfig):
    """Extract text spans with metadata from a page.

    Merges line objects that share the same y-position (within tolerance)
    into a single logical line, sorted by x-position.
    """
    raw_lines = []
    for b in page.get_text('dict')['blocks']:
        if 'lines' not in b:
            continue
        for line in b['lines']:
            y_top = line['bbox'][1]
            if y_top < cfg.header_y:
                continue
            spans = _extract_spans(line)
            if spans:
                raw_lines.append((y_top, line['bbox'][0], spans))

    raw_lines.sort(key=lambda t: (t[0], t[1]))

    groups = []
    for y, x, spans in raw_lines:
        is_left = x < cfg.col_boundary
        merged = False
        for g in groups:
            if abs(y - g[0]) <= cfg.y_merge_tolerance and is_left == g[3]:
                g[2].append((x, spans))
                g[0] = min(g[0], y)
                g[1] = min(g[1], x)
                merged = True
                break
        if not merged:
            groups.append([y, x, [(x, spans)], is_left])

    lines_data = _merge_span_groups(groups)
    for ld in lines_data:
        ld['page'] = page_idx
    return lines_data


# ── Detection helpers ────────────────────────────────────────────────────────


def get_first_real_span(spans):
    """Get the first non-empty, non-asterisk span."""
    for s in spans:
        text = s['text'].strip()
        if text and text != '*':
            return s
    return spans[0] if spans else None


def is_indented_for_bio(x, cfg: ExtractionConfig):
    """Check if x-position corresponds to biography start indentation."""
    lo, hi = cfg.left_col_indent if x < cfg.col_boundary else cfg.right_col_indent
    return lo <= x <= hi


def has_name_pattern(text, cfg: ExtractionConfig):
    """Check if text starts with an uppercase name followed by ( or , or 'ou'."""
    text = re.sub(r'^\*\s*', '', text).strip()
    if re.match(rf'^[{UC}][{UC}\s\-\'\.]+\s*(\(|,|ou\s)', text):
        name_part = re.split(r'[,(]', text)[0].strip()
        name_clean = re.sub(r'[\s\-\'\.]+', '', name_part)
        if (len(name_clean) >= cfg.min_name_length and
                not re.match(r'^[IVXLCDM]+$', name_clean)):
            return True
    return False


# ── Biography start detection ────────────────────────────────────────────────


def _check_bold_name(spans, first, full, y, next_line_data, cfg: ExtractionConfig):
    """Method 1: Bold uppercase name detection.

    Returns True (is bio start), False (definitely not), or None (inconclusive).
    """
    if not (first['bold'] and first['size'] >= cfg.min_bold_name_size):
        return None

    bold_parts = []
    for s in spans:
        if s['bold']:
            bold_parts.append(s['text'])
        else:
            break
    bold_name = ''.join(bold_parts).strip()

    name_clean = re.sub(r'[\s\-\'\.,;:\(\)\*\"I]', '', bold_name)
    if not name_clean:
        return False
    upper_count = sum(1 for c in name_clean if c.isupper())
    if (len(name_clean) == 0 or
            upper_count / len(name_clean) < cfg.min_uppercase_ratio or
            upper_count < cfg.min_uppercase_count):
        return None

    rest = full[len(bold_name):].strip()
    if bold_name.rstrip().endswith('('):
        rest = '(' + rest

    if first['size'] < cfg.min_bold_name_size and y > cfg.footnote_y:
        return False

    if (re.match(r'^[A-Z][a-z]*[\.\-]\s*[A-Z]', bold_name) and
            first['size'] < cfg.max_attribution_size):
        return False

    has_comma = ',' in bold_name
    if (rest.startswith('(') or rest.startswith(',') or
        re.match(r'^ou\s', rest, re.IGNORECASE) or
        bold_name.rstrip().endswith(',') or
        bold_name.rstrip().endswith('(') or
            has_comma):
        return True

    if next_line_data:
        next_full = next_line_data['full_text'].strip()
        if next_full.startswith('(') or next_full.startswith(','):
            return True
        if re.match(r'^ou\s', next_full, re.IGNORECASE):
            return True

    return None


def _check_spaced_smallcaps(first, full, next_line_data):
    """Method 2: Spaced small-caps pattern (A B B É)."""
    check_text = re.sub(r'^\*\s*', '', first['text'].strip())
    if not re.match(rf'^[{UC}]( [{UC}]){{2,}}', check_text):
        return False

    rest = full[len(first['text'].strip()):].strip()
    if (rest.startswith('(') or rest.startswith(',') or
            re.match(r'^ou\s', rest, re.IGNORECASE)):
        return True
    if next_line_data:
        next_full = next_line_data['full_text'].strip()
        if next_full.startswith('(') or next_full.startswith(','):
            return True
    return False


def _check_indented_italic(x, spans, cfg: ExtractionConfig):
    """Method 4: Indented UPPERCASE + italic prénom pattern."""
    if not (is_indented_for_bio(x, cfg) and len(spans) >= 2):
        return False

    first_real = get_first_real_span(spans)
    if not first_real or first_real['bold']:
        return False

    ft = first_real['text'].strip().lstrip('*').strip()
    ft_name = re.sub(r'\s*\(\s*$', '', ft).strip()
    if not (re.match(rf'^[{UC}][{UC}\-\' ]+$', ft_name) and
            len(ft_name) >= cfg.min_name_length and
            not re.match(r'^[IVXLCDM\s]+$', ft_name)):
        return False

    for s in spans:
        if s is first_real:
            continue
        next_text = s['text'].strip()
        if not next_text:
            continue
        if s['italic'] or next_text.startswith('(') or next_text.startswith(','):
            return True
        break
    return False


def _check_name_alone(full, next_line_data, cfg: ExtractionConfig):
    """Method 5: Name alone on a line, next line starts with ( or ,."""
    full_stripped = full.replace('*', '').strip()
    if not (re.match(rf'^[{UC}][{UC}\s\-\'\.]+$', full_stripped) and
            cfg.min_name_length <= len(full_stripped) <= cfg.max_name_alone_length and
            not re.match(r'^[IVXLCDM\s]+$', full_stripped)):
        return False

    if not next_line_data:
        return False
    next_full = next_line_data['full_text'].strip()
    return (next_full.startswith('(') or next_full.startswith(',') or
            bool(re.match(r'^\([^)]+\)', next_full)))


def _check_after_attribution(full, prev_line_data, cfg: ExtractionConfig):
    """Method 6: Name pattern preceded by author attribution."""
    if not (prev_line_data and has_name_pattern(full, cfg)):
        return False

    prev_full = prev_line_data['full_text'].strip()
    prev_spans = prev_line_data['spans']

    if not prev_full.endswith('.'):
        return False

    last_bold_spans = [s for s in prev_spans if s['bold'] and s['text'].strip()]
    if last_bold_spans and max(s['size'] for s in last_bold_spans) < cfg.max_attribution_size:
        return True

    if re.search(r'[A-Z][a-z]*[\.\-]\s*[A-Z][a-zà-ÿ]+\.\s*$', prev_full):
        return True
    if re.search(r'[A-Z][a-z]*\.\s*[a-z]+[«»]+\.\s*$', prev_full):
        return True
    if re.search(r'\bVoir\b.*\.\s*$', prev_full):
        return True

    return False


def is_biography_start(line_data, cfg: ExtractionConfig,
                       next_line_data=None, prev_line_data=None):
    """Detect if a line is the start of a new biography entry."""
    spans = line_data['spans']
    full = line_data['full_text']
    x = line_data['x']
    y = line_data['y']

    if not spans or not full:
        return False

    first = get_first_real_span(spans)
    if not first:
        return False

    bold_result = _check_bold_name(spans, first, full, y, next_line_data, cfg)
    if bold_result is True:
        return True
    if bold_result is False:
        return False
    if _check_spaced_smallcaps(first, full, next_line_data):
        return True
    if is_indented_for_bio(x, cfg) and has_name_pattern(full, cfg):
        return True
    if _check_indented_italic(x, spans, cfg):
        return True
    if _check_name_alone(full, next_line_data, cfg):
        return True
    if _check_after_attribution(full, prev_line_data, cfg):
        return True

    return False


# ── Name continuation & merging ──────────────────────────────────────────────


def is_name_continuation(prev_text, curr_text):
    """Check if curr_text continues the name started in prev_text."""
    prev = prev_text.strip()
    last_word = prev.rstrip('.,;:').split()[-1] if prev.split() else ''
    if last_word.upper() in _BASE_NAME_PARTICLES:
        return True
    if prev.rstrip().endswith("D'") or prev.rstrip().endswith("d'"):
        return True
    if re.search(rf'[{UC}]{{2,}}-$', prev.rstrip()):
        return True

    last_two = ' '.join(prev.rstrip('.,;:').split()[-2:]) if len(prev.split()) >= 2 else ''
    return last_two.lower() in _BASE_NAME_CONTINUATION_PAIRS


# ── Collection & segmentation ────────────────────────────────────────────────


def collect_bio_starts(doc, cfg: ExtractionConfig):
    """Scan all biography pages and collect starts, merging split names."""
    end_page = cfg.resolve_end_page(len(doc))

    all_lines = []
    for pidx in range(cfg.start_page, end_page):
        for ld in extract_page_data(doc[pidx], pidx, cfg):
            all_lines.append((len(all_lines), pidx, ld))

    bio_starts = []
    for i, (gidx, pidx, ld) in enumerate(all_lines):
        next_ld = all_lines[i + 1][2] if i + 1 < len(all_lines) else None
        prev_ld = all_lines[i - 1][2] if i > 0 else None
        if is_biography_start(ld, cfg, next_ld, prev_ld):
            bio_starts.append((gidx, pidx, ld))

    # Post-process 1: Remove false starts caused by hyphenation
    bio_starts = [
        (gidx, pidx, ld) for gidx, pidx, ld in bio_starts
        if gidx == 0 or not re.search(rf'[{UC}]{{2,}}-$',
                                       all_lines[gidx - 1][2]['full_text'].rstrip())
    ]

    # Post-process 2: Merge when gap ≤ max_merge_gap_lines and prev ends with particle
    merged = []
    skip_next = False
    for i, (gidx, pidx, ld) in enumerate(bio_starts):
        if skip_next:
            skip_next = False
            continue

        if i + 1 < len(bio_starts):
            next_gidx = bio_starts[i + 1][0]
            next_ld = bio_starts[i + 1][2]
            gap = next_gidx - gidx

            if gap <= cfg.max_merge_gap_lines:
                between_text = ' '.join(
                    all_lines[j][2]['full_text']
                    for j in range(gidx, next_gidx) if j < len(all_lines)
                )
                if 'Voir' not in between_text:
                    prev_text = all_lines[next_gidx - 1][2]['full_text'] if next_gidx - 1 >= 0 else ''
                    if is_name_continuation(prev_text, next_ld['full_text']):
                        skip_next = True

        merged.append((gidx, pidx, ld))

    return all_lines, merged


def extract_bio_text(all_lines, start_gidx, end_gidx):
    """Extract the raw text lines between two global line indices."""
    return [
        ld['full_text']
        for gidx, _, ld in all_lines
        if start_gidx <= gidx < end_gidx
    ]


# ── Text cleaning ────────────────────────────────────────────────────────────


def collapse_spaced_names(text):
    """Collapse 'A B B É' -> 'ABBÉ'."""
    def _collapse(m):
        prefix = m.group(1) or ''
        spaced = m.group(0)[len(prefix):]
        return prefix + re.sub(r'(?<=\w) (?=\w)', '', spaced)

    return re.sub(
        rf'^(\*\s*)?([{UC}] ){{2,}}[{UC}][{UC}]*',
        _collapse, text, flags=re.MULTILINE
    )


def clean_biography_text(raw_lines, cfg: ExtractionConfig):
    """Clean biography text into continuous flowing text."""
    text = collapse_spaced_names('\n'.join(raw_lines))

    text = re.sub(
        r'(\w)-\n(\w)',
        lambda m: m.group(1) + m.group(2) if m.group(2)[0].islower() else m.group(0),
        text
    )

    parts = []
    for line in text.split('\n'):
        line = line.strip()
        if line:
            if parts:
                parts.append(' ')
            parts.append(line)

    text = re.sub(r'[ \t]+', ' ', ''.join(parts)).strip()
    for old, new in cfg.ocr_fixes.items():
        text = text.replace(old, new)
    return text


# ── Name extraction ──────────────────────────────────────────────────────────


def _join_header_lines(raw_lines, cfg: ExtractionConfig):
    """Join first few lines handling hyphenation for name extraction."""
    header_lines = [
        collapse_spaced_names(line.strip())
        for line in raw_lines[:cfg.header_lines_count]
        if line.strip()
    ]
    if not header_lines:
        return ''

    joined = ''
    for line in header_lines:
        if joined and joined.endswith('-'):
            if line and line[0].islower():
                joined = joined[:-1] + line
            elif line and line[0].isupper() and re.search(rf'[{UC}]{{2,}}-$', joined):
                joined = joined[:-1] + line
            else:
                joined += line
        elif joined:
            joined += ' ' + line
        else:
            joined = line

    return re.sub(r'^\*\s*', '', joined).strip()


def _find_name_end(joined, words: dict):
    """Find the end position of the name in the joined header text."""
    descriptors = words['descriptors']
    paren_depth = 0
    i = 0
    while i < len(joined):
        ch = joined[i]
        if ch == '(':
            footnote_match = re.match(r'\([IVX\d]{1,3}\)', joined[i:])
            if footnote_match:
                pos = i
                while pos > 0 and joined[pos - 1] in ' ,':
                    pos -= 1
                return pos
            paren_depth += 1
            i += 1
            continue
        elif ch == ')':
            paren_depth = max(0, paren_depth - 1)
            i += 1
            continue

        if paren_depth == 0:
            if ch == '.' and i + 1 < len(joined) and joined[i + 1] == ' ':
                before = joined[:i].rstrip()
                if before and not re.search(r'\b[A-Z]$', before):
                    return i + 1

            if i > 0 and joined[i - 1] in ' ,)':
                word_match = re.match(
                    r'[a-zàáâãäåæçèéêëìíîïðñòóôõöùúûüýþé]+', joined[i:])
                if word_match:
                    word = word_match.group(0)
                    if word in descriptors:
                        pos = i
                        while pos > 0 and joined[pos - 1] in ' ,':
                            pos -= 1
                        return pos
                    if joined[i - 1] == ')' or (i > 1 and ')' in joined[max(0, i - 5):i]):
                        if word not in _BASE_NAME_LINKS:
                            pos = i
                            while pos > 0 and joined[pos - 1] in ' ,':
                                pos -= 1
                            return pos
        i += 1

    return len(joined)


def extract_name_from_lines(raw_lines, cfg: ExtractionConfig, words: dict):
    """Extract the biography name from raw lines."""
    joined = _join_header_lines(raw_lines, cfg)
    if not joined:
        return ''

    name_end = _find_name_end(joined, words)
    name = joined[:name_end].strip().rstrip(',').strip()

    if len(name) > cfg.max_name_chars:
        paren_end = name.find(')')
        if 0 < paren_end < cfg.max_name_chars:
            rest = name[paren_end + 1:].strip()
            if rest and re.match(r'^(,\s*)?(ou\s|dit\s|dite\s|OU\s)', rest):
                second_paren = rest.find(')')
                if second_paren > 0:
                    name = name[:paren_end + 1 + rest.index(')') + 1]
                else:
                    name = name[:paren_end + 1]
            else:
                name = name[:paren_end + 1]

    return name


# ── Filename & OCR cleanup ──────────────────────────────────────────────────


def fix_ocr_spacing(name, cfg: ExtractionConfig):
    """Fix OCR artifacts that insert spaces within words."""
    def collapse_spaced_word(m):
        return m.group(0).replace(' ', '')

    name = re.sub(
        r'(?<![A-ZÀ-Þa-zà-ÿ])(?:[A-ZÀ-Þ] ){2,}[A-ZÀ-Þ](?![A-ZÀ-Þa-zà-ÿ])',
        collapse_spaced_word, name
    )

    for pattern, fixed in _BASE_SPACED_PARTICLES:
        name = re.sub(pattern, fixed, name)

    name = re.sub(r'\xad\s*', '', name)
    name = re.sub(r'\s+\)', ')', name)
    name = re.sub(r'\(\s+', '(', name)
    name = re.sub(r'\s+,', ',', name)

    for old, new in cfg.filename_ocr_fixes.items():
        name = name.replace(old, new)

    return name


def clean_filename_trailing(name):
    """Remove trailing incomplete phrases from filenames."""
    for pat in _BASE_TRAILING_PATTERNS:
        name = re.sub(pat, '', name, flags=re.IGNORECASE)

    name = re.sub(
        r',\s+(?:premier|première|deuxième|troisième|quatrième|cinquième|'
        r'sixième|septième|huitième|neuvième|dixième|onzième|douzième|'
        r'treizième|quatorzième|quinzième|seizième|dix-septième|'
        r'dix-huitième|dix-neuvième|vingtième|trentième|quarantième|'
        r'cinquantième|soixantième|Quarante-sixième|quarante-cinquième|'
        r'cinquante-neuvième)\b.*$',
        '', name, flags=re.IGNORECASE
    )
    return name.strip()


def extract_filename(bio_text, raw_lines, cfg: ExtractionConfig, words: dict):
    """Extract filesystem-safe filename from biography text."""
    name = (extract_name_from_lines(raw_lines, cfg, words) or
            bio_text.split(',')[0].strip()[:cfg.fallback_name_chars])
    name = name.rstrip('.')
    name = fix_ocr_spacing(name, cfg)
    name = clean_filename_trailing(name)
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    if len(name) > cfg.max_filename_chars:
        name = name[:cfg.max_filename_chars].rstrip()
    return (name or 'UNKNOWN') + '.txt'


# ── Entry classification ────────────────────────────────────────────────────


def is_cross_reference(bio_text, cfg: ExtractionConfig):
    """Check if entry is just a 'Voir X' redirect."""
    text = bio_text.strip()
    if len(text) < cfg.xref_max_chars and re.search(r'\bVoir\b', text):
        return True
    if len(text) < cfg.xref_garbled_max_chars and re.search(r'\bVoir[A-Z]', text):
        return True
    if len(text) < cfg.xref_garbled_max_chars and re.search(r'\bVO[A-Z]{3,}', text):
        return True
    return False


def is_false_positive(bio_text, cfg: ExtractionConfig, words: dict):
    """Detect fragments, footnotes, and non-biography entries."""
    text = bio_text.strip()
    first_word = text.split()[0] if text.split() else ''
    first_word = re.sub(r'^\*\s*', '', first_word)
    first_word_clean = re.sub(r'[.,;:\(\)]', '', first_word)

    if first_word_clean in words['blacklisted']:
        return True

    if text.startswith('D. O. M.') or text.startswith('ET DAME'):
        return True

    words_in_text = set(re.findall(r'[A-ZÀ-Þ]{3,}', text[:cfg.xref_garbled_max_chars]))
    if len(words_in_text) >= 2 and words_in_text <= words['latin_fragments']:
        return True

    if len(text) < cfg.short_entry_chars:
        alpha = re.findall(r'[a-zA-ZÀ-ÿ]+', text)
        if alpha:
            upper_words = [w for w in alpha if w[0].isupper() and len(w) > 1]
            lower_words = [w for w in alpha if w[0].islower() and
                          w not in _BASE_FRENCH_STOP_WORDS]
            if not lower_words and len(upper_words) >= 3:
                return True

    sample = text[:cfg.latin_sample_chars]
    upper_chars = sum(1 for c in sample if c.isupper())
    alpha_chars = sum(1 for c in sample if c.isalpha())
    if alpha_chars > cfg.min_alpha_for_latin and upper_chars / alpha_chars > cfg.latin_uppercase_ratio:
        if set(re.findall(r'[A-Z]{2,}', sample)) & words['latin_indicators']:
            return True

    if first_word_clean in _BASE_STANDALONE_PARTICLES:
        return True
    if first_word_clean == 'ou' or first_word == 'ou':
        return True
    if re.match(r'^[A-Z]\.[A-Z]\.', text):
        return True

    roman_match = re.match(r'^[IVXLCDM]{2,}(\s|$)', text)
    if roman_match:
        rest = text[roman_match.end():].strip()
        if not rest.startswith('(') and not rest.startswith(','):
            return True

    if (re.match(r'^[A-Z][\.\-][A-Z]?[\.\-]\s*[A-Z][a-z]+', text) and
            len(text) < cfg.author_attrib_max_size):
        return True
    if len(text) < cfg.min_entry_chars:
        return True

    first_50 = text[:50].strip()
    if first_50 and first_50[0].islower():
        return True

    first_word_text = re.sub(r'[.,;:\(\)\*]', '', text.split()[0]) if text.split() else ''
    if first_word_text in words['fragment_starters']:
        return True

    if re.match(r'^[IVX]+[,.\s]', text) and not re.match(r'^[IVX]+\s*\(', text):
        return True
    if re.match(r"^L'[a-z]", text):
        return True

    return False


def split_merged_entries(bio_text, raw_lines, cfg: ExtractionConfig):
    """Split a bio containing a cross-reference followed by another biography."""
    text = bio_text.strip()

    voir_match = re.search(
        r'\bVoir\s+.{5,150}?\)\.\s*'
        r'([A-ZÀ-Þ][A-ZÀ-Þa-zà-ÿ\s\-\']+(?:,|\())',
        text
    )
    if not voir_match:
        voir_match = re.search(
            r'\bVoir\s+[A-ZÀ-Þ][^\n]{3,80}?\.\s*'
            r'([A-ZÀ-Þ][A-ZÀ-Þa-zà-ÿ\s\-\']+(?:,|\())',
            text
        )

    if voir_match:
        split_pos = voir_match.start(1)
        part1, part2 = text[:split_pos].strip(), text[split_pos:].strip()
        if len(part1) > cfg.split_part1_min_chars and len(part2) > cfg.split_part2_min_chars:
            return [
                (part1, raw_lines[:1]),
                (part2, [part2[:200]]),
            ]

    return [(bio_text, raw_lines)]


# ── CLI ──────────────────────────────────────────────────────────────────────


def build_parser():
    """Build argument parser."""
    p = argparse.ArgumentParser(
        description="Extract biographies from scanned PDF biographical dictionaries.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  %(prog)s volume1_config.json\n"
               "  %(prog)s doc.pdf --start-page 41 --end-page 469\n"
               "  %(prog)s -c config.json -o output/\n",
    )
    p.add_argument(
        "source",
        help="PDF file path, or JSON config file (auto-detected by extension)",
    )
    p.add_argument("-c", "--config", help="JSON config file (overrides defaults)")
    p.add_argument("-o", "--output-dir", help="Output directory")
    p.add_argument("--log-file", help="Log file path")
    p.add_argument("--start-page", type=int, help="First page (0-indexed)")
    p.add_argument("--end-page", type=int, help="Last page (exclusive, 0-indexed)")
    p.add_argument("--report-title", help="Title for the extraction report")
    return p


def config_from_args(args) -> ExtractionConfig:
    """Build ExtractionConfig from parsed CLI arguments.

    Priority: CLI flags > JSON config file > dataclass defaults.
    """
    source = args.source
    config_path = args.config

    # Auto-detect: if source is a .json file, treat it as config
    if source.endswith('.json'):
        config_path = source
        cfg = ExtractionConfig.from_json(config_path)
    elif config_path:
        cfg = ExtractionConfig.from_json(config_path)
        cfg.pdf_path = source
    else:
        cfg = ExtractionConfig(pdf_path=source)

    # CLI overrides
    if args.output_dir is not None:
        cfg.output_dir = args.output_dir
    if args.log_file is not None:
        cfg.log_file = args.log_file
    if args.start_page is not None:
        cfg.start_page = args.start_page
    if args.end_page is not None:
        cfg.end_page = args.end_page
    if args.report_title is not None:
        cfg.report_title = args.report_title

    return cfg


# ── Main pipeline ────────────────────────────────────────────────────────────


def run(cfg: ExtractionConfig):
    """Run the full extraction pipeline with the given configuration."""
    pdf_path = Path(cfg.pdf_path)
    output_dir = Path(cfg.output_dir)
    log_file = Path(cfg.log_file)
    end_page_label = cfg.end_page if cfg.end_page is not None else "end"

    print(f"Opening {pdf_path}...")
    doc = fitz.open(str(pdf_path))
    end_page = cfg.resolve_end_page(len(doc))
    print(f"Total pages: {len(doc)}")
    print(f"Biography pages: {cfg.start_page + 1} to {end_page}")

    words = _build_word_sets(cfg)

    print("Extracting text with font metadata...")
    all_lines, bio_starts = collect_bio_starts(doc, cfg)
    print(f"Total text lines extracted: {len(all_lines)}")
    print(f"Biography starts detected: {len(bio_starts)}")

    print("Segmenting biographies...")
    biographies = []
    for i, (gidx, pidx, ld) in enumerate(bio_starts):
        end_gidx = bio_starts[i + 1][0] if i + 1 < len(bio_starts) else len(all_lines)
        raw_lines = extract_bio_text(all_lines, gidx, end_gidx)
        biographies.append((clean_biography_text(raw_lines, cfg), raw_lines))

    print(f"Biographies segmented: {len(biographies)}")

    # Merge stub entries with next entry
    merged_bios = []
    i = 0
    while i < len(biographies):
        bio_text, raw_lines = biographies[i]
        if len(bio_text.strip()) < cfg.stub_merge_max_chars and i + 1 < len(biographies):
            next_text, next_raw = biographies[i + 1]
            merged_bios.append((
                f"{bio_text.strip()} {next_text.strip()}",
                raw_lines + next_raw,
            ))
            i += 2
        else:
            merged_bios.append((bio_text, raw_lines))
            i += 1
    biographies = merged_bios
    print(f"After merging stubs: {len(biographies)}")

    # Split merged entries (cross-ref + bio in one segment)
    biographies = [
        entry
        for bio_text, raw_lines in biographies
        for entry in split_merged_entries(bio_text, raw_lines, cfg)
    ]

    # Write output
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    log_entries = []
    written = 0
    skipped_xrefs = 0
    skipped_false = 0
    filename_counts = {}

    for bio_text, raw_lines in biographies:
        if is_cross_reference(bio_text, cfg):
            skipped_xrefs += 1
            continue
        if is_false_positive(bio_text, cfg, words):
            skipped_false += 1
            continue

        filename = extract_filename(bio_text, raw_lines, cfg, words)

        if filename in filename_counts:
            filename_counts[filename] += 1
            stem, ext = Path(filename).stem, Path(filename).suffix
            filename = f"{stem} ({filename_counts[filename]}){ext}"
        else:
            filename_counts[filename] = 0

        (output_dir / filename).write_text(bio_text, encoding='utf-8')

        word_count = len(bio_text.split())
        char_count = len(bio_text)
        status = "OK" if char_count >= cfg.alert_min_chars else "ALERTE: très court"
        log_entries.append(f"{filename} | {word_count} mots | {char_count} car. | {status}")
        written += 1

    # Write report
    alerts = [e for e in log_entries if "ALERTE" in e]
    report_lines = [
        "=" * 80,
        cfg.report_title,
        "=" * 80,
        "",
        f"Biographies extraites : {written}",
        f"Renvois (Voir...) ignorés : {skipped_xrefs}",
        f"Faux positifs ignorés : {skipped_false}",
        f"Total entrées détectées : {len(biographies)}",
        "",
    ]
    if alerts:
        report_lines.append(f"--- ALERTES ({len(alerts)} entrées courtes < {cfg.alert_min_chars} car.) ---")
        report_lines.extend(f"  {a}" for a in alerts)
        report_lines.append("")
    report_lines.append("--- DÉTAIL COMPLET ---")
    report_lines.extend(f"  {entry}" for entry in log_entries)

    log_file.write_text('\n'.join(report_lines) + '\n', encoding='utf-8')

    print(f"\nTerminé!")
    print(f"  {written} biographies écrites dans {output_dir}/")
    print(f"  {skipped_xrefs} renvois ignorés")
    print(f"  {skipped_false} faux positifs ignorés")
    print(f"  Rapport: {log_file}")


def main():
    parser = build_parser()
    args = parser.parse_args()
    cfg = config_from_args(args)

    if not cfg.pdf_path:
        parser.error("No PDF path specified (provide it in the JSON config or as argument)")

    run(cfg)


if __name__ == "__main__":
    main()
