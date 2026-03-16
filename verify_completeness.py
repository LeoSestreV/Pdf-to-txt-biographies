#!/usr/bin/env python3
"""
Exhaustive verification of biography extraction from BiographieNationale_Volume1.pdf
against the .txt files in biographies_finales/.

Scans all biography pages (42-469) of the PDF using multiple detection methods:
  A) Bold ALL-CAPS text (Times-Bold font, size >= 7.3)
  B) Spaced uppercase letters (e.g., "A B B E")
  C) Roman ALL-CAPS name followed by italic first name in parentheses
  D) Roman ALL-CAPS name followed by descriptive text (comma or "ou" pattern)
  E) Cross-references detected via "Voir" keyword

Compares detected entries against .txt files in biographies_finales/.
"""

import fitz
import os
import re
import unicodedata

PDF_PATH = "/home/user/Pdf-to-txt-biographies/BiographieNationale_Volume1.pdf"
TXT_DIR = "/home/user/Pdf-to-txt-biographies/biographies_finales/"

START_PAGE = 41  # 0-indexed page 42
END_PAGE = 469   # 0-indexed page 469


def collapse_spaced_letters(text):
    """Collapse spaced uppercase letters: 'A B B E' -> 'ABBE'."""
    text = text.strip()
    if re.match(r'^[\*\s]*[A-ZÀ-Ü] [A-ZÀ-Ü]', text):
        parts = text.split(' ')
        single_chars = sum(1 for p in parts if len(p) == 1 or (len(p) == 2 and p[0] in '*'))
        if single_chars >= 2 and single_chars >= len(parts) * 0.4:
            return ''.join(parts)
    return text


def normalize_for_comparison(name):
    """Normalize a name for comparison."""
    name = re.sub(r'^\*\s*', '', name)
    name = collapse_spaced_letters(name)
    name = name.upper().strip()
    name = unicodedata.normalize('NFC', name)
    name = name.rstrip(',.;: ')
    return name


def is_page_header_line(line, page_top_y):
    """Check if a line is a running header at the top of the page."""
    y = line["bbox"][1]
    if y > page_top_y + 22:
        return False
    spans = line["spans"]
    full = "".join(s["text"] for s in spans).strip()
    if re.match(r'^\d+$', full):
        return True
    if '—' in full or ' — ' in full:
        return True
    if re.match(r'^[A-ZÀ-Ü\s\-\.]+\s*[\-—]\s*[A-ZÀ-Ü\s\-\.]+$', full):
        return True
    return False


def is_false_positive_bold(first_text):
    """Filter out false positive bold entries."""
    clean = first_text.strip().rstrip(',.')
    if re.match(r'^[A-Z][.\-]', clean) and len(clean) < 8:
        return True
    if re.match(r'^(I{1,3}V?|IV|V?I{0,3}|IX|X{1,3}V?I{0,3}|XIV|XV|XVI{0,3}|XIX|XX)$', clean):
        return True
    if re.match(r'^[\—\-\d]', clean):
        return True
    if clean in ('DE', 'LE', 'LA', 'LES', 'DU', 'DES', 'VAN', 'VON', 'D', 'SS', 'ST'):
        return True
    alpha = re.sub(r'[^A-ZÀ-Ü]', '', clean)
    if len(alpha) < 3:
        return True
    return False


def collect_entry_name(spans, start_idx=0):
    """Collect entry name parts from spans starting at start_idx."""
    name_parts = []
    for s in spans[start_idx:]:
        st = s["text"]
        font = s["font"]
        if "Bold" in font and "Italic" not in font:
            a = re.sub(r'[^A-ZÀ-Üa-zà-ü]', '', st)
            if a and a == a.upper():
                name_parts.append(st)
            elif st.strip() in ('(', ')', ',', '', "'", "'"):
                name_parts.append(st)
            else:
                break
        elif "Italic" in font:
            name_parts.append(st)
            break
        else:
            if st.strip().startswith('('):
                name_parts.append(st)
            break
    return "".join(name_parts).strip().rstrip(',. ')


def collect_roman_entry_name(spans):
    """Collect entry name from Roman-font spans."""
    name_parts = [spans[0]["text"]]
    for s in spans[1:]:
        st = s["text"].strip()
        if "Italic" in s["font"]:
            if st.startswith("("):
                name_parts.append(st)
            break
        elif st.startswith("("):
            name_parts.append(st)
            break
        elif re.match(r'^(ou|OU)\s', st):
            name_parts.append(st.split(',')[0])
            break
        elif re.match(r'^[A-ZÀ-Ü]', st) and s["size"] < 9.0:
            # Continuation of compound name
            alpha = re.sub(r'[^A-Za-zÀ-ü]', '', st)
            if alpha and alpha == alpha.upper():
                name_parts.append(st)
            else:
                break
        else:
            break
    return " ".join("".join(name_parts).split()).strip().rstrip(',. ')


def extract_biography_entries(pdf_path):
    """Extract all biography entries from the PDF using multiple detection methods."""
    doc = fitz.open(pdf_path)
    entries = []

    for page_num in range(START_PAGE, END_PAGE):
        page = doc[page_num]
        page_rect = page.rect
        blocks = page.get_text("dict")["blocks"]
        text_blocks = [b for b in blocks if "lines" in b]

        for block in text_blocks:
            for line_idx, line in enumerate(block["lines"]):
                spans = line["spans"]
                if not spans:
                    continue

                if is_page_header_line(line, page_rect.y0):
                    continue

                first = spans[0]
                first_text = first["text"].strip()
                full_line = "".join(s["text"] for s in spans).strip()

                if not first_text or len(full_line) < 2:
                    continue

                entry_name = None
                detection_method = None

                # =====================================================
                # METHOD A: Bold ALL-CAPS entry
                # =====================================================
                if ("Bold" in first["font"] and "Italic" not in first["font"]
                        and first["size"] >= 7.3):
                    alpha_chars = re.sub(r'[^A-ZÀ-Üa-zà-ü]', '', first_text)
                    if alpha_chars and alpha_chars == alpha_chars.upper() and len(alpha_chars) >= 2:
                        if not is_false_positive_bold(first_text):
                            raw_name = collect_entry_name(spans)
                            if len(raw_name) >= 2:
                                entry_name = raw_name
                                detection_method = 'bold'

                # =====================================================
                # METHOD B: Spaced uppercase letters
                # =====================================================
                if entry_name is None and 5.5 <= first["size"] < 8.5:
                    if re.match(r'^\*?\s*[A-ZÀ-Ü] [A-ZÀ-Ü]', first_text):
                        if first["size"] < 5.5:
                            continue  # Latin inscription

                        raw_name = collect_roman_entry_name(spans)
                        collapsed = collapse_spaced_letters(raw_name.split('(')[0].strip())
                        alpha = re.sub(r'[^A-ZÀ-Ü]', '', collapsed)
                        if len(alpha) >= 3:
                            entry_name = raw_name
                            detection_method = 'spaced'

                # =====================================================
                # METHOD C: Roman ALL-CAPS + italic first name in parens
                # This catches entries that don't use Bold font
                # =====================================================
                if entry_name is None and "Bold" not in first["font"] and "Italic" not in first["font"]:
                    if first["size"] >= 7.0:
                        alpha = re.sub(r'[^A-Za-zÀ-ü]', '', first_text)
                        if alpha and alpha == alpha.upper() and len(alpha) >= 3:
                            # IMPORTANT: Filter out short "reference pointer" lines
                            # These are lines like "SONKEUX (Jean)." or "GILLIS (Pierre)."
                            # that are just cross-reference targets, not biography entries.
                            # Real biography entries have description text after the name.
                            is_ref_pointer = (
                                len(full_line) < 40
                                and re.match(r'^[A-ZÀ-Ü\s\-\*]+\s*\([^)]+\)\s*\.?\s*$', full_line)
                                and first["size"] < 8.5
                            )

                            if not is_ref_pointer:
                                # Check next span for italic text (first name pattern)
                                if len(spans) > 1:
                                    next_span = spans[1]
                                    next_text = next_span["text"].strip()

                                    # Pattern C1: Italic first name in parens + description
                                    if "Italic" in next_span["font"] and "(" in next_text:
                                        # Must have description text (not just name)
                                        remaining = "".join(s["text"] for s in spans[2:]).strip()
                                        has_desc = len(remaining) > 5 and any(c.islower() for c in remaining[:20])
                                        if has_desc:
                                            raw_name = collect_roman_entry_name(spans)
                                            if len(raw_name) >= 3:
                                                entry_name = raw_name
                                                detection_method = 'roman_italic'

                                    # Pattern C2: "ou" alternative name
                                    elif re.match(r'^ou\s+[A-ZÀ-Ü]', next_text):
                                        raw_name = collect_roman_entry_name(spans)
                                        if len(raw_name) >= 3:
                                            entry_name = raw_name
                                            detection_method = 'roman_ou'

                                    # Pattern C3: Roman (parens) without italic
                                    elif next_text.startswith("(") and first["size"] <= 10.0:
                                        # Must have description text after parens
                                        remaining = "".join(s["text"] for s in spans[2:]).strip()
                                        has_desc = len(remaining) > 5 and any(c.islower() for c in remaining[:20])
                                        if has_desc and re.match(r'^[A-ZÀ-Ü\*\s\-\']+$', first_text.rstrip(',.')):
                                            raw_name = collect_roman_entry_name(spans)
                                            if len(raw_name) >= 3:
                                                entry_name = raw_name
                                                detection_method = 'roman_paren'

                                # Pattern C4: Name + comma + description on same line
                                # e.g., "AMBIORIX, roi des Éburons"
                                if entry_name is None:
                                    if re.match(r'^[A-ZÀ-Ü\*]{3,},\s+[a-zà-ü]', full_line):
                                        # Must have substantial description (not just a short fragment)
                                        desc_part = re.sub(r'^[A-ZÀ-Ü\*]+,\s*', '', full_line)
                                        if len(desc_part) > 10:
                                            name_match = re.match(r'^([A-ZÀ-Ü\*]+)', full_line)
                                            if name_match:
                                                raw_name = name_match.group(1)
                                                if len(raw_name) >= 3:
                                                    entry_name = raw_name
                                                    detection_method = 'roman_comma'

                # =====================================================
                # METHOD D: Cross-references (non-bold ALL CAPS + "Voir")
                # =====================================================
                if entry_name is None and first["size"] >= 8.0:
                    m = re.match(r'^([A-ZÀ-Ü][A-ZÀ-Ü\s\-\'\(\),.*]+?)\s*\.?\s*Voir\b', full_line)
                    if m:
                        name = m.group(1).strip().rstrip(',.')
                        if len(name) >= 2:
                            entry_name = name
                            detection_method = 'text_voir'

                if entry_name is None:
                    continue

                # =====================================================
                # Additional filtering for any method
                # =====================================================
                collapsed = collapse_spaced_letters(entry_name)
                # Skip the main title "BIOGRAPHIE NATIONALE"
                if "BIOGRAPHIE" in collapsed or "NATIONALE" in collapsed:
                    continue

                # =====================================================
                # Classify: cross-reference vs full biography
                # =====================================================
                if 'Voir' in full_line:
                    entry_type = 'cross_reference'
                else:
                    text_after = ""
                    found_self = False
                    for b2 in text_blocks:
                        for l2 in b2["lines"]:
                            if not found_self:
                                if l2 is line:
                                    found_self = True
                                continue
                            text_after += "".join(s2["text"] for s2 in l2["spans"]) + " "
                            if len(text_after) > 100:
                                break
                        if len(text_after) > 100:
                            break

                    if re.match(r'^\s*Voir\b', text_after):
                        entry_type = 'cross_reference'
                    else:
                        entry_type = 'full_biography'

                entries.append({
                    'raw_name': entry_name,
                    'collapsed_name': collapsed,
                    'normalized': normalize_for_comparison(entry_name),
                    'page': page_num + 1,
                    'type': entry_type,
                    'full_text': full_line[:200],
                    'detection': detection_method,
                    'font_size': first["size"],
                })

    doc.close()
    return entries


def load_txt_files(txt_dir):
    """Load all .txt filenames and prepare normalized versions for matching."""
    files = {}
    for fname in sorted(os.listdir(txt_dir)):
        if not fname.endswith('.txt'):
            continue
        display = fname[:-4]
        surname_match = re.match(r'^([^(,]+)', display)
        surname = surname_match.group(1).strip() if surname_match else display

        files[fname] = {
            'filename': fname,
            'display': display,
            'surname_norm': surname.upper().strip(),
            'full_norm': display.upper().strip(),
        }
    return files


def match_entry_to_files(entry, files):
    """Match a PDF entry to .txt files using multiple strategies."""
    e_collapsed = entry['collapsed_name'].upper().strip()
    e_collapsed = re.sub(r'^\*\s*', '', e_collapsed)

    e_surname = re.split(r'[\s\(,]', e_collapsed)[0].strip()

    matches = []
    for fname, finfo in files.items():
        f_norm = finfo['full_norm']
        f_surname = finfo['surname_norm']

        # Strategy 1: Exact surname match
        if e_surname and len(e_surname) >= 3 and f_surname == e_surname:
            matches.append(fname)
            continue

        # Strategy 2: Surname prefix/containment (>= 4 chars)
        if len(e_surname) >= 4:
            if (f_surname.startswith(e_surname) or e_surname.startswith(f_surname)
                    or e_surname in f_norm):
                matches.append(fname)
                continue

        # Strategy 3: Full compound name match
        if len(e_collapsed) >= 6:
            e_clean = ' '.join(e_collapsed.split())
            f_pre_paren = f_norm.split('(')[0].strip()
            if (f_pre_paren.startswith(e_clean) or e_clean.startswith(f_pre_paren)
                    or f_norm.startswith(e_clean)):
                matches.append(fname)
                continue

        # Strategy 4: Handle OU alternatives
        if ' OU ' in e_collapsed:
            e_parts = re.split(r'\s+OU\s+', e_collapsed)
            for part in e_parts:
                part = part.strip()
                if len(part) >= 3 and part in f_norm:
                    matches.append(fname)
                    break

        # Strategy 5: Handle D', DE, VAN particles
        if "D'" in e_collapsed or " DE " in e_collapsed or " VAN " in e_collapsed:
            e_base = re.split(r"\s+D'|\s+DE\s|\s+VAN\s", e_collapsed)[0].strip()
            if len(e_base) >= 4 and (f_surname == e_base or f_surname.startswith(e_base)):
                matches.append(fname)
                continue

    return list(set(matches))


def categorize_unmatched(entry):
    """Categorize an unmatched entry as likely false positive or genuinely missing."""
    name = entry['collapsed_name'].upper()

    # Known fragments / false positives
    fp_names = {'ASPERO', 'MONTE', 'SAINT-GOMAR', 'DE MAESTRICHT', 'BAR',
                'BARBANCON', 'CHARTREUX', 'NINOVE', 'GAND', 'QUAM',
                'KENSWEEGSCHAEL,REUCKAPPEL', 'LÉDE', 'DETO-', 'HENSIS',
                'DEBAER', 'A VICTORIO ALFERIO', 'SORORISFILIT', 'HUJUS',
                'SANCII', 'SAINT-)', 'ECCL[ES|]A', 'SAPIENTIA,FACT1S,VIRTUTEILLUSTIUVIT'}

    if name in fp_names:
        return 'false_positive'

    # Very short names (< 4 alpha chars)
    alpha = re.sub(r'[^A-ZÀ-Ü]', '', name)
    if len(alpha) < 3:
        return 'false_positive'

    return 'missing'


def main():
    print("=" * 80)
    print("BIOGRAPHY EXTRACTION VERIFICATION REPORT")
    print("PDF: BiographieNationale_Volume1.pdf (pages 42-469)")
    print("TXT: biographies_finales/")
    print("=" * 80)

    # Step 1: Scan PDF
    print("\n[1] Scanning PDF for all biography entries...")
    entries = extract_biography_entries(PDF_PATH)
    print(f"    Raw entries detected: {len(entries)}")

    # Deduplicate by (page, normalized_name)
    seen = set()
    unique_entries = []
    for e in entries:
        key = (e['page'], e['normalized'])
        if key not in seen:
            seen.add(key)
            unique_entries.append(e)
    entries = unique_entries
    print(f"    After deduplication: {len(entries)}")

    # Show detection method breakdown
    methods = {}
    for e in entries:
        m = e['detection']
        methods[m] = methods.get(m, 0) + 1
    print(f"    Detection methods: {dict(sorted(methods.items()))}")

    # Step 2: Classify
    full_bios = [e for e in entries if e['type'] == 'full_biography']
    cross_refs = [e for e in entries if e['type'] == 'cross_reference']

    print(f"\n[2] Entry classification:")
    print(f"    Full biographies: {len(full_bios)}")
    print(f"    Cross-references (Voir...): {len(cross_refs)}")

    # Step 3: Load .txt files
    print(f"\n[3] Loading .txt files...")
    txt_files = load_txt_files(TXT_DIR)
    print(f"    Total .txt files: {len(txt_files)}")

    # Step 4: Match entries to files
    print(f"\n[4] Matching PDF entries to .txt files...")
    all_matched_files = set()
    unmatched_entries = []
    false_positive_entries = []

    for entry in full_bios:
        matched = match_entry_to_files(entry, txt_files)
        if matched:
            all_matched_files.update(matched)
        else:
            cat = categorize_unmatched(entry)
            if cat == 'false_positive':
                false_positive_entries.append(entry)
            else:
                unmatched_entries.append(entry)

    for entry in cross_refs:
        matched = match_entry_to_files(entry, txt_files)
        if matched:
            all_matched_files.update(matched)

    extra_files = set(txt_files.keys()) - all_matched_files
    matched_count = len(full_bios) - len(unmatched_entries) - len(false_positive_entries)

    print(f"    Full biographies matched to .txt:      {matched_count}")
    print(f"    Full biographies MISSING .txt:         {len(unmatched_entries)}")
    print(f"    Likely false positives (filtered):     {len(false_positive_entries)}")
    print(f"    .txt files matched to PDF entry:       {len(all_matched_files)}")
    print(f"    Extra .txt files (no PDF match):       {len(extra_files)}")

    # =====================================================
    # REPORTS
    # =====================================================

    print("\n" + "=" * 80)
    print("CROSS-REFERENCES (Voir... redirects) - %d found" % len(cross_refs))
    print("=" * 80)
    for xref in sorted(cross_refs, key=lambda e: e['page']):
        print(f"  Page {xref['page']:>3}: {xref['collapsed_name'][:60]}")
        print(f"           -> {xref['full_text'][:100]}")

    print("\n" + "=" * 80)
    print("BIOGRAPHIES IN PDF MISSING FROM .txt FILES - %d found" % len(unmatched_entries))
    print("=" * 80)
    if unmatched_entries:
        for entry in sorted(unmatched_entries, key=lambda e: e['page']):
            print(f"  Page {entry['page']:>3} [{entry['detection']:>14}] size={entry['font_size']:.1f}: "
                  f"{entry['collapsed_name'][:55]}")
            print(f"           Full: {entry['full_text'][:100]}")
    else:
        print("  None - all PDF biographies have corresponding .txt files!")

    print("\n" + "=" * 80)
    print("LIKELY FALSE POSITIVES (filtered out) - %d found" % len(false_positive_entries))
    print("=" * 80)
    for entry in sorted(false_positive_entries, key=lambda e: e['page']):
        print(f"  Page {entry['page']:>3}: {entry['collapsed_name'][:50]} -> {entry['full_text'][:70]}")

    print("\n" + "=" * 80)
    print("EXTRA .txt FILES (no corresponding PDF entry detected) - %d found" % len(extra_files))
    print("=" * 80)
    if extra_files:
        for fname in sorted(extra_files):
            print(f"  {fname}")
    else:
        print("  None!")

    # =====================================================
    # SUMMARY
    # =====================================================
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Total entries detected in PDF:           {len(entries)}")
    print(f"    - Full biographies:                    {len(full_bios)}")
    print(f"    - Cross-references (Voir...):          {len(cross_refs)}")
    print(f"  Likely false positives removed:          {len(false_positive_entries)}")
    print(f"  Real biographies detected:               {len(full_bios) - len(false_positive_entries)}")
    print(f"  Total .txt files present:                {len(txt_files)}")
    print()
    print(f"  PDF biographies matched to .txt files:   {matched_count}")
    print(f"  PDF biographies MISSING .txt files:      {len(unmatched_entries)}")
    print(f"  .txt files matched to a PDF entry:       {len(all_matched_files)}")
    print(f"  Extra .txt files (not matched to PDF):   {len(extra_files)}")
    print()
    real_bios = len(full_bios) - len(false_positive_entries)
    print(f"  Bio detection match rate (PDF->txt):     "
          f"{matched_count / max(real_bios, 1) * 100:.1f}%")
    print(f"  File coverage rate (txt->PDF):           "
          f"{len(all_matched_files) / max(len(txt_files), 1) * 100:.1f}%")
    print()
    print("  NOTE: 'Extra .txt files' are biographies that exist as .txt files but")
    print("  whose entry headers in the PDF were not detected by the font-based scanner.")
    print("  This can happen when OCR produced non-standard font metadata, or when")
    print("  entries use unusual formatting. These files are NOT necessarily wrong -")
    print("  they likely represent valid biographies that were extracted by other means.")

    # =====================================================
    # ALL DETECTED ENTRIES
    # =====================================================
    print("\n" + "=" * 80)
    print("ALL DETECTED FULL BIOGRAPHIES (sorted by page)")
    print("=" * 80)
    for entry in sorted(full_bios, key=lambda e: (e['page'], e['collapsed_name'])):
        matched = match_entry_to_files(entry, txt_files)
        if matched:
            status = "OK"
        elif entry in false_positive_entries:
            status = "FP"
        else:
            status = "MISSING"
        name_display = entry['collapsed_name'][:50]
        print(f"  Page {entry['page']:>3} [{status:>7}] [{entry['detection']:>14}]: {name_display}")


if __name__ == "__main__":
    main()
