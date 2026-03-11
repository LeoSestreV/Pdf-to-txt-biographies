#!/usr/bin/env python3
"""
Extract biographies from BiographieNationale_Volume1.pdf

Uses PyMuPDF font metadata (bold detection) combined with text pattern matching
to reliably segment biographies. Page headers are filtered by Y-position.
"""

import fitz  # PyMuPDF
import re
import os
import shutil

PDF_PATH = "BiographieNationale_Volume1.pdf"
OUTPUT_DIR = "biographies_finales"
LOG_FILE = "rapport_final.log"

# Page where actual biographies begin (0-indexed page 41 = PDF page 42)
BIO_START_PAGE = 41
# Last page with biographies (0-indexed; page 470 has ERRATA)
BIO_END_PAGE = 469

# Y threshold: anything above this in the page is a running header
HEADER_Y_THRESHOLD = 60.0

UC = r'A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖÙÚÛÜÝÞ'


# ─────────────────────────────────────────────
# STEP 1: Extract structured data per page
# ─────────────────────────────────────────────

def extract_page_data(page, page_idx):
    """Extract text spans with metadata from a page.

    Returns a list of line dicts with: y, x, spans[], full_text, has_bold_start.
    Filters out the running header zone (y < HEADER_Y_THRESHOLD).
    """
    lines_data = []
    blocks = page.get_text('dict')['blocks']

    for b in blocks:
        if 'lines' not in b:
            continue
        for line in b['lines']:
            y_top = line['bbox'][1]
            x_left = line['bbox'][0]

            # SKIP running headers at top of page
            if y_top < HEADER_Y_THRESHOLD:
                continue

            spans = []
            for s in line['spans']:
                text = s['text']
                if not text.strip():
                    continue
                is_bold = bool(s['flags'] & (1 << 4))
                is_italic = bool(s['flags'] & (1 << 1))
                size = s['size']
                font = s['font']
                spans.append({
                    'text': text,
                    'bold': is_bold,
                    'italic': is_italic,
                    'size': size,
                    'font': font,
                })

            if not spans:
                continue

            full_text = ''.join(s['text'] for s in spans).strip()

            # Check if line starts with bold text
            has_bold_start = spans[0]['bold'] if spans else False

            lines_data.append({
                'y': y_top,
                'x': x_left,
                'spans': spans,
                'full_text': full_text,
                'has_bold_start': has_bold_start,
                'page': page_idx,
            })

    return lines_data


# ─────────────────────────────────────────────
# STEP 2: Identify biography start positions
# ─────────────────────────────────────────────

def is_biography_start(line_data, next_line_data=None):
    """Detect if a line is the start of a new biography entry.

    A biography starts with a name that is:
    - In bold font (Times-Bold), OR
    - In spaced small-caps (smaller font size, uppercase with spaces)
    - In regular font but clearly an uppercase name pattern

    Followed by (Prénom) or , descriptor (possibly on the next line)

    Must NOT be:
    - A footnote (bold at small size < 7.0 at bottom of page)
    - An author signature (mixed case like "P. F. X. de Ram.")
    - A bibliography reference
    """
    spans = line_data['spans']
    full = line_data['full_text']
    y = line_data['y']

    if not spans or not full:
        return False

    first = spans[0]

    # ── Method 1: Bold start ──
    if first['bold'] and first['size'] >= 7.0:
        # Collect bold name part
        bold_parts = []
        for s in spans:
            if s['bold']:
                bold_parts.append(s['text'])
            else:
                break
        bold_name = ''.join(bold_parts).strip()

        # Must be mostly uppercase
        name_clean = re.sub(r'[\s\-\'\.,;:\(\)\*\"I]', '', bold_name)
        if not name_clean:
            return False
        upper_count = sum(1 for c in name_clean if c.isupper())
        if len(name_clean) > 0 and upper_count / len(name_clean) >= 0.6:
            # Must have at least 3 uppercase chars
            if upper_count >= 3:
                # Must be followed by ( or , or "ou" (biography descriptor)
                # If bold_name ends with "(", consider that as having ( already
                rest = full[len(bold_name):].strip()
                if bold_name.rstrip().endswith('('):
                    rest = '(' + rest
                if (rest.startswith('(') or rest.startswith(',') or
                    re.match(r'^ou\s', rest, re.IGNORECASE) or
                    bold_name.rstrip().endswith(',') or bold_name.rstrip().endswith('(')):
                    # Filter out footnotes at bottom of page (y > 520 and size < 7.5)
                    if y > 520 and first['size'] < 7.0:
                        return False
                    # Filter author signatures: "P. F. X. de Ram." pattern
                    if re.match(r'^[A-Z]\.\s*[A-Z]', bold_name):
                        return False
                    return True

    # ── Method 2: Spaced small-caps (non-bold) ──
    # Names like "A B B É (Henri)" or "* A B E L (Saint)" rendered in smaller font with spaces
    first_text = first['text'].strip()
    # Remove leading * for foreign entries
    check_text = re.sub(r'^\*\s*', '', first_text)
    if re.match(rf'^[{UC}]( [{UC}]){{2,}}', check_text):
        # Spaced uppercase letters - this is a biography name
        rest = full[len(first_text):].strip()
        if (rest.startswith('(') or rest.startswith(',') or
            re.match(r'^ou\s', rest, re.IGNORECASE)):
            return True

    # ── Method 3: Regular uppercase name (non-bold, non-spaced) ──
    # Some entries like AGURTO are in regular font but clearly biography starts
    # They are uppercase names followed by (Prénom) or , descriptor
    # Handle * prefix for foreign entries

    # Find first meaningful span (skip * and spaces)
    first_real_idx = 0
    for idx, s in enumerate(spans):
        if s['text'].strip() in ('*', ''):
            first_real_idx = idx + 1
        else:
            break

    if first_real_idx < len(spans):
        real_first = spans[first_real_idx]
        ft = real_first['text'].strip()
        # Handle "* NAME" or "NAME (" in a single span
        ft_clean = re.sub(r'^\*\s*', '', ft)
        # Strip trailing ( for "NAME (" pattern
        ft_name = re.sub(r'\s*\(\s*$', '', ft_clean).strip()

        # Check if it's an uppercase name (at least 3 chars)
        if re.match(rf'^[{UC}][{UC}\-\' ]+$', ft_name) and len(ft_name) >= 3:
            # Get what follows the name
            name_end_pos = full.find(ft_name) + len(ft_name) if ft_name in full else -1
            rest = full[name_end_pos:].strip() if name_end_pos >= 0 else ''

            # Check next span for italic (first name) or ( or ,
            if first_real_idx + 1 < len(spans):
                next_span = spans[first_real_idx + 1]
                next_text = next_span['text'].strip()
                if (next_span['italic'] or
                    next_text.startswith('(') or next_text.startswith(',') or
                    rest.startswith('(') or rest.startswith(',')):
                    return True

            # Also check rest of full text for ( or , (with stripped space)
            if rest.startswith('(') or rest.startswith(','):
                return True

    # ── Method 4: Single-span line with NAME (Prénom) pattern ──
    # Sometimes the entire line is one span: "ADRIAENS (Henri), nommé aussi..."
    if len(spans) == 1 and not first['bold']:
        line_text = first['text'].strip()
        # Remove leading * for foreign entries
        check = re.sub(r'^\*\s*', '', line_text)
        m = re.match(
            rf'^([{UC}][{UC}\s\-\']+)\s*\(([^)]+)\)',
            check
        )
        if m:
            name_part = m.group(1).strip()
            prenom = m.group(2).strip()
            # Name must be at least 3 uppercase chars and the prénom should look like a name
            if len(name_part) >= 3 and len(prenom) >= 2:
                # Not a footnote reference like "(1)" or "(2)"
                if not re.match(r'^\d+$', prenom):
                    return True
        # Also match single-span NAME, descriptor
        m2 = re.match(
            rf'^([{UC}][{UC}\s\-\']+),\s+[a-zàáâãäåæçèéêëìíîïðñòóôõöùúûüýþ]',
            check
        )
        if m2:
            name_part = m2.group(1).strip()
            if len(name_part) >= 3:
                return True

    # ── Method 5: Name alone on a line, next line starts with ( or , ──
    # In two-column layout, the name can be on one line, description on next
    full_stripped = full.replace('*', '').strip()
    if (re.match(rf'^[{UC}][{UC}\s\-\'\.]+$', full_stripped) and
        len(full_stripped) >= 3 and len(full_stripped) <= 50):
        if next_line_data:
            next_full = next_line_data['full_text'].strip()
            if next_full.startswith('(') or next_full.startswith(','):
                return True
            # Next line has (Prénom) pattern
            if re.match(r'^\([^)]+\)', next_full):
                return True

    return False


def collect_bio_starts(doc):
    """Scan all biography pages and collect (page_idx, line_idx, line_data) for each start."""
    all_lines = []  # (global_idx, page_idx, line_data)
    global_idx = 0

    for pidx in range(BIO_START_PAGE, BIO_END_PAGE):
        page = doc[pidx]
        page_lines = extract_page_data(page, pidx)
        for ld in page_lines:
            all_lines.append((global_idx, pidx, ld))
            global_idx += 1

    # Find biography starts
    bio_starts = []
    for i, (gidx, pidx, ld) in enumerate(all_lines):
        next_ld = all_lines[i + 1][2] if i + 1 < len(all_lines) else None
        if is_biography_start(ld, next_ld):
            bio_starts.append((gidx, pidx, ld))

    return all_lines, bio_starts


# ─────────────────────────────────────────────
# STEP 3: Extract text between biography starts
# ─────────────────────────────────────────────

def extract_bio_text(all_lines, start_gidx, end_gidx):
    """Extract and clean the text between two global line indices."""
    text_parts = []
    for gidx, pidx, ld in all_lines:
        if gidx < start_gidx:
            continue
        if gidx >= end_gidx:
            break
        text_parts.append(ld['full_text'])

    raw = '\n'.join(text_parts)
    return raw


def clean_biography_text(text):
    """Apply all cleaning steps to a biography's text."""
    # Collapse spaced names
    text = collapse_spaced_names(text)

    # Dehyphenate
    text = re.sub(
        r'(\w)-\n(\w)',
        lambda m: m.group(1) + m.group(2) if m.group(2)[0].islower() else m.group(0),
        text
    )

    # Join broken lines (column wrapping)
    lines = text.split('\n')
    result = []
    i = 0
    NAME_PARTICLES = {'VAN', 'DE', 'DU', 'DES', 'LE', 'LA', 'LES', 'DEN', 'DER',
                      'VANDER', 'VANDEN', 'VANDE', 'VER', 'TER', 'TEN', 'TE',
                      'D', "D'", 'OU', 'ET'}

    while i < len(lines):
        line = lines[i]
        while i + 1 < len(lines) and lines[i + 1].strip():
            next_s = lines[i + 1].strip()
            first_word = next_s.split(')')[0].split(',')[0].split('(')[0].strip()

            # Join lowercase continuation
            if next_s[0].islower() or next_s[0] in '»«,;:)':
                if not re.match(rf'^[{UC}]{{2,}}', next_s):
                    line = line.rstrip() + ' ' + next_s
                    i += 1
                    continue

            # Join name particle continuation inside parens
            if first_word.rstrip(').,;:') in NAME_PARTICLES:
                if line.count('(') > line.count(')'):
                    line = line.rstrip() + ' ' + next_s
                    i += 1
                    continue

            # Join closing paren
            if next_s.startswith(')'):
                line = line.rstrip() + ' ' + next_s
                i += 1
                continue

            break
        result.append(line)
        i += 1

    text = '\n'.join(result)

    # Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = [l.strip() for l in text.split('\n')]
    text = '\n'.join(lines)

    # Remove trailing empty lines
    text = text.strip()

    return text


def collapse_spaced_names(text):
    """Collapse 'A B B É' -> 'ABBÉ'."""
    def _collapse(m):
        full = m.group(0)
        prefix = m.group(1) or ''
        spaced = full[len(prefix):]
        collapsed = re.sub(r'(?<=\w) (?=\w)', '', spaced)
        return prefix + collapsed

    text = re.sub(
        rf'^(\*\s*)?([{UC}] ){{2,}}[{UC}][{UC}]*',
        _collapse,
        text,
        flags=re.MULTILINE
    )
    return text


# ─────────────────────────────────────────────
# STEP 4: Extract filename and classify entries
# ─────────────────────────────────────────────

def extract_filename(bio_text):
    """Extract NOM (Prénom).txt from the first line."""
    first_line = bio_text.split('\n')[0].strip()

    # Pattern 1: NAME (Prénom)
    m = re.match(
        rf'^(\*?\s*[{UC}][{UC}\s\-\'\.]*\s*\([^)]*\))',
        first_line
    )
    if m:
        name = m.group(1).strip().lstrip('*').strip()
    else:
        # Pattern 2: NAME, description — extract name + optional (Prénom) after
        m = re.match(
            rf'^(\*?\s*[{UC}][{UC}\s\-\'\.]*)',
            first_line
        )
        if m:
            name = m.group(1).strip().lstrip('*').strip()
            rest = first_line[m.end():]
            m2 = re.match(r'\s*\(([^)]*)\)', rest)
            if m2:
                name = name + ' (' + m2.group(1) + ')'
        else:
            name = first_line[:60]

    name = name.strip().rstrip('.')
    # Filesystem-safe
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = re.sub(r'\s+', ' ', name)

    return name + '.txt'


def is_cross_reference(bio_text):
    """Check if entry is just a 'Voir X' redirect."""
    text = bio_text.strip()
    lines = [l for l in text.split('\n') if l.strip()]
    full = ' '.join(lines)
    if len(full) < 300 and re.search(r'Voir', full):
        return True
    return False


def is_false_positive(bio_text):
    """Detect fragments, footnotes, and non-biography entries."""
    text = bio_text.strip()
    first_line = text.split('\n')[0].strip()

    # Blacklisted "names" that are not biographies
    BLACKLIST = {
        'IDEM', 'VAN', 'DE', 'DU', 'DES', 'LE', 'LA', 'LES', 'DEN', 'DER',
        'NIES', 'DOMINUS', 'FEBRUARII', 'ITEM', 'ANNO', 'OBIIT',
    }
    first_word = re.sub(r'^\*\s*', '', first_line).split()[0] if first_line.split() else ''
    first_word_clean = re.sub(r'[.,;:\(\)]', '', first_word)
    if first_word_clean in BLACKLIST:
        return True

    # Roman numeral entries (XXX, XXXIV, etc.)
    roman_match = re.match(r'^[IVXLCDM]{2,}(\s|$)', first_line)
    if roman_match:
        # Only allow if it looks like a real name (has lowercase or parentheses nearby)
        rest = first_line[roman_match.end():].strip()
        if not rest.startswith('(') and not rest.startswith(','):
            return True

    # Short initials like "E.V. D.B." or "T'A" — not biography names
    name_part = first_line.split('(')[0].split(',')[0].strip()
    name_part = re.sub(r'^\*\s*', '', name_part)
    # Names with apostrophe fragments like "T'A" or very short non-name tokens
    if len(name_part) <= 4 and not re.match(rf'^[{UC}]{{3,}}$', name_part):
        return True
    if "'" in name_part and len(name_part.replace("'", '')) <= 3:
        return True
    # First word too short to be a biography name (e.g., "T'A kers, seker...")
    first_name_word = name_part.split()[0] if name_part.split() else ''
    first_word_letters = re.sub(r'[^A-Za-zÀ-ÿ]', '', first_name_word)
    if len(first_word_letters) < 3:
        return True

    # Initials pattern like "E.V. D.B."
    if re.match(r'^[A-Z]\.[A-Z]?\.\s*[A-Z]?\.\s*[A-Z]?\.', first_line):
        return True

    if len(text) < 80:
        if re.search(r'\bou\b|\bOU\b', text):
            return True
        lines = [l for l in text.split('\n') if l.strip()]
        full = ' '.join(lines)
        if re.match(rf'^[{UC}\s\-\']+\s*(\([^)]*\))?\s*[.,;:]?\s*\S{{0,30}}\s*$', full):
            return True

    # Truncated fragments (end mid-sentence, < 150 chars)
    if len(text) < 150:
        last_char = text.rstrip()[-1] if text.rstrip() else ''
        if last_char not in '.!?:)' and not re.search(r'[A-Z][a-z]+\.\s*$', text):
            if not re.search(r'\.\s*$', text):
                return True

    return False


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print(f"Opening {PDF_PATH}...")
    doc = fitz.open(PDF_PATH)
    print(f"Total pages: {len(doc)}")
    print(f"Biography pages: {BIO_START_PAGE + 1} to {BIO_END_PAGE}")

    # Step 1: Collect all lines with metadata
    print("Extracting text with font metadata...")
    all_lines, bio_starts = collect_bio_starts(doc)
    print(f"Total text lines extracted: {len(all_lines)}")
    print(f"Biography starts detected: {len(bio_starts)}")

    # Step 2: Extract text between consecutive starts
    print("Segmenting biographies...")
    biographies = []
    for i, (gidx, pidx, ld) in enumerate(bio_starts):
        end_gidx = bio_starts[i + 1][0] if i + 1 < len(bio_starts) else len(all_lines)
        raw_text = extract_bio_text(all_lines, gidx, end_gidx)
        clean_text = clean_biography_text(raw_text)
        biographies.append(clean_text)

    print(f"Biographies segmented: {len(biographies)}")

    # Step 3: Create output directory
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)

    # Step 4: Write files and report
    log_entries = []
    written = 0
    skipped_xrefs = 0
    skipped_false = 0
    filename_counts = {}

    for bio_text in biographies:
        if is_cross_reference(bio_text):
            skipped_xrefs += 1
            continue

        if is_false_positive(bio_text):
            skipped_false += 1
            continue

        filename = extract_filename(bio_text)

        if filename in filename_counts:
            filename_counts[filename] += 1
            base, ext = os.path.splitext(filename)
            filename = f"{base} ({filename_counts[filename]}){ext}"
        else:
            filename_counts[filename] = 0

        filepath = os.path.join(OUTPUT_DIR, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(bio_text)

        word_count = len(bio_text.split())
        char_count = len(bio_text)
        status = "OK" if char_count >= 150 else "ALERTE: très court"

        log_entries.append(f"{filename} | {word_count} mots | {char_count} car. | {status}")
        written += 1

    # Write report
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("RAPPORT D'EXTRACTION - BiographieNationale Volume 1\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Biographies extraites : {written}\n")
        f.write(f"Renvois (Voir...) ignorés : {skipped_xrefs}\n")
        f.write(f"Faux positifs ignorés : {skipped_false}\n")
        f.write(f"Total entrées détectées : {len(biographies)}\n\n")

        alerts = [e for e in log_entries if "ALERTE" in e]
        if alerts:
            f.write(f"--- ALERTES ({len(alerts)} entrées courtes < 150 car.) ---\n")
            for a in alerts:
                f.write(f"  {a}\n")
            f.write("\n")

        f.write("--- DÉTAIL COMPLET ---\n")
        for entry in log_entries:
            f.write(f"  {entry}\n")

    print(f"\nTerminé!")
    print(f"  {written} biographies écrites dans {OUTPUT_DIR}/")
    print(f"  {skipped_xrefs} renvois ignorés")
    print(f"  {skipped_false} faux positifs ignorés")
    print(f"  Rapport: {LOG_FILE}")

    # Show a few examples for verification
    print("\n--- EXEMPLES ---")
    samples = ["AGURTO", "ACHELEN", "ABBÉ", "BAUDOUIN DE BOUCLE"]
    for s in samples:
        for fn in os.listdir(OUTPUT_DIR):
            if s in fn:
                fp = os.path.join(OUTPUT_DIR, fn)
                with open(fp, 'r', encoding='utf-8') as f2:
                    content = f2.read()
                print(f"\n{fn}: {len(content)} car., {len(content.split())} mots")
                print(f"  Début: {content[:120]}...")
                break


if __name__ == "__main__":
    main()
