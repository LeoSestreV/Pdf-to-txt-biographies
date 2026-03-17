"""Text cleaning, name extraction, and filename generation."""

import re

from config import ExtractionConfig
from constants import (
    UC, NAME_LINKS, SPACED_PARTICLES, TRAILING_PATTERNS,
)


def collapse_spaced_names(text):
    """Collapse 'A B B E' -> 'ABBE'."""
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
                        if word not in NAME_LINKS:
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


def fix_ocr_spacing(name, cfg: ExtractionConfig):
    """Fix OCR artifacts that insert spaces within words."""
    def collapse_spaced_word(m):
        return m.group(0).replace(' ', '')

    name = re.sub(
        r'(?<![A-ZÀ-Þa-zà-ÿ])(?:[A-ZÀ-Þ] ){2,}[A-ZÀ-Þ](?![A-ZÀ-Þa-zà-ÿ])',
        collapse_spaced_word, name
    )

    for pattern, fixed in SPACED_PARTICLES:
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
