#!/usr/bin/env python3
"""
Extract biographies from BiographieNationale_Volume1.pdf

Uses PyMuPDF font metadata (bold detection) combined with text pattern matching
and indentation analysis to reliably segment biographies.
"""

import re
from pathlib import Path

import fitz  # PyMuPDF

# --- Configuration ---

PDF_PATH = Path("BiographieNationale_Volume1.pdf")
OUTPUT_DIR = Path("biographies_finales")
LOG_FILE = Path("rapport_final.log")

BIO_START_PAGE = 41
BIO_END_PAGE = 469
HEADER_Y_THRESHOLD = 60.0
FOOTER_Y_THRESHOLD = 590.0
COL_BOUNDARY = 290
Y_MERGE_TOLERANCE = 2.0

# X-position ranges for biography start indentation (alinéa)
# Left column: body text ~138-143, bio starts ~146-160
# Right column: body text ~302-307, bio starts ~308-325
LEFT_COL_INDENT = (146, 165)
RIGHT_COL_INDENT = (308, 330)

UC = r'A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖÙÚÛÜÝÞ'

# Descriptor words that signal end of name / start of biography body
DESCRIPTORS = frozenset({
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

NAME_PARTICLES = frozenset({
    'DE', 'DU', 'DES', 'LE', 'LA', 'LES', 'VAN', 'DEN', 'DER',
    'VANDER', 'VANDEN', 'OU', 'ET', 'D', 'VON', 'VER', 'TER',
})

NAME_LINKS = frozenset({'ou', 'dit', 'dite', 'surnommé', 'nommé', 'appelé', 'appelée'})

FRAGMENT_STARTERS = frozenset({
    'Il', 'Elle', 'Son', 'Sa', 'Ses', 'Les', 'Le', 'La', 'Un', 'Une',
    'Ce', 'Cette', 'Ces', 'On', 'Nous', 'Des', 'Du', 'En', 'Au',
    'Après', 'Avant', 'Dans', 'Sous', 'Sur', 'Par', 'Pour', 'Avec',
    'Parmi', 'Selon',
})

BLACKLISTED_STARTS = frozenset({
    'IDEM', 'DOMINUS', 'FEBRUARII', 'ITEM', 'ANNO', 'OBIIT',
    'HIC', 'LIBER', 'HUJUS', 'DIXIT',
})

LATIN_FRAGMENT_WORDS = frozenset({
    'INCLYTA', 'GESTA', 'CECINIT', 'TRIUMPHOS', 'NATURASI', 'MORES',
    'MYSTICA', 'VERBA', 'DEI', 'ARTES', 'DEPINGENS', 'MILITIAMQUE',
    'POLI', 'ELOQUII', 'PICTOR', 'HORUM', 'CENSOR', 'CYTIIARISTA',
    'PYERIDUM', 'PIDEI', 'ERAT', 'REQUIES', 'ANIMÆ', 'COELESTI',
    'DETUR', 'ARCE', 'EXOPTAT', 'ROGITES', 'LECTOR', 'AMICE', 'DEUM',
    'EGREGIE', 'SCRIBENS', 'PLANXIT', 'DOCUIT', 'CULTOR', 'CUBAT',
    'ALANUS', 'DOCTOR', 'QUEM', 'DECET', 'ALMUS', 'HONOR',
})

LATIN_INDICATORS = frozenset({
    'ET', 'QUI', 'QUOD', 'HIC', 'EST', 'FUIT', 'OBIIT',
    'ANNO', 'DOMINI', 'JACET', 'CUBAT', 'HUJUS', 'POST',
    'DIXIT', 'PONDUS', 'DOCUIT', 'CULTOR', 'FILIT',
})

STANDALONE_PARTICLES = frozenset({
    'VAN', 'DE', 'DU', 'DES', 'LE', 'LA', 'LES', 'DEN', 'DER',
})

SPACED_PARTICLES = [
    (r'\bD E S\b', 'DES'), (r'\bD E N\b', 'DEN'), (r'\bD E R\b', 'DER'),
    (r'\bV A N\b', 'VAN'), (r'\bV O N\b', 'VON'), (r'\bL E S\b', 'LES'),
    (r'\bD E\b', 'DE'), (r'\bD U\b', 'DU'),
    (r'\bL E\b', 'LE'), (r'\bL A\b', 'LA'),
]

TRAILING_PATTERNS = [
    r',?\s+dont\s+.*$',
    r',?\s+communément\s*$',
    r',?\s+mais\s*$',
    r',?\s+Belge\s+de\s+naissance\s*$',
    r",?\s+chroni\w*,?\s+qui\b.*$",
    r",?\s+'\s*$",
    r',?\s+aussi\b.*$',
]

OCR_FIXES = {
    'DETO -LÉDE': 'DE TOLÈDE',
    'DETO-LÉDE': 'DE TOLÈDE',
    'ARIVOIIL': 'ARNOUL',
}

# --- Page data extraction ---


def _extract_spans(line):
    """Extract non-empty spans with font metadata from a PDF line object."""
    return [
        {
            'text': s['text'],
            'bold': bool(s['flags'] & (1 << 4)),
            'italic': bool(s['flags'] & (1 << 1)),
            'size': s['size'],
            'font': s['font'],
        }
        for s in line['spans']
        if s['text'].strip()
    ]


def _merge_span_groups(groups):
    """Merge grouped span lists into final line data objects."""
    # Sort: left column first (by y), then right column (by y)
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
            'page': 0,  # set by caller
        })
    return lines_data


def extract_page_data(page, page_idx):
    """Extract text spans with metadata from a page.

    Merges line objects that share the same y-position (within 2px tolerance)
    into a single logical line, sorted by x-position.
    """
    raw_lines = []
    for b in page.get_text('dict')['blocks']:
        if 'lines' not in b:
            continue
        for line in b['lines']:
            y_top = line['bbox'][1]
            if y_top < HEADER_Y_THRESHOLD:
                continue
            spans = _extract_spans(line)
            if spans:
                raw_lines.append((y_top, line['bbox'][0], spans))

    raw_lines.sort(key=lambda t: (t[0], t[1]))

    # Group lines within 2px y tolerance and same column
    groups = []
    for y, x, spans in raw_lines:
        is_left = x < COL_BOUNDARY
        merged = False
        for g in groups:
            if abs(y - g[0]) <= Y_MERGE_TOLERANCE and is_left == g[3]:
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


# --- Detection helpers ---


def get_first_real_span(spans):
    """Get the first non-empty, non-asterisk span."""
    for s in spans:
        text = s['text'].strip()
        if text and text != '*':
            return s
    return spans[0] if spans else None


def is_indented_for_bio(x):
    """Check if x-position corresponds to biography start indentation."""
    lo, hi = LEFT_COL_INDENT if x < COL_BOUNDARY else RIGHT_COL_INDENT
    return lo <= x <= hi


def has_name_pattern(text):
    """Check if text starts with an uppercase name followed by ( or , or 'ou'."""
    text = re.sub(r'^\*\s*', '', text).strip()
    if re.match(rf'^[{UC}][{UC}\s\-\'\.]+\s*(\(|,|ou\s)', text):
        name_part = re.split(r'[,(]', text)[0].strip()
        name_clean = re.sub(r'[\s\-\'\.]+', '', name_part)
        if len(name_clean) >= 3 and not re.match(r'^[IVXLCDM]+$', name_clean):
            return True
    return False


# --- Biography start detection ---


def _check_bold_name(spans, first, full, y, next_line_data):
    """Method 1: Bold uppercase name detection.

    Returns True (is bio start), False (definitely not — block further methods),
    or None (not matched, try other methods).
    """
    if not (first['bold'] and first['size'] >= 7.0):
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
    if len(name_clean) == 0 or upper_count / len(name_clean) < 0.5 or upper_count < 2:
        return None

    rest = full[len(bold_name):].strip()
    if bold_name.rstrip().endswith('('):
        rest = '(' + rest

    if first['size'] < 7.0 and y > 350:
        return False

    if re.match(r'^[A-Z][a-z]*[\.\-]\s*[A-Z]', bold_name) and first['size'] < 7.5:
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


def _check_indented_italic(x, spans):
    """Method 4: Indented UPPERCASE + italic prénom pattern."""
    if not (is_indented_for_bio(x) and len(spans) >= 2):
        return False

    first_real = get_first_real_span(spans)
    if not first_real or first_real['bold']:
        return False

    ft = first_real['text'].strip().lstrip('*').strip()
    ft_name = re.sub(r'\s*\(\s*$', '', ft).strip()
    if not (re.match(rf'^[{UC}][{UC}\-\' ]+$', ft_name) and
            len(ft_name) >= 3 and
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


def _check_name_alone(full, next_line_data):
    """Method 5: Name alone on a line, next line starts with ( or ,."""
    full_stripped = full.replace('*', '').strip()
    if not (re.match(rf'^[{UC}][{UC}\s\-\'\.]+$', full_stripped) and
            3 <= len(full_stripped) <= 50 and
            not re.match(r'^[IVXLCDM\s]+$', full_stripped)):
        return False

    if not next_line_data:
        return False
    next_full = next_line_data['full_text'].strip()
    return (next_full.startswith('(') or next_full.startswith(',') or
            bool(re.match(r'^\([^)]+\)', next_full)))


def _check_after_attribution(full, prev_line_data):
    """Method 6: Name pattern preceded by author attribution."""
    if not (prev_line_data and has_name_pattern(full)):
        return False

    prev_full = prev_line_data['full_text'].strip()
    prev_spans = prev_line_data['spans']

    if not prev_full.endswith('.'):
        return False

    # Check last bold spans for attribution size
    last_bold_spans = [s for s in prev_spans if s['bold'] and s['text'].strip()]
    if last_bold_spans and max(s['size'] for s in last_bold_spans) < 7.5:
        return True

    # Initials-like ending: "Ad. Siret." or "F.-J. Fétis."
    if re.search(r'[A-Z][a-z]*[\.\-]\s*[A-Z][a-zà-ÿ]+\.\s*$', prev_full):
        return True

    # OCR-garbled attributions
    if re.search(r'[A-Z][a-z]*\.\s*[a-z]+[«»]+\.\s*$', prev_full):
        return True

    # "Voir X." cross-reference
    if re.search(r'\bVoir\b.*\.\s*$', prev_full):
        return True

    return False


def is_biography_start(line_data, next_line_data=None, prev_line_data=None):
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

    bold_result = _check_bold_name(spans, first, full, y, next_line_data)
    if bold_result is True:
        return True
    if bold_result is False:
        return False
    if _check_spaced_smallcaps(first, full, next_line_data):
        return True
    if is_indented_for_bio(x) and has_name_pattern(full):
        return True
    if _check_indented_italic(x, spans):
        return True
    if _check_name_alone(full, next_line_data):
        return True
    if _check_after_attribution(full, prev_line_data):
        return True

    return False


# --- Name continuation & merging ---


def is_name_continuation(prev_text, curr_text):
    """Check if curr_text continues the name started in prev_text."""
    prev = prev_text.strip()
    last_word = prev.rstrip('.,;:').split()[-1] if prev.split() else ''
    if last_word.upper() in NAME_PARTICLES:
        return True
    if prev.rstrip().endswith("D'") or prev.rstrip().endswith("d'"):
        return True
    if re.search(rf'[{UC}]{{2,}}-$', prev.rstrip()):
        return True

    last_two = ' '.join(prev.rstrip('.,;:').split()[-2:]) if len(prev.split()) >= 2 else ''
    return last_two.lower() in (
        'ou le', 'ou la', 'ou les', 'ou l', 'dit le', 'dit la',
        'dite la', 'dite le', 'nommé le', 'nommé la',
    )


# --- Collection & segmentation ---


def collect_bio_starts(doc):
    """Scan all biography pages and collect starts, merging split names."""
    all_lines = []
    for pidx in range(BIO_START_PAGE, BIO_END_PAGE):
        for ld in extract_page_data(doc[pidx], pidx):
            all_lines.append((len(all_lines), pidx, ld))

    bio_starts = []
    for i, (gidx, pidx, ld) in enumerate(all_lines):
        next_ld = all_lines[i + 1][2] if i + 1 < len(all_lines) else None
        prev_ld = all_lines[i - 1][2] if i > 0 else None
        if is_biography_start(ld, next_ld, prev_ld):
            bio_starts.append((gidx, pidx, ld))

    # Post-process 1: Remove false starts caused by hyphenation
    bio_starts = [
        (gidx, pidx, ld) for gidx, pidx, ld in bio_starts
        if gidx == 0 or not re.search(rf'[{UC}]{{2,}}-$',
                                       all_lines[gidx - 1][2]['full_text'].rstrip())
    ]

    # Post-process 2: Merge when gap is 1-2 lines and previous line ends with name particle
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

            if gap <= 2:
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


# --- Text cleaning ---


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


def clean_biography_text(raw_lines):
    """Clean biography text into continuous flowing text."""
    text = collapse_spaced_names('\n'.join(raw_lines))

    # Dehyphenate words split across lines
    text = re.sub(
        r'(\w)-\n(\w)',
        lambda m: m.group(1) + m.group(2) if m.group(2)[0].islower() else m.group(0),
        text
    )

    # Join all lines, strip, collapse whitespace
    parts = []
    for line in text.split('\n'):
        line = line.strip()
        if line:
            if parts:
                parts.append(' ')
            parts.append(line)

    text = re.sub(r'[ \t]+', ' ', ''.join(parts)).strip()
    text = text.replace('ARIVOIIL', 'ARNOUL')
    return text


# --- Name extraction ---


def _join_header_lines(raw_lines):
    """Join first few lines handling hyphenation for name extraction."""
    header_lines = [
        collapse_spaced_names(line.strip())
        for line in raw_lines[:5]
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


def _find_name_end(joined):
    """Find the end position of the name in the joined header text."""
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
                    if word in DESCRIPTORS:
                        pos = i
                        while pos > 0 and joined[pos - 1] in ' ,':
                            pos -= 1
                        return pos
                    if joined[i - 1] == ')' or (i > 1 and ')' in joined[max(0, i - 5):i]):
                        if word not in NAME_LINKS:
                            pos = i
                            while pos > 0 and joined[pos - 1] in ' ,':
                                pos -= 1
                            return pos
        i += 1

    return len(joined)


def extract_name_from_lines(raw_lines):
    """Extract the biography name from raw lines."""
    joined = _join_header_lines(raw_lines)
    if not joined:
        return ''

    name_end = _find_name_end(joined)
    name = joined[:name_end].strip().rstrip(',').strip()

    # Truncate overly long names at a reasonable point
    if len(name) > 80:
        paren_end = name.find(')')
        if 0 < paren_end < 80:
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


# --- Filename & OCR cleanup ---


def fix_ocr_spacing(name):
    """Fix OCR artifacts that insert spaces within words."""
    def collapse_spaced_word(m):
        return m.group(0).replace(' ', '')

    # Collapse 3+ spaced uppercase letters
    name = re.sub(
        r'(?<![A-ZÀ-Þa-zà-ÿ])(?:[A-ZÀ-Þ] ){2,}[A-ZÀ-Þ](?![A-ZÀ-Þa-zà-ÿ])',
        collapse_spaced_word, name
    )

    for pattern, fixed in SPACED_PARTICLES:
        name = re.sub(pattern, fixed, name)

    name = re.sub(r'\xad\s*', '', name)  # soft hyphen
    name = re.sub(r'\s+\)', ')', name)
    name = re.sub(r'\(\s+', '(', name)
    name = re.sub(r'\s+,', ',', name)

    for old, new in OCR_FIXES.items():
        name = name.replace(old, new)

    return name


def clean_filename_trailing(name):
    """Remove trailing incomplete phrases from filenames."""
    for pat in TRAILING_PATTERNS:
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


def extract_filename(bio_text, raw_lines):
    """Extract filesystem-safe filename from biography text."""
    name = extract_name_from_lines(raw_lines) or bio_text.split(',')[0].strip()[:60]
    name = name.rstrip('.')
    name = fix_ocr_spacing(name)
    name = clean_filename_trailing(name)
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    if len(name) > 90:
        name = name[:90].rstrip()
    return (name or 'UNKNOWN') + '.txt'


# --- Entry classification ---


def is_cross_reference(bio_text):
    """Check if entry is just a 'Voir X' redirect."""
    text = bio_text.strip()
    if len(text) < 300 and re.search(r'\bVoir\b', text):
        return True
    if len(text) < 200 and re.search(r'\bVoir[A-Z]', text):
        return True
    if len(text) < 200 and re.search(r'\bVO[A-Z]{3,}', text):
        return True
    return False


def is_false_positive(bio_text):
    """Detect fragments, footnotes, and non-biography entries."""
    text = bio_text.strip()
    first_word = text.split()[0] if text.split() else ''
    first_word = re.sub(r'^\*\s*', '', first_word)
    first_word_clean = re.sub(r'[.,;:\(\)]', '', first_word)

    if first_word_clean in BLACKLISTED_STARTS:
        return True

    if text.startswith('D. O. M.') or text.startswith('ET DAME'):
        return True

    # Latin verse fragments
    words_in_text = set(re.findall(r'[A-ZÀ-Þ]{3,}', text[:200]))
    if len(words_in_text) >= 2 and words_in_text <= LATIN_FRAGMENT_WORDS:
        return True

    # Short all-uppercase entries with no descriptive content
    if len(text) < 100:
        alpha = re.findall(r'[a-zA-ZÀ-ÿ]+', text)
        if alpha:
            upper_words = [w for w in alpha if w[0].isupper() and len(w) > 1]
            lower_words = [w for w in alpha if w[0].islower() and w not in
                          {'ou', 'et', 'de', 'du', 'des', 'le', 'la', 'les', 'en', 'a', 'y'}]
            if not lower_words and len(upper_words) >= 3:
                return True

    # Latin inscriptions: >80% uppercase with Latin indicators
    sample = text[:300]
    upper_chars = sum(1 for c in sample if c.isupper())
    alpha_chars = sum(1 for c in sample if c.isalpha())
    if alpha_chars > 30 and upper_chars / alpha_chars > 0.8:
        if set(re.findall(r'[A-Z]{2,}', sample)) & LATIN_INDICATORS:
            return True

    if first_word_clean in STANDALONE_PARTICLES:
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

    if re.match(r'^[A-Z][\.\-][A-Z]?[\.\-]\s*[A-Z][a-z]+', text) and len(text) < 100:
        return True
    if len(text) < 30:
        return True

    first_50 = text[:50].strip()
    if first_50 and first_50[0].islower():
        return True

    first_word_text = re.sub(r'[.,;:\(\)\*]', '', text.split()[0]) if text.split() else ''
    if first_word_text in FRAGMENT_STARTERS:
        return True

    if re.match(r'^[IVX]+[,.\s]', text) and not re.match(r'^[IVX]+\s*\(', text):
        return True
    if re.match(r"^L'[a-z]", text):
        return True

    return False


def split_merged_entries(bio_text, raw_lines):
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
        if len(part1) > 10 and len(part2) > 50:
            return [
                (part1, raw_lines[:1]),
                (part2, [part2[:200]]),
            ]

    return [(bio_text, raw_lines)]


# --- Main pipeline ---


def main():
    print(f"Opening {PDF_PATH}...")
    doc = fitz.open(str(PDF_PATH))
    print(f"Total pages: {len(doc)}")
    print(f"Biography pages: {BIO_START_PAGE + 1} to {BIO_END_PAGE}")

    print("Extracting text with font metadata...")
    all_lines, bio_starts = collect_bio_starts(doc)
    print(f"Total text lines extracted: {len(all_lines)}")
    print(f"Biography starts detected: {len(bio_starts)}")

    print("Segmenting biographies...")
    biographies = []
    for i, (gidx, pidx, ld) in enumerate(bio_starts):
        end_gidx = bio_starts[i + 1][0] if i + 1 < len(bio_starts) else len(all_lines)
        raw_lines = extract_bio_text(all_lines, gidx, end_gidx)
        biographies.append((clean_biography_text(raw_lines), raw_lines))

    print(f"Biographies segmented: {len(biographies)}")

    # Merge stub entries (< 60 chars) with next entry
    merged_bios = []
    i = 0
    while i < len(biographies):
        bio_text, raw_lines = biographies[i]
        if len(bio_text.strip()) < 60 and i + 1 < len(biographies):
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
        for entry in split_merged_entries(bio_text, raw_lines)
    ]

    # Write output
    if OUTPUT_DIR.exists():
        import shutil
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir()

    log_entries = []
    written = 0
    skipped_xrefs = 0
    skipped_false = 0
    filename_counts = {}

    for bio_text, raw_lines in biographies:
        if is_cross_reference(bio_text):
            skipped_xrefs += 1
            continue
        if is_false_positive(bio_text):
            skipped_false += 1
            continue

        filename = extract_filename(bio_text, raw_lines)

        if filename in filename_counts:
            filename_counts[filename] += 1
            stem, ext = Path(filename).stem, Path(filename).suffix
            filename = f"{stem} ({filename_counts[filename]}){ext}"
        else:
            filename_counts[filename] = 0

        (OUTPUT_DIR / filename).write_text(bio_text, encoding='utf-8')

        word_count = len(bio_text.split())
        char_count = len(bio_text)
        status = "OK" if char_count >= 150 else "ALERTE: très court"
        log_entries.append(f"{filename} | {word_count} mots | {char_count} car. | {status}")
        written += 1

    # Write report
    alerts = [e for e in log_entries if "ALERTE" in e]
    report_lines = [
        "=" * 80,
        "RAPPORT D'EXTRACTION - BiographieNationale Volume 1",
        "=" * 80,
        "",
        f"Biographies extraites : {written}",
        f"Renvois (Voir...) ignorés : {skipped_xrefs}",
        f"Faux positifs ignorés : {skipped_false}",
        f"Total entrées détectées : {len(biographies)}",
        "",
    ]
    if alerts:
        report_lines.append(f"--- ALERTES ({len(alerts)} entrées courtes < 150 car.) ---")
        report_lines.extend(f"  {a}" for a in alerts)
        report_lines.append("")
    report_lines.append("--- DÉTAIL COMPLET ---")
    report_lines.extend(f"  {entry}" for entry in log_entries)

    LOG_FILE.write_text('\n'.join(report_lines) + '\n', encoding='utf-8')

    print(f"\nTerminé!")
    print(f"  {written} biographies écrites dans {OUTPUT_DIR}/")
    print(f"  {skipped_xrefs} renvois ignorés")
    print(f"  {skipped_false} faux positifs ignorés")
    print(f"  Rapport: {LOG_FILE}")


if __name__ == "__main__":
    main()
