#!/usr/bin/env python3
"""
Extract biographies from BiographieNationale_Volume1.pdf

Uses PyMuPDF font metadata (bold detection) combined with text pattern matching
and indentation analysis to reliably segment biographies.
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
FOOTER_Y_THRESHOLD = 590.0

UC = r'A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖÙÚÛÜÝÞ'

# X-position ranges for biography start indentation (alinéa)
# Left column: body text ~138-143, bio starts ~146-160
# Right column: body text ~302-307, bio starts ~308-325
LEFT_COL_INDENT_MIN = 146
LEFT_COL_INDENT_MAX = 165
RIGHT_COL_INDENT_MIN = 308
RIGHT_COL_INDENT_MAX = 330
COL_BOUNDARY = 290


def extract_page_data(page, page_idx):
    """Extract text spans with metadata from a page.

    Merges line objects that share the same y-position (within 2px tolerance)
    into a single logical line, sorted by x-position. This handles cases where
    the PDF splits a single visual line into multiple line objects (e.g.,
    "ADRIEN" + "LE" + "CHARTREUX," as separate line objects at the same y).
    """
    raw_lines = []
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

            raw_lines.append((y_top, x_left, spans))

    # Merge lines with same y-position (within 2px tolerance) AND same column.
    # First group by approximate y and column, then sort spans by x within group.
    raw_lines.sort(key=lambda t: (t[0], t[1]))

    # Group lines that are within 2px y tolerance and same column
    groups = []  # list of (min_y, min_x, [spans_with_x])
    for y, x, spans in raw_lines:
        is_left = x < COL_BOUNDARY
        merged = False
        for g in groups:
            g_y, g_x, g_spans_list, g_is_left = g
            if abs(y - g_y) <= 2.0 and is_left == g_is_left:
                g_spans_list.append((x, spans))
                # Update min y and min x
                g[0] = min(g[0], y)
                g[1] = min(g[1], x)
                merged = True
                break
        if not merged:
            groups.append([y, x, [(x, spans)], is_left])

    lines_data = []
    # Sort groups: left column first (by y), then right column (by y)
    # This preserves reading order in a two-column layout
    groups.sort(key=lambda g: (0 if g[3] else 1, g[0], g[1]))

    for min_y, min_x, spans_list, is_left in groups:
        # Sort spans within group by x-position
        spans_list.sort(key=lambda t: t[0])
        merged_spans = []
        for k, (sx, sp) in enumerate(spans_list):
            if k > 0 and merged_spans:
                # Add space between spans from different line objects
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
        has_bold_start = merged_spans[0]['bold'] if merged_spans else False

        lines_data.append({
            'y': min_y,
            'x': min_x,
            'spans': merged_spans,
            'full_text': full_text,
            'has_bold_start': has_bold_start,
            'page': page_idx,
        })

    return lines_data


def get_first_real_span(spans):
    """Get the first non-empty, non-asterisk span."""
    for s in spans:
        text = s['text'].strip()
        if text and text != '*':
            return s
    return spans[0] if spans else None


def is_indented_for_bio(x):
    """Check if x-position corresponds to biography start indentation."""
    if x < COL_BOUNDARY:
        return LEFT_COL_INDENT_MIN <= x <= LEFT_COL_INDENT_MAX
    else:
        return RIGHT_COL_INDENT_MIN <= x <= RIGHT_COL_INDENT_MAX


def has_name_pattern(text):
    """Check if text starts with an uppercase name followed by ( or , or 'ou'."""
    text = re.sub(r'^\*\s*', '', text).strip()
    # NAME (Prénom) or NAME, descriptor or NAME ou ALIAS
    if re.match(rf'^[{UC}][{UC}\s\-\'\.]+\s*(\(|,|ou\s)', text):
        name_part = re.split(r'[,(]', text)[0].strip()
        # Filter out roman numerals alone, single-letter abbreviations
        name_clean = re.sub(r'[\s\-\'\.]+', '', name_part)
        if len(name_clean) >= 3 and not re.match(r'^[IVXLCDM]+$', name_clean):
            return True
    return False


def is_biography_start(line_data, next_line_data=None, prev_line_data=None):
    """Detect if a line is the start of a new biography entry.

    Detection methods:
    1. Bold uppercase name (Times-Bold) with ( or , after name
    2. Spaced small-caps pattern (A B B É)
    3. Indented line with uppercase name + ( or , (for non-bold entries)
    4. Indented line with UPPERCASE + italic prénom
    5. Name alone on a line, next line starts with ( or ,
    6. Non-indented but preceded by author attribution + has name pattern
    """
    spans = line_data['spans']
    full = line_data['full_text']
    x = line_data['x']
    y = line_data['y']

    if not spans or not full:
        return False

    first = get_first_real_span(spans)
    if not first:
        return False

    first_text = first['text'].strip().lstrip('*').strip()

    # --- Method 1: Bold uppercase name ---
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
        if len(name_clean) > 0 and upper_count / len(name_clean) >= 0.5:
            if upper_count >= 2:
                rest = full[len(bold_name):].strip()
                if bold_name.rstrip().endswith('('):
                    rest = '(' + rest

                # Check that this is a real name entry, not a footnote/attribution
                # Footnotes/attributions are small bold text (size < 7.0) at bottom of page
                if first['size'] < 7.0 and y > 350:
                    return False

                # Skip author attributions like "P. F. X. de Ram." or "Ad. Siret."
                if re.match(r'^[A-Z][a-z]*[\.\-]\s*[A-Z]', bold_name):
                    # Likely author attribution, not biography
                    if first['size'] < 7.5:
                        return False

                has_comma = ',' in bold_name
                if (rest.startswith('(') or rest.startswith(',') or
                    re.match(r'^ou\s', rest, re.IGNORECASE) or
                    bold_name.rstrip().endswith(',') or
                    bold_name.rstrip().endswith('(') or
                    has_comma):
                    return True

                # Bold name alone on a line, next line has ( or ,
                if next_line_data:
                    next_full = next_line_data['full_text'].strip()
                    if next_full.startswith('(') or next_full.startswith(','):
                        return True
                    if re.match(r'^ou\s', next_full, re.IGNORECASE):
                        return True

    # --- Method 2: Spaced small-caps ---
    check_text = re.sub(r'^\*\s*', '', first['text'].strip())
    if re.match(rf'^[{UC}]( [{UC}]){{2,}}', check_text):
        rest = full[len(first['text'].strip()):].strip()
        if (rest.startswith('(') or rest.startswith(',') or
            re.match(r'^ou\s', rest, re.IGNORECASE)):
            return True
        # Spaced name alone on line, next line continues
        if next_line_data:
            next_full = next_line_data['full_text'].strip()
            if next_full.startswith('(') or next_full.startswith(','):
                return True

    # --- Method 3: Indented uppercase name (non-bold) ---
    if is_indented_for_bio(x) and has_name_pattern(full):
        return True

    # --- Method 4: Indented line with UPPERCASE (Italic-Prénom) pattern ---
    # For entries where bold is lost but name is still uppercase + italic prénom
    # Must be indented to avoid matching cross-reference text like "PEGHEM (Adrien VAN.)"
    if is_indented_for_bio(x) and len(spans) >= 2:
        first_real = get_first_real_span(spans)
        if first_real and not first_real['bold']:
            ft = first_real['text'].strip().lstrip('*').strip()
            ft_name = re.sub(r'\s*\(\s*$', '', ft).strip()
            if (re.match(rf'^[{UC}][{UC}\-\' ]+$', ft_name) and
                len(ft_name) >= 3 and
                not re.match(r'^[IVXLCDM\s]+$', ft_name)):
                # Next span should be italic (Prénom) or start with ( or ,
                for s in spans:
                    if s is first_real:
                        continue
                    next_text = s['text'].strip()
                    if not next_text:
                        continue
                    if (s['italic'] or next_text.startswith('(') or
                        next_text.startswith(',')):
                        return True
                    break

    # --- Method 5: Name alone on a line, next line starts with ( or , ---
    full_stripped = full.replace('*', '').strip()
    if (re.match(rf'^[{UC}][{UC}\s\-\'\.]+$', full_stripped) and
        3 <= len(full_stripped) <= 50 and
        not re.match(r'^[IVXLCDM\s]+$', full_stripped)):
        if next_line_data:
            next_full = next_line_data['full_text'].strip()
            if next_full.startswith('(') or next_full.startswith(','):
                return True
            if re.match(r'^\([^)]+\)', next_full):
                return True

    # --- Method 6: Non-indented NAME (Prénom/,) preceded by author attribution ---
    # Some entries lost their bold AND their indent in the PDF encoding.
    # Detect by checking if previous line ends with an author attribution pattern.
    # Attributions may be merged with body text on the same line, so check
    # the END of the previous line's text.
    if prev_line_data and has_name_pattern(full):
        prev_full = prev_line_data['full_text'].strip()
        prev_spans = prev_line_data['spans']

        is_attrib = False

        # Check if prev line ends with attribution-like text
        # Pattern: "Author Name." at the end, e.g., "Ad. Siret.", "P.-D. Kujl."
        # Also handles OCR-garbled versions like "sir«."
        if prev_full.endswith('.'):
            # Check last portion of text for attribution pattern
            last_part = prev_full.split('.')[-2] if '.' in prev_full[:-1] else prev_full
            last_part = last_part.strip()

            # Check if last bold spans are small (attribution size)
            last_bold_spans = [s for s in prev_spans if s['bold'] and s['text'].strip()]
            if last_bold_spans:
                max_bold_size = max(s['size'] for s in last_bold_spans)
                if max_bold_size < 7.5:
                    is_attrib = True

            # Check for initials-like ending: "Ad. Siret." or "F.-J. Fétis."
            if re.search(r'[A-Z][a-z]*[\.\-]\s*[A-Z][a-zà-ÿ]+\.\s*$', prev_full):
                is_attrib = True

            # Check for OCR-garbled attributions
            if re.search(r'[A-Z][a-z]*\.\s*[a-z]+[«»]+\.\s*$', prev_full):
                is_attrib = True

            # Check if prev line ends with a "Voir X." cross-reference
            if re.search(r'\bVoir\b.*\.\s*$', prev_full):
                is_attrib = True

        if is_attrib:
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
        prev_ld = all_lines[i - 1][2] if i > 0 else None
        if is_biography_start(ld, next_ld, prev_ld):
            bio_starts.append((gidx, pidx, ld))

    # Post-process 1: Remove false starts caused by hyphenation
    filtered = []
    for gidx, pidx, ld in bio_starts:
        if gidx > 0:
            prev_line = all_lines[gidx - 1][2]['full_text'].rstrip()
            if re.search(rf'[{UC}]{{2,}}-$', prev_line):
                continue
        filtered.append((gidx, pidx, ld))
    bio_starts = filtered

    # Post-process 2: Merge ONLY when the gap is 1-2 lines AND
    # the line just before the next start ends with a name particle
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

            if gap <= 2:
                # Collect text between starts
                between_text = []
                for j in range(gidx, next_gidx):
                    if j < len(all_lines):
                        between_text.append(all_lines[j][2]['full_text'])
                combined = ' '.join(between_text)

                # Never merge if first entry contains "Voir" (cross-reference)
                if 'Voir' in combined:
                    merged.append((gidx, pidx, ld))
                    continue

                # Only merge if the line before next start ends with a particle
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
    """Extract the biography name from raw lines.

    Strategy: find bold spans in the first line(s) for the name.
    If no bold, use uppercase text before the first descriptor word.
    """
    header_lines = []
    for line in raw_lines[:5]:
        line = line.strip()
        if not line:
            continue
        line = collapse_spaced_names(line)
        header_lines.append(line)

    if not header_lines:
        return ''

    # Join first few lines, handling hyphenation
    joined = ''
    for line in header_lines:
        if joined and joined.endswith('-'):
            if line and line[0].islower():
                joined = joined[:-1] + line
            elif line and line[0].isupper() and re.search(rf'[{UC}]{{2,}}-$', joined):
                joined = joined[:-1] + line
            else:
                joined = joined + line
        elif joined:
            joined = joined + ' ' + line
        else:
            joined = line

    # Remove leading asterisk
    joined = re.sub(r'^\*\s*', '', joined).strip()

    # Strategy 1: Find the name by looking for the transition from
    # uppercase/name-like text to lowercase descriptive text
    # The name part is: SURNAME (Prénom), ou ALIAS, dit LE SURNOM
    # It ends when we hit a lowercase descriptor word outside parentheses

    DESCRIPTORS = {
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
        'doyen', 'duc', 'duchesse', 'décédé', 'défenseur',
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
    }

    paren_depth = 0
    name_end = len(joined)

    i = 0
    while i < len(joined):
        ch = joined[i]
        if ch == '(':
            # Check for footnote reference like (1), (I), (2) etc.
            footnote_match = re.match(r'\([IVX\d]{1,3}\)', joined[i:])
            if footnote_match:
                # This is a footnote, not part of the name
                name_end = i
                while name_end > 0 and joined[name_end - 1] in ' ,':
                    name_end -= 1
                break
            paren_depth += 1
            i += 1
            continue
        elif ch == ')':
            paren_depth = max(0, paren_depth - 1)
            i += 1
            continue

        if paren_depth == 0:
            # Check for sentence start: period + space + uppercase letter
            if ch == '.' and i + 1 < len(joined) and joined[i + 1] == ' ':
                before = joined[:i].rstrip()
                # Stop at period unless it's a single-letter abbreviation
                if before and not re.search(r'\b[A-Z]$', before):
                    name_end = i + 1
                    break

            # Check for descriptor word at word boundary
            if i > 0 and joined[i - 1] in ' ,)':
                word_match = re.match(
                    r'[a-zàáâãäåæçèéêëìíîïðñòóôõöùúûüýþé]+', joined[i:])
                if word_match:
                    word = word_match.group(0)
                    if word in DESCRIPTORS:
                        name_end = i
                        while name_end > 0 and joined[name_end - 1] in ' ,':
                            name_end -= 1
                        break
                    # After closing paren: any lowercase word that isn't
                    # a name-linking particle signals end of name
                    if joined[i - 1] == ')' or (i > 1 and ')' in joined[max(0,i-5):i]):
                        NAME_LINKS = {'ou', 'dit', 'dite', 'surnommé', 'nommé',
                                      'appelé', 'appelée'}
                        if word not in NAME_LINKS:
                            name_end = i
                            while name_end > 0 and joined[name_end - 1] in ' ,':
                                name_end -= 1
                            break

        i += 1

    name = joined[:name_end].strip().rstrip(',').strip()

    # If name is still too long (> 80 chars), try to cut at a reasonable point
    if len(name) > 80:
        # Try cutting after the first closing parenthesis
        paren_end = name.find(')')
        if paren_end > 0 and paren_end < 80:
            # Check if there's more name after (ou ALIAS, dit LE SURNOM)
            rest = name[paren_end + 1:].strip()
            if rest and re.match(r'^(,\s*)?(ou\s|dit\s|dite\s|OU\s)', rest):
                # Keep looking for second paren close
                second_paren = rest.find(')')
                if second_paren > 0:
                    name = name[:paren_end + 1 + rest.index(')') + 1]
                else:
                    name = name[:paren_end + 1]
            else:
                name = name[:paren_end + 1]

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
    if len(name) > 90:
        name = name[:90].rstrip()

    if not name:
        name = 'UNKNOWN'

    return name + '.txt'


def is_cross_reference(bio_text):
    """Check if entry is just a 'Voir X' redirect."""
    text = bio_text.strip()
    if len(text) < 300 and re.search(r'\bVoir\b', text):
        return True
    return False


def is_false_positive(bio_text):
    """Detect fragments, footnotes, and non-biography entries.

    Conservative: only filter out clearly non-biographical content.
    """
    text = bio_text.strip()
    first_word = text.split()[0] if text.split() else ''
    first_word = re.sub(r'^\*\s*', '', first_word)
    first_word_clean = re.sub(r'[.,;:\(\)]', '', first_word)

    # Blacklisted first words that are never biography names
    BLACKLIST = {
        'IDEM', 'DOMINUS', 'FEBRUARII', 'ITEM', 'ANNO', 'OBIIT',
        'HIC', 'LIBER', 'HUJUS', 'DIXIT',
    }
    if first_word_clean in BLACKLIST:
        return True

    # Latin epitaphs/inscriptions
    if text.startswith('D. O. M.') or text.startswith('ET DAME'):
        return True

    # Detect Latin inscriptions: mostly uppercase with Latin words
    # Only filter if uppercase ratio > 0.8 AND contains Latin indicators
    sample = text[:300]
    upper_chars = sum(1 for c in sample if c.isupper())
    alpha_chars = sum(1 for c in sample if c.isalpha())
    if alpha_chars > 30 and upper_chars / alpha_chars > 0.8:
        # Check for Latin indicators
        latin_words = {'ET', 'QUI', 'QUOD', 'HIC', 'EST', 'FUIT', 'OBIIT',
                       'ANNO', 'DOMINI', 'JACET', 'CUBAT', 'HUJUS', 'POST',
                       'DIXIT', 'PONDUS', 'DOCUIT', 'CULTOR', 'FILIT'}
        words = set(re.findall(r'[A-Z]{2,}', sample))
        if words & latin_words:
            return True

    # Standalone particles are not biographies
    if first_word_clean in {'VAN', 'DE', 'DU', 'DES', 'LE', 'LA', 'LES', 'DEN', 'DER'}:
        return True

    # Roman numerals alone (not followed by name pattern)
    roman_match = re.match(r'^[IVXLCDM]{2,}(\s|$)', text)
    if roman_match:
        rest = text[roman_match.end():].strip()
        if not rest.startswith('(') and not rest.startswith(','):
            return True

    # Author attribution pattern: "A.-B. Name." or "F.-J. Fétis."
    if re.match(r'^[A-Z][\.\-][A-Z]?[\.\-]\s*[A-Z][a-z]+', text) and len(text) < 100:
        return True

    # Very short fragments (< 30 chars) with no sentence structure
    if len(text) < 30:
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
