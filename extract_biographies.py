#!/usr/bin/env python3
"""
Extract biographies from BiographieNationale_Volume1.pdf
Each biography is saved as a separate UTF-8 .txt file in biographies_finales/
"""

import fitz  # PyMuPDF
import re
import os
import shutil

PDF_PATH = "BiographieNationale_Volume1.pdf"
OUTPUT_DIR = "biographies_finales"
LOG_FILE = "rapport_final.log"

# Page where actual biographies begin (0-indexed). Page 42 in 1-based = index 41
BIO_START_PAGE = 41

# Uppercase letter class including accented characters
UC = r'A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖÙÚÛÜÝÞ'


def clean_page_text(page_num, text):
    """Remove headers, footers, page numbers from a single page's text."""
    lines = text.split('\n')
    cleaned = []
    non_empty_seen = 0

    for idx, line in enumerate(lines):
        stripped = line.strip()

        # Skip empty lines at very start
        if non_empty_seen < 4 and not stripped:
            continue

        if stripped:
            non_empty_seen += 1

        # Skip standalone page numbers (just digits)
        if re.match(r'^\d{1,4}\s*$', stripped):
            continue

        # Skip column headers in the first few non-empty lines
        # These are ALL CAPS navigation headers like "ABEL — ABOLIN", "AGURTO"
        if non_empty_seen <= 4:
            if re.match(rf'^[{UC}\s\-—–.*\'()]+$', stripped):
                if len(stripped) < 80 and ',' not in stripped and 'né' not in stripped.lower():
                    continue

        # Skip "BIOGR. NAT. — T. I." type footers
        if re.match(r'^BIOC?R?\.\s*NAT\.\s*[-—–]\s*T\.\s*[IVX]+', stripped):
            continue

        # Skip "BIOGRAPHIE NATIONALE." header
        if stripped == "BIOGRAPHIE NATIONALE.":
            continue

        cleaned.append(line)

    return '\n'.join(cleaned)


def collapse_spaced_names(text):
    """Collapse spaced-out uppercase letters like 'A B B É' -> 'ABBÉ'.

    The PDF sometimes renders names with spaces between letters.
    We detect patterns of single uppercase letters separated by spaces
    at the start of a line (biography header position).
    """
    def collapse_spaced(m):
        full = m.group(0)
        prefix = m.group(1) or ''
        # The spaced part starts after the prefix
        spaced = full[len(prefix):]
        collapsed = re.sub(r'(?<=\w) (?=\w)', '', spaced)
        return prefix + collapsed

    # Pattern: line starts with single uppercase letters separated by spaces
    # e.g., "A B B É (Henri)" or "A D E L H A I R E,"
    # May be preceded by optional "* " for foreign entries
    # At least 3 spaced single chars to avoid false positives
    text = re.sub(
        rf'^(\*\s*)?([{UC}] ){{2,}}[{UC}][{UC}]*',
        collapse_spaced,
        text,
        flags=re.MULTILINE
    )
    return text


def merge_pages(pages):
    """Merge all cleaned page texts into one continuous stream."""
    cleaned_texts = []
    for page_num, text in pages:
        cleaned = clean_page_text(page_num, text)
        if cleaned.strip():
            cleaned_texts.append(cleaned)
    return '\n'.join(cleaned_texts)


def dehyphenate(text):
    """Fix words broken by hyphens at line endings."""
    # word-\n lowercase continuation -> merge
    text = re.sub(
        r'(\w)-\n(\w)',
        lambda m: m.group(1) + m.group(2) if m.group(2)[0].islower() else m.group(0),
        text
    )
    return text


def normalize_whitespace(text):
    """Clean up whitespace while preserving paragraph structure."""
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = [l.strip() for l in text.split('\n')]
    return '\n'.join(lines)


def join_broken_lines(text):
    """Join lines broken by column formatting into continuous paragraphs."""
    # Particles and short words that commonly continue a name on the next line
    NAME_CONTINUATIONS = {'VAN', 'DE', 'DU', 'DES', 'LE', 'LA', 'LES', 'DEN', 'DER',
                          'VANDER', 'VANDEN', 'VANDE', 'VER', 'TER', 'TEN', 'TE',
                          'D', "D'", 'OU', 'ET'}

    lines = text.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        while i + 1 < len(lines) and lines[i + 1]:
            next_line = lines[i + 1]
            next_stripped = next_line.strip()
            first_word = next_stripped.split(')')[0].split(',')[0].split('(')[0].strip() if next_stripped else ''

            # Join if next line starts lowercase or with continuation punctuation
            if (next_stripped[0].islower() or next_stripped[0] in '»«,;:)'):
                # But not if it looks like a new biography (uppercase name pattern)
                if not re.match(rf'^[{UC}]{{2,}}', next_stripped):
                    line = line.rstrip() + ' ' + next_stripped
                    i += 1
                    continue

            # Join if next line is a name particle continuation
            # e.g., current line ends with "(" and next starts with "VAN)"
            if first_word.rstrip(').,;:') in NAME_CONTINUATIONS:
                # Check if current line has an unclosed parenthesis
                if line.count('(') > line.count(')'):
                    line = line.rstrip() + ' ' + next_stripped
                    i += 1
                    continue

            # Join if next line starts with closing paren or is very short fragment
            if next_stripped.startswith(')'):
                line = line.rstrip() + ' ' + next_stripped
                i += 1
                continue

            break
        result.append(line)
        i += 1
    return '\n'.join(result)


def segment_biographies(text):
    """Split the full text into individual biographies using regex.

    A biography starts with:
    - UPPERCASE NAME (at least 2 uppercase letters, possibly with hyphens/apostrophes)
    - Followed by ( with first name or , with description
    - The name must be a proper noun (not random Latin/French text in caps)
    """
    # Two patterns:
    # 1. NAME (Prénom...) — most common
    # 2. NAME, descriptive text — less common but valid (e.g., "ABOLIN, septième abbé...")

    bio_pattern = re.compile(
        r'^'
        r'(\*?\s*'                                    # Optional asterisk
        r'[' + UC + r']'                              # First uppercase letter
        r'[' + UC + r'\-\' ]{1,50})'                  # Rest of name (uppercase, hyphens, apostrophes)
        r'\s*'
        r'(?:'
        r'\([^)]{2,}'                                 # Followed by (Prénom... — at least 2 chars inside
        r'|'
        r',\s*(?:'                                    # Or comma followed by biographical descriptors
        r'(?:dit|née?|saint|abbé|évêque|roi|duc|'
        r'comte|baron|prince|seigneur|chevalier|'
        r'cardinal|chanoine|prieur|moine|'
        r'peintre|sculpteur|graveur|dessinateur|'
        r'écrivain|poète|musicien|compositeur|'
        r'architecte|médecin|chirurgien|'
        r'professeur|docteur|théologien|'
        r'homme\s+de|militaire|général|colonel|capitaine|'
        r'avocat|juriste|jurisconsulte|'
        r'historien|chroniqueur|annaliste|'
        r'imprimeur|libraire|éditeur|'
        r'philologue|philosophe|mathématicien|'
        r'naturaliste|botaniste|astronome|'
        r'diplomate|magistrat|conseiller|'
        r'ingénieur|amiral|navigateur|'
        r'florissait|vivait|mort|décédé|'
        r'\d{1,2}e?\s*(?:abbé|évêque|comte|duc))'     # ordinal + title
        r'|[a-zàáâãäåæçèéêëìíîïðñòóôõöùúûüýþ]'        # Or just lowercase word after comma
        r')'
        r')',
        re.MULTILINE
    )

    matches = list(bio_pattern.finditer(text))

    if not matches:
        return []

    # Filter out false positives
    filtered = []
    for m in matches:
        name = m.group(1).strip().lstrip('*').strip()
        # Name should have at least 2 characters (after removing spaces)
        name_collapsed = name.replace(' ', '')
        if len(name_collapsed) < 2:
            continue
        # Skip if name is too long (likely a sentence fragment)
        if len(name_collapsed) > 40:
            continue
        # Skip common false positives - Latin words, roman numerals alone
        if name_collapsed in ('II', 'III', 'IV', 'VI', 'VII', 'VIII', 'IX', 'XI',
                              'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII',
                              'XIX', 'XX', 'XXI', 'ART', 'NOTE', 'NB'):
            continue
        filtered.append(m)

    biographies = []
    for i, match in enumerate(filtered):
        start = match.start()
        end = filtered[i + 1].start() if i + 1 < len(filtered) else len(text)
        bio_text = text[start:end].strip()
        header = match.group(0).strip()
        biographies.append((header, bio_text))

    return biographies


def extract_filename(header, bio_text):
    """Extract filename from biography header.

    Format: NOM (Prénom).txt
    """
    first_line = bio_text.split('\n')[0].strip()

    # Try pattern: NAME (Prénom), ... or NAME (Prénom VAN), ...
    m = re.match(
        rf'^(\*?\s*[{UC}][{UC}\s\-\'\.]*'
        r'\s*\([^)]*\))',
        first_line
    )
    if m:
        name = m.group(1).strip().lstrip('*').strip()
    else:
        # Try NAME, description pattern — take just the name
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

    # Replace filesystem-forbidden characters: \ / : * ? " < > |
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    # Clean up multiple spaces
    name = re.sub(r'\s+', ' ', name)

    return name + '.txt'


def is_cross_reference(bio_text):
    """Check if a biography entry is just a cross-reference (Voir ...)."""
    text = bio_text.strip()
    lines = [l for l in text.split('\n') if l.strip()]
    full = ' '.join(lines)
    # A cross-reference contains "Voir" (possibly concatenated like "VoirSPIRA")
    if len(full) < 300 and re.search(r'Voir', full, re.IGNORECASE):
        return True
    return False


def is_false_positive(bio_text):
    """Detect entries that are clearly not biographies (fragments, footnotes, etc.)."""
    text = bio_text.strip()

    # Very short fragments that are just name variants or incomplete
    if len(text) < 80:
        # Bibliography reference or footnote
        if re.match(r'^[A-Z\s\-]+,?\s*(pp?\.\s*\d|t\.\s*[IVX\d]|édit\.|l\.\s*[IVX])', text):
            return True
        # Just a name with "ou" (variant name, part of previous bio)
        if re.search(r'\bou\b|\bOU\b', text):
            return True
        # Name fragment ending abruptly: NAME (Prénom). or NAME (Prénom),
        # without actual biographical content
        lines = [l for l in text.split('\n') if l.strip()]
        full = ' '.join(lines)
        # If it's just a name possibly followed by a single word or nothing
        if re.match(rf'^[{UC}\s\-\']+\s*(\([^)]*\))?\s*[.,;:]?\s*\S{{0,30}}\s*$', full):
            return True

    # Entries under 150 chars that end mid-sentence (no period/author at end)
    # These are fragments that got split from the previous or next biography
    if len(text) < 150:
        # Check if text ends abruptly (no sentence-ending punctuation)
        last_char = text.rstrip()[-1] if text.rstrip() else ''
        if last_char not in '.!?:)' and not re.search(r'[A-Z][a-z]+\.\s*$', text):
            # Doesn't end with punctuation or an author name
            # Check if it looks like a truncated fragment
            if not re.search(r'\.\s*$', text):
                return True

    return False


def main():
    print(f"Opening {PDF_PATH}...")
    doc = fitz.open(PDF_PATH)
    print(f"Total pages: {len(doc)}")

    # Step 1: Extract raw text from biography pages
    print(f"Extracting text from page {BIO_START_PAGE + 1} onwards...")
    pages = []
    for i in range(BIO_START_PAGE, len(doc)):
        text = doc[i].get_text()
        pages.append((i + 1, text))

    # Step 2: Clean and merge
    print("Cleaning and merging pages...")
    full_text = merge_pages(pages)

    # Step 3: Collapse spaced-out names
    print("Collapsing spaced-out names...")
    full_text = collapse_spaced_names(full_text)

    # Step 4: Dehyphenate
    print("Dehyphenating...")
    full_text = dehyphenate(full_text)

    # Step 5: Join broken lines
    print("Joining broken lines...")
    full_text = join_broken_lines(full_text)

    # Step 6: Normalize whitespace
    full_text = normalize_whitespace(full_text)

    # Step 7: Segment into biographies
    print("Segmenting biographies...")
    biographies = segment_biographies(full_text)
    print(f"Found {len(biographies)} biography entries")

    # Step 8: Create output directory (fresh)
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)

    # Step 9: Write files and generate report
    log_entries = []
    written = 0
    skipped_xrefs = 0
    skipped_false = 0
    filename_counts = {}

    for header, bio_text in biographies:
        if is_cross_reference(bio_text):
            skipped_xrefs += 1
            continue

        if is_false_positive(bio_text):
            skipped_false += 1
            continue

        filename = extract_filename(header, bio_text)

        # Handle duplicate filenames
        if filename in filename_counts:
            filename_counts[filename] += 1
            base, ext = os.path.splitext(filename)
            filename = f"{base} ({filename_counts[filename]}){ext}"
        else:
            filename_counts[filename] = 0

        filepath = os.path.join(OUTPUT_DIR, filename)

        clean_text = bio_text.strip()

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(clean_text)

        word_count = len(clean_text.split())
        char_count = len(clean_text)
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


if __name__ == "__main__":
    main()
