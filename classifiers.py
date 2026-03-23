import re

from config import ExtractionConfig
from constants import (
    UC, FRENCH_STOP_WORDS, STANDALONE_PARTICLES, FRAGMENT_STARTERS,
    NAME_PARTICLES, NAME_CONTINUATION_PAIRS, NAME_LINKS,
)


def get_first_real_span(spans):
    for s in spans:
        text = s['text'].strip()
        if text and text != '*':
            return s
    return spans[0] if spans else None


def is_indented_for_bio(x, cfg: ExtractionConfig):
    lo, hi = cfg.left_col_indent if x < cfg.col_boundary else cfg.right_col_indent
    return lo <= x <= hi


def has_name_pattern(text, cfg: ExtractionConfig):
    text = re.sub(r'^\*\s*', '', text).strip()
    if re.match(rf'^[{UC}][{UC}\s\-\'\.]+\s*(\(|,|ou\s)', text):
        name_part = re.split(r'[,(]', text)[0].strip()
        name_clean = re.sub(r'[\s\-\'\.]+', '', name_part)
        if (len(name_clean) >= cfg.min_name_length and
                not re.match(r'^[IVXLCDM]+$', name_clean)):
            return True
    return False


def _check_bold_name(line_data, cfg, next_line_data, _prev_line_data):
    spans = line_data['spans']
    full = line_data['full_text']
    y = line_data['y']

    first = get_first_real_span(spans)
    if not first:
        return None
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


def _check_spaced_smallcaps(line_data, cfg, next_line_data, _prev_line_data):
    first = get_first_real_span(line_data['spans'])
    if not first:
        return None
    full = line_data['full_text']

    check_text = re.sub(r'^\*\s*', '', first['text'].strip())
    if not re.match(rf'^[{UC}]( [{UC}]){{2,}}', check_text):
        return None

    rest = full[len(first['text'].strip()):].strip()
    if (rest.startswith('(') or rest.startswith(',') or
            re.match(r'^ou\s', rest, re.IGNORECASE)):
        return True
    if next_line_data:
        next_full = next_line_data['full_text'].strip()
        if next_full.startswith('(') or next_full.startswith(','):
            return True
    return None


def _check_indented_name_pattern(line_data, cfg, _next_line_data, _prev_line_data):
    if is_indented_for_bio(line_data['x'], cfg) and has_name_pattern(line_data['full_text'], cfg):
        return True
    return None


def _check_indented_italic(line_data, cfg, _next_line_data, _prev_line_data):
    spans = line_data['spans']
    x = line_data['x']

    if not (is_indented_for_bio(x, cfg) and len(spans) >= 2):
        return None

    first_real = get_first_real_span(spans)
    if not first_real or first_real['bold']:
        return None

    ft = first_real['text'].strip().lstrip('*').strip()
    ft_name = re.sub(r'\s*\(\s*$', '', ft).strip()
    if not (re.match(rf'^[{UC}][{UC}\-\' ]+$', ft_name) and
            len(ft_name) >= cfg.min_name_length and
            not re.match(r'^[IVXLCDM\s]+$', ft_name)):
        return None

    for s in spans:
        if s is first_real:
            continue
        next_text = s['text'].strip()
        if not next_text:
            continue
        if s['italic'] or next_text.startswith('(') or next_text.startswith(','):
            return True
        break
    return None


def _check_name_alone(line_data, cfg, next_line_data, _prev_line_data):
    full = line_data['full_text']
    full_stripped = full.replace('*', '').strip()
    if not (re.match(rf'^[{UC}][{UC}\s\-\'\.]+$', full_stripped) and
            cfg.min_name_length <= len(full_stripped) <= cfg.max_name_alone_length and
            not re.match(r'^[IVXLCDM\s]+$', full_stripped)):
        return None

    if not next_line_data:
        return None
    next_full = next_line_data['full_text'].strip()
    if (next_full.startswith('(') or next_full.startswith(',') or
            bool(re.match(r'^\([^)]+\)', next_full))):
        return True
    return None


def _check_after_attribution(line_data, cfg, _next_line_data, prev_line_data):
    full = line_data['full_text']
    if not (prev_line_data and has_name_pattern(full, cfg)):
        return None

    prev_full = prev_line_data['full_text'].strip()
    prev_spans = prev_line_data['spans']

    if not prev_full.endswith('.'):
        return None

    last_bold_spans = [s for s in prev_spans if s['bold'] and s['text'].strip()]
    if last_bold_spans and max(s['size'] for s in last_bold_spans) < cfg.max_attribution_size:
        return True

    if re.search(r'[A-Z][a-z]*[\.\-]\s*[A-Z][a-zà-ÿ]+\.\s*$', prev_full):
        return True
    if re.search(r'[A-Z][a-z]*\.\s*[a-z]+[«»]+\.\s*$', prev_full):
        return True
    if re.search(r'\bVoir\b.*\.\s*$', prev_full):
        return True

    return None


BIO_START_VALIDATORS = [
    _check_bold_name,
    _check_spaced_smallcaps,
    _check_indented_name_pattern,
    _check_indented_italic,
    _check_name_alone,
    _check_after_attribution,
]


def is_biography_start(line_data, cfg: ExtractionConfig,
                       next_line_data=None, prev_line_data=None):
    spans = line_data['spans']
    full = line_data['full_text']

    if not spans or not full:
        return False

    for validator in BIO_START_VALIDATORS:
        result = validator(line_data, cfg, next_line_data, prev_line_data)
        if result is True:
            return True
        if result is False:
            return False

    return False


def is_name_continuation(prev_text, curr_text):
    prev = prev_text.strip()
    last_word = prev.rstrip('.,;:').split()[-1] if prev.split() else ''
    if last_word.upper() in NAME_PARTICLES:
        return True
    if prev.rstrip().endswith("D'") or prev.rstrip().endswith("d'"):
        return True
    if re.search(rf'[{UC}]{{2,}}-$', prev.rstrip()):
        return True

    last_two = ' '.join(prev.rstrip('.,;:').split()[-2:]) if len(prev.split()) >= 2 else ''
    return last_two.lower() in NAME_CONTINUATION_PAIRS


def is_cross_reference(bio_text, cfg: ExtractionConfig):
    text = bio_text.strip()
    if len(text) < cfg.xref_max_chars and re.search(r'\bVoir\b', text):
        return True
    if len(text) < cfg.xref_garbled_max_chars and re.search(r'\bVoir[A-Z]', text):
        return True
    if len(text) < cfg.xref_garbled_max_chars and re.search(r'\bVO[A-Z]{3,}', text):
        return True
    if len(text) < cfg.xref_max_chars and re.search(r"[AV]'?[oO]ir", text):
        return True
    if len(text) < cfg.xref_max_chars and re.search(
            r'[—\-\.]\s*T\.\s*[IVXLCDMlvxicdm]+,?\s*col\.', text):
        return True
    if len(text) < cfg.xref_max_chars and re.search(
            r'^[A-ZÀ-Þa-zà-ÿ\s\-\'\(\),]+\.\s*Col\.\s*\d+', text):
        return True
    return False


def is_false_positive(bio_text, cfg: ExtractionConfig, words: dict):
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
                          w not in FRENCH_STOP_WORDS]
            if not lower_words and len(upper_words) >= 3:
                return True

    sample = text[:cfg.latin_sample_chars]
    upper_chars = sum(1 for c in sample if c.isupper())
    alpha_chars = sum(1 for c in sample if c.isalpha())
    if alpha_chars > cfg.min_alpha_for_latin and upper_chars / alpha_chars > cfg.latin_uppercase_ratio:
        if set(re.findall(r'[A-Z]{2,}', sample)) & words['latin_indicators']:
            return True

    if len(text) < cfg.xref_garbled_max_chars and re.search(
            r'\b(?:Anno|œtatis|ætatis|obiit|natus)\s+[MDCLXVI]+\b', text, re.IGNORECASE):
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

    title_match = re.match(
        rf'^[{UC}]{{3,}},\s+[{UC}]{{3,}}(?:\s+(?:ET|OU|DE|DU|DES)\s+[{UC}]{{3,}})+',
        text)
    if title_match and '(' not in text[:title_match.end() + 20]:
        return True

    if first_word_clean and len(first_word_clean) >= 2:
        upper_in_first = sum(1 for c in first_word_clean if c.isupper())
        if upper_in_first / len(first_word_clean) < 0.5:
            return True

    if first_word_clean and re.search(r'(.)\1{2,}', first_word_clean):
        return True

    if re.match(r'^[A-ZÀ-Þ]+\s+(?:sculp|fecit|excudit|del|inv|pinx)\b', text):
        return True

    if re.search(r'\b(?:sterf|stierf)\s+(?:den|de)\b', text[:200], re.IGNORECASE):
        return True

    if re.match(r'^[A-ZÀ-Þ]+,\s+OU\s+bien\b', text):
        return True

    if re.match(r'^[A-ZÀ-Þ]+\s+(?:defendet|delineavit|invenit|pinxit)\b', text):
        return True

    if re.match(r'^(?:EX|IN|AD|CUM|PRO|QUOD)\s+[A-Z]', text) and len(text) < cfg.xref_max_chars:
        return True

    if re.match(r'^M?D[CLXVI]+\.', text):
        return True

    if re.match(r"^D'[A-ZÀ-Þ]{3,}\s+[A-ZÀ-Þ]{3,}", text):
        name_end = text.find(',')
        if name_end > 0:
            after = text[name_end + 1:name_end + 50].strip()
            if after and after[0].islower():
                first_w = re.match(r'[a-zà-ÿ]+', after)
                if first_w and first_w.group(0) not in words['descriptors']:
                    return True

    first_line = text.split('\n')[0] if '\n' in text else text[:200]
    first_line_words = re.findall(r'[A-ZÀ-Þa-zà-ÿ]{3,}', first_line)
    if len(first_line_words) >= 5:
        latin_count = sum(1 for w in first_line_words
                         if w.upper() in words['latin_indicators'])
        if latin_count >= 3:
            return True

    name_part = re.match(rf'^[{UC}][{UC}\s\-\'\.]+', text)
    if name_part:
        after_name = text[name_part.end():].strip()
        if after_name.startswith(','):
            after_comma = after_name[1:].strip()
            first_w = re.match(r"[a-zà-ÿ']+", after_comma)
            if first_w:
                word = first_w.group(0).rstrip("'")
                if (word not in words['descriptors'] and
                        word not in NAME_LINKS and
                        word not in FRENCH_STOP_WORDS and
                        word not in {'né', 'née', 'mort', 'morte', 'dit',
                                     'dite', 'surnommé', 'nommé', 'appelé',
                                     'plus', 'aussi', 'dont'}):
                    if '(' not in text[:100]:
                        return True

    return False


def split_merged_entries(bio_text, raw_lines, cfg: ExtractionConfig):
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
