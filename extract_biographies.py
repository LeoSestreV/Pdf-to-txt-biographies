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

BIO_START_PAGE = 41
BIO_END_PAGE = 469
HEADER_Y_THRESHOLD = 60.0

UC = r'A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖÙÚÛÜÝÞ'

NAME_PARTICLES = {'VAN', 'DE', 'DU', 'DES', 'LE', 'LA', 'LES', 'DEN', 'DER',
                  'VANDER', 'VANDEN', 'VANDE', 'VER', 'TER', 'TEN', 'TE',
                  'D', "D'", 'OU', 'ET', 'ou', 'le', 'la', 'de', 'du', 'des'}


def extract_page_data(page, page_idx):
    """Extract text spans with metadata from a page."""
    lines_data = []
    blocks = page.get_text('dict')['blocks']

    for b in blocks:
        if 'lines' not in b:
            continue
        for line in b['lines']:
            y_top = line['bbox'][1]
            x_left = line['bbox'][0]

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


def is_biography_start(line_data, next_line_data=None):
    """Detect if a line is the start of a new biography entry."""
    spans = line_data['spans']
    full = line_data['full_text']
    y = line_data['y']

    if not spans or not full:
        return False

    first = spans[0]

    # Method 1: Bold start
    if first['bold'] and first['size'] >= 7.0:
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
        if len(name_clean) > 0 and upper_count / len(name_clean) >= 0.6:
            if upper_count >= 3:
                rest = full[len(bold_name):].strip()
                if bold_name.rstrip().endswith('('):
                    rest = '(' + rest
                # Also check if bold_name itself contains a comma (name + descriptor in one span)
                has_comma_in_name = ',' in bold_name
                if (rest.startswith('(') or rest.startswith(',') or
                    re.match(r'^ou\s', rest, re.IGNORECASE) or
                    bold_name.rstrip().endswith(',') or bold_name.rstrip().endswith('(') or
                    has_comma_in_name):
                    if y > 520 and first['size'] < 7.0:
                        return False
                    if re.match(r'^[A-Z]\.\s*[A-Z]', bold_name):
                        return False
                    return True

    # Method 2: Spaced small-caps
    first_text = first['text'].strip()
    check_text = re.sub(r'^\*\s*', '', first_text)
    if re.match(rf'^[{UC}]( [{UC}]){{2,}}', check_text):
        rest = full[len(first_text):].strip()
        if (rest.startswith('(') or rest.startswith(',') or
            re.match(r'^ou\s', rest, re.IGNORECASE)):
            return True

    # Method 3: Regular uppercase name
    first_real_idx = 0
    for idx, s in enumerate(spans):
        if s['text'].strip() in ('*', ''):
            first_real_idx = idx + 1
        else:
            break

    if first_real_idx < len(spans):
        real_first = spans[first_real_idx]
        ft = real_first['text'].strip()
        ft_clean = re.sub(r'^\*\s*', '', ft)
        ft_name = re.sub(r'\s*\(\s*$', '', ft_clean).strip()

        if re.match(rf'^[{UC}][{UC}\-\' ]+$', ft_name) and len(ft_name) >= 3:
            name_end_pos = full.find(ft_name) + len(ft_name) if ft_name in full else -1
            rest = full[name_end_pos:].strip() if name_end_pos >= 0 else ''

            if first_real_idx + 1 < len(spans):
                next_span = spans[first_real_idx + 1]
                next_text = next_span['text'].strip()
                if (next_span['italic'] or
                    next_text.startswith('(') or next_text.startswith(',') or
                    rest.startswith('(') or rest.startswith(',')):
                    return True

            if rest.startswith('(') or rest.startswith(','):
                return True

    # Method 4: Single-span NAME (Prénom) pattern
    if len(spans) == 1 and not first['bold']:
        line_text = first['text'].strip()
        check = re.sub(r'^\*\s*', '', line_text)
        m = re.match(rf'^([{UC}][{UC}\s\-\']+)\s*\(([^)]+)\)', check)
        if m:
            name_part = m.group(1).strip()
            prenom = m.group(2).strip()
            if len(name_part) >= 3 and len(prenom) >= 2:
                if not re.match(r'^\d+$', prenom):
                    return True
        m2 = re.match(
            rf'^([{UC}][{UC}\s\-\']+),\s+[a-zàáâãäåæçèéêëìíîïðñòóôõöùúûüýþ]',
            check
        )
        if m2:
            name_part = m2.group(1).strip()
            if len(name_part) >= 3:
                return True

    # Method 5: Name alone on a line, next line starts with ( or ,
    full_stripped = full.replace('*', '').strip()
    if (re.match(rf'^[{UC}][{UC}\s\-\'\.]+$', full_stripped) and
        len(full_stripped) >= 3 and len(full_stripped) <= 50):
        if next_line_data:
            next_full = next_line_data['full_text'].strip()
            if next_full.startswith('(') or next_full.startswith(','):
                return True
            if re.match(r'^\([^)]+\)', next_full):
                return True

    return False


def is_name_continuation(prev_text, curr_text):
    """Check if curr_text is a continuation of the name started in prev_text."""
    prev = prev_text.strip()

    last_word = prev.rstrip('.,;:').split()[-1] if prev.split() else ''
    if last_word.upper() in {'DE', 'DU', 'DES', 'LE', 'LA', 'LES', 'VAN', 'DEN', 'DER',
                              'VANDER', 'VANDEN', 'OU', 'ET', 'D', 'VON', 'VER', 'TER'}:
        return True

    if prev.rstrip().endswith("D'") or prev.rstrip().endswith("d'"):
        return True

    # Hyphenation of uppercase word: "FLA-"
    if re.search(rf'[{UC}]{{2,}}-$', prev.rstrip()):
        return True

    last_two = ' '.join(prev.rstrip('.,;:').split()[-2:]) if len(prev.split()) >= 2 else ''
    if last_two.lower() in ('ou le', 'ou la', 'ou les', 'ou l', 'dit le', 'dit la',
                             'dite la', 'dite le', 'nommé le', 'nommé la'):
        return True

    return False


def collect_bio_starts(doc):
    """Scan all biography pages and collect starts, merging split names."""
    all_lines = []
    global_idx = 0

    for pidx in range(BIO_START_PAGE, BIO_END_PAGE):
        page = doc[pidx]
        page_lines = extract_page_data(page, pidx)
        for ld in page_lines:
            all_lines.append((global_idx, pidx, ld))
            global_idx += 1

    bio_starts = []
    for i, (gidx, pidx, ld) in enumerate(all_lines):
        next_ld = all_lines[i + 1][2] if i + 1 < len(all_lines) else None
        if is_biography_start(ld, next_ld):
            bio_starts.append((gidx, pidx, ld))

    # Post-process 1: Remove false starts caused by hyphenation
    # If the line IMMEDIATELY before a bio start ends with "WORD-" (uppercase hyphenation),
    # then this "start" is actually a continuation of that word, not a new bio
    filtered = []
    for gidx, pidx, ld in bio_starts:
        if gidx > 0:
            prev_line = all_lines[gidx - 1][2]['full_text'].rstrip()
            if re.search(rf'[{UC}]{{2,}}-$', prev_line):
                # This is a hyphenation continuation, skip it
                continue
        filtered.append((gidx, pidx, ld))
    bio_starts = filtered

    # Post-process 2: Merge split names between consecutive bio starts
    # Only merge when the FIRST bio start's own text (or its immediate continuation)
    # ends with a name particle, AND the intermediate text is short (name-like)
    merged = []
    skip_next = False
    for i in range(len(bio_starts)):
        if skip_next:
            skip_next = False
            continue

        gidx, pidx, ld = bio_starts[i]

        if i + 1 < len(bio_starts):
            next_gidx = bio_starts[i + 1][0]
            next_ld = bio_starts[i + 1][2]
            gap = next_gidx - gidx

            if gap <= 3:
                # Collect all text between the two starts
                between_text = []
                for j in range(gidx, next_gidx):
                    if j < len(all_lines):
                        between_text.append(all_lines[j][2]['full_text'])
                combined = ' '.join(between_text)

                # Don't merge if the first entry contains "Voir" (cross-reference)
                if 'Voir' in combined:
                    merged.append((gidx, pidx, ld))
                    continue

                # Check if the line just before the next start ends with a particle
                prev_text = all_lines[next_gidx - 1][2]['full_text'] if next_gidx - 1 >= 0 else ''
                if is_name_continuation(prev_text, next_ld['full_text']):
                    skip_next = True

        merged.append((gidx, pidx, ld))

    bio_starts = merged

    return all_lines, bio_starts


def extract_bio_text(all_lines, start_gidx, end_gidx):
    """Extract the raw text lines between two global line indices."""
    text_parts = []
    for gidx, pidx, ld in all_lines:
        if gidx < start_gidx:
            continue
        if gidx >= end_gidx:
            break
        text_parts.append(ld['full_text'])
    return text_parts


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


def extract_name_from_lines(raw_lines):
    """Extract the full biography name from the raw (pre-join) lines.

    Scans text to find where the name ends and the description begins.
    Handles: NAME (Prénom), ou ALTERNATIVE, dit LE SURNOM, etc.
    """
    # Join first few raw lines for name extraction
    header_lines = []
    for line in raw_lines[:10]:
        line = line.strip()
        if not line:
            continue
        line = collapse_spaced_names(line)
        header_lines.append(line)

    # Join lines, handling hyphenation
    joined = ''
    for line in header_lines:
        if joined and joined.endswith('-'):
            if line and line[0].islower():
                # Lowercase continuation: dehyphenate
                joined = joined[:-1] + line
            elif line and line[0].isupper() and re.search(rf'[{UC}]{{2,}}-$', joined):
                # Uppercase continuation of uppercase word: FLA- + MAND -> FLAMAND
                joined = joined[:-1] + line
            else:
                joined = joined + line
        elif joined:
            joined = joined + ' ' + line
        else:
            joined = line

    # Descriptor words that signal end of name
    DESCRIPTORS = {
        'abbé', 'abbesse', 'administrateur', 'agronome', 'amiral', 'ancien',
        'annaliste', 'antiquaire', 'apôtre', 'architecte', 'archéologue',
        'artisan', 'artiste', 'artistes', 'astronome', 'auteur',
        'baron', 'bienfaiteur', 'bienheureux', 'biographe', 'bourgmestre',
        'bourgeois', 'bénédictin', 'belge',
        'calligraphe', 'capitaine', 'cardinal', 'cartographe', 'célèbre',
        'chanoine', 'chantre', 'chapelain', 'chef', 'chevalier', 'chirurgien',
        'chroniqueur', 'chronologiste', 'coadjuteur', 'colonel', 'combattant',
        'commerçant', 'commandant', 'commandeur', 'commentateur', 'compilateur',
        'compositeur', 'comte', 'comtesse', 'confesseur', 'conseiller',
        'constructeur', 'consul', 'controversiste', 'coseigneur', 'curé',
        'dame', 'dessinateur', 'diplomate', 'directeur', 'docteur', 'dominicain',
        'doyen', 'duc', 'duchesse', 'décédé', 'défenseur',
        'ecclésiastique', 'empereur', 'enseigna', 'ermite', 'escrimeur',
        'est', 'ethnologue',
        'évêque', 'écolâtre', 'écrivain', 'érudit', 'époux', 'épouse', 'était',
        'facteur', 'feldmaréchal', 'femme', 'fils', 'financier', 'fille',
        'fondateur', 'fondatrice', 'forme', 'frère', 'fut',
        'gardien', 'gentilhomme', 'gouverneur', 'grammairien', 'graveur',
        'guerrier', 'général', 'géographe', 'géologue',
        'hagiographe', 'helléniste', 'héraldiste', 'historien', 'homme',
        'humaniste', 'hébraïsant',
        'imprimeur', 'industriel', 'ingénieur', 'instituteur',
        'jésuite', 'jurisconsulte', 'juriste',
        'lazariste', 'lecteur', 'libraire', 'licencié', 'littérateur',
        'lieutenant',
        'magistrat', 'major', 'marchand', 'marquis', 'maréchal',
        'mathématicien', 'maître', 'membre', 'militaire', 'minéralogiste',
        'ministre', 'missionnaire', 'moine', 'moraliste', 'musicien', 'médecin',
        'ménestrel',
        'navigateur', 'naquit', 'neveu', 'noble', 'nommé', 'notaire', 'né',
        'née',
        'officier', 'organiste', 'orientaliste', 'ornithologue',
        'patriote', 'patron', 'peintre', 'personnage', 'philologue',
        'philosophe', 'physicien', 'plus', 'poète', 'poëte', 'prédicateur',
        'président', 'prêtre', 'prince', 'princesse', 'prieur', 'procureur',
        'professeur', 'protonotaire', 'prévôt', 'publiciste',
        'recteur', 'religieux', 'religieuse', 'roi', 'reine', 'récollet',
        'savant', 'sculpteur', 'secrétaire', 'seigneur', 'sénateur', 'sire',
        'soldat', 'statuaire', 'successivement', 'surnommé',
        'théologien', 'théoricien', 'topographe', 'trouvère',
        'vicaire', 'vivait', 'voyageur',
    }

    # Scan to find where the name ends and description begins
    # Name ends at:
    # 1. A descriptor word outside parens
    # 2. A period followed by space outside parens (sentence end)
    paren_depth = 0
    name_end = len(joined)

    i = 0
    while i < len(joined):
        ch = joined[i]
        if ch == '(':
            paren_depth += 1
            i += 1
            continue
        elif ch == ')':
            paren_depth = max(0, paren_depth - 1)
            i += 1
            continue

        if paren_depth == 0:
            # Check for period followed by space (sentence end = name end)
            if ch == '.' and i + 1 < len(joined) and joined[i + 1] == ' ':
                # Only stop if this is after a word (not an abbreviation like "D'.")
                # and before a real sentence (not "St." or "etc.")
                before = joined[:i].rstrip()
                if before and not re.search(r'\b[A-Z]$', before):
                    # Not a single-letter abbreviation
                    name_end = i + 1  # include the period
                    break

            # Check for descriptor word at word boundary
            if i > 0:
                prev_ch = joined[i - 1]
                if prev_ch in ' ,)':
                    word_match = re.match(r'[a-zàáâãäåæçèéêëìíîïðñòóôõöùúûüýþé]+', joined[i:])
                    if word_match:
                        word = word_match.group(0)
                        if word in DESCRIPTORS:
                            name_end = i
                            while name_end > 0 and joined[name_end - 1] in ' ,':
                                name_end -= 1
                            break

        i += 1

    name = joined[:name_end].strip().rstrip(',').strip()

    # Remove leading *
    name = name.lstrip('*').strip()

    return name


def clean_biography_text(raw_lines):
    """Clean biography text into continuous flowing text."""
    text = '\n'.join(raw_lines)

    # Collapse spaced names
    text = collapse_spaced_names(text)

    # Dehyphenate words split across lines
    text = re.sub(
        r'(\w)-\n(\w)',
        lambda m: m.group(1) + m.group(2) if m.group(2)[0].islower() else m.group(0),
        text
    )

    # Join ALL lines into one continuous text
    lines = text.split('\n')
    parts = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if parts:
            parts.append(' ')
        parts.append(line)

    text = ''.join(parts)

    # Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = text.strip()

    return text


def extract_filename(bio_text, raw_lines):
    """Extract filename from biography text using raw lines for name extraction."""
    name = extract_name_from_lines(raw_lines)

    if not name:
        name = bio_text.split(',')[0].strip()[:60]

    name = name.rstrip('.')
    # Filesystem-safe
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = re.sub(r'\s+', ' ', name)
    # Truncate very long names
    if len(name) > 120:
        name = name[:120].rstrip()

    if not name:
        name = 'UNKNOWN'

    return name + '.txt'


def is_cross_reference(bio_text):
    """Check if entry is just a 'Voir X' redirect."""
    text = bio_text.strip()
    if len(text) < 300 and re.search(r'Voir', text):
        return True
    return False


def is_false_positive(bio_text):
    """Detect fragments, footnotes, and non-biography entries."""
    text = bio_text.strip()
    first_words = text.split()[:3]
    first_word = first_words[0] if first_words else ''

    first_word = re.sub(r'^\*\s*', '', first_word)
    first_word_clean = re.sub(r'[.,;:\(\)]', '', first_word)

    BLACKLIST = {
        'IDEM', 'VAN', 'DE', 'DU', 'DES', 'LE', 'LA', 'LES', 'DEN', 'DER',
        'NIES', 'DOMINUS', 'FEBRUARII', 'ITEM', 'ANNO', 'OBIIT',
    }
    if first_word_clean in BLACKLIST:
        return True

    roman_match = re.match(r'^[IVXLCDM]{2,}(\s|$)', text)
    if roman_match:
        rest = text[roman_match.end():].strip()
        if not rest.startswith('(') and not rest.startswith(','):
            return True

    name_part = text.split('(')[0].split(',')[0].strip()
    name_part = re.sub(r'^\*\s*', '', name_part)
    if len(name_part) <= 4 and not re.match(rf'^[{UC}]{{3,}}$', name_part):
        return True
    if "'" in name_part and len(name_part.replace("'", '')) <= 3:
        return True
    first_name_word = name_part.split()[0] if name_part.split() else ''
    first_word_letters = re.sub(r'[^A-Za-zÀ-ÿ]', '', first_name_word)
    if len(first_word_letters) < 3:
        return True

    if re.match(r'^[A-Z]\.[A-Z]?\.\s*[A-Z]?\.\s*[A-Z]?\.', text):
        return True

    if len(text) < 80:
        if re.search(r'\bou\b|\bOU\b', text):
            return True
        if re.match(rf'^[{UC}\s\-\']+\s*(\([^)]*\))?\s*[.,;:]?\s*\S{{0,30}}\s*$', text):
            return True

    if len(text) < 150:
        last_char = text.rstrip()[-1] if text.rstrip() else ''
        if last_char not in '.!?:)' and not re.search(r'[A-Z][a-z]+\.\s*$', text):
            if not re.search(r'\.\s*$', text):
                return True

    return False


def main():
    print(f"Opening {PDF_PATH}...")
    doc = fitz.open(PDF_PATH)
    print(f"Total pages: {len(doc)}")
    print(f"Biography pages: {BIO_START_PAGE + 1} to {BIO_END_PAGE}")

    print("Extracting text with font metadata...")
    all_lines, bio_starts = collect_bio_starts(doc)
    print(f"Total text lines extracted: {len(all_lines)}")
    print(f"Biography starts detected: {len(bio_starts)}")

    print("Segmenting biographies...")
    biographies = []  # list of (clean_text, raw_lines)
    for i, (gidx, pidx, ld) in enumerate(bio_starts):
        end_gidx = bio_starts[i + 1][0] if i + 1 < len(bio_starts) else len(all_lines)
        raw_lines = extract_bio_text(all_lines, gidx, end_gidx)
        clean_text = clean_biography_text(raw_lines)
        biographies.append((clean_text, raw_lines))

    print(f"Biographies segmented: {len(biographies)}")

    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)

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


if __name__ == "__main__":
    main()
