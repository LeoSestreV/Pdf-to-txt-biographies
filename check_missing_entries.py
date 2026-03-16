import fitz
import re

doc = fitz.open("/home/user/Pdf-to-txt-biographies/BiographieNationale_Volume1.pdf")

# Define all entries to check: (page_1indexed, [names])
entries = [
    (83, ["ADRIANO", "ADRIANI"]),
    (86, ["A GANDAVO"]),
    (104, ["AFFLIGHEM", "AGATHOCHRONUS", "AGNUS"]),
    (112, ["AINEFFE", "ÉMARD", "ÉNARD"]),
    (142, ["ALBUS"]),
    (143, ["ALDENARDO"]),
    (158, ["ALLAUDA"]),
    (160, ["ALSACE"]),
    (171, ["AMELEN"]),
    (175, ["ANASTASE"]),
    (188, ["III"]),
    (189, ["ANGELIS"]),
    (191, ["ANIEN", "ANNAPES"]),
    (208, ["AUSFRIDUS"]),
    (214, ["ANTINES"]),
    (219, ["APS"]),
    (224, ["ARBORE", "ARCHANGELUS", "ARCIS", "ARCKEL", "TENERAMUNDANUS"]),
    (288, ["ASPEL"]),
    (294, ["ASSENEDE"]),
    (313, ["AUDOMARUS"]),
    (314, ["AUFROI", "AULA"]),
    (326, ["AXPOELE", "AXELPOELE"]),
    (340, ["BACCIUS", "BACHERIUS", "BACHÆRUS", "BACHAERUS"]),
    (341, ["BACHERIUS"]),
    (346, ["BACULETO", "BACX", "BACQUERE"]),
    (356, ["BAERSIUS", "EBAER", "BAER"]),
    (365, ["BAILLEUL"]),
    (369, ["BAIUS"]),
    (380, ["COSTERE", "PIERKEN"]),
    (400, ["BAREND"]),
    (403, ["BARLENUS", "BARRAL"]),
    (412, ["BARTIUS", "BARTOLLET", "BRA"]),
    (413, ["BASILIDES"]),
]

def get_page_text(page_num_1indexed):
    """Get text from a page (converting 1-indexed to 0-indexed)"""
    idx = page_num_1indexed - 1
    if idx < 0 or idx >= len(doc):
        return ""
    return doc[idx].get_text()

def find_entry_context(text, name, context_chars=500):
    """Find name in text and return surrounding context"""
    # Try case-insensitive search
    pattern = re.compile(re.escape(name), re.IGNORECASE)
    match = pattern.search(text)
    if match:
        start = max(0, match.start() - 200)
        end = min(len(text), match.end() + context_chars)
        return text[start:end]
    return None

def classify_entry(context, name):
    """Classify an entry based on its context"""
    if context is None:
        return "FALSE_POSITIVE", "Name not found on this page"
    
    # Normalize whitespace for analysis
    ctx_clean = re.sub(r'\s+', ' ', context)
    
    # Check for "Voir" / "Voy." cross-references near the name
    # Look for patterns like "NAME ... Voir X" or "NAME ... Voy. X"
    name_pat = re.compile(re.escape(name), re.IGNORECASE)
    m = name_pat.search(ctx_clean)
    if m:
        after_name = ctx_clean[m.end():m.end()+300]
        # Cross-ref patterns
        if re.search(r'^\s*[\(\)A-Za-zé,\.\s]{0,30}(Voy\.|Voir|V\.)\s', after_name):
            return "CROSS_REF", f"Cross-reference: {after_name[:150].strip()}"
        if re.search(r'(Voy\.|Voir|V\.)\s', after_name[:100]):
            # Check if it's a short entry that's mostly a redirect
            # Look for how much text before next entry
            return "CROSS_REF", f"Likely cross-ref: {after_name[:150].strip()}"
    
    return "NEEDS_REVIEW", context

# Now check each entry
results = []

for page, names in entries:
    text = get_page_text(page)
    # Also get adjacent pages for context
    text_prev = get_page_text(page - 1) if page > 1 else ""
    text_next = get_page_text(page + 1) if page < len(doc) else ""
    
    for name in names:
        context = find_entry_context(text, name)
        
        # If not found on primary page, check adjacent
        source_page = page
        if context is None:
            context = find_entry_context(text_prev, name)
            if context:
                source_page = page - 1
        if context is None:
            context = find_entry_context(text_next, name)
            if context:
                source_page = page + 1
        
        classification, notes = classify_entry(context, name)
        results.append({
            'page': page,
            'found_page': source_page,
            'name': name,
            'type': classification,
            'notes': notes,
            'context': context
        })

# Now let's do a more careful manual review of each entry
# Print all contexts so we can classify properly
print("=" * 120)
print(f"{'Page':<6} {'Name':<25} {'Type':<15} Notes")
print("=" * 120)

for r in results:
    # Refine classification based on context
    ctx = r['context']
    if ctx is None:
        r['type'] = 'FALSE_POSITIVE'
        r['final_notes'] = 'Name not found on page'
        print(f"{r['page']:<6} {r['name']:<25} {r['type']:<15} {r['final_notes']}")
        continue
    
    ctx_clean = re.sub(r'\s+', ' ', ctx).strip()
    name = r['name']
    
    # More refined classification
    name_pat = re.compile(re.escape(name), re.IGNORECASE)
    m = name_pat.search(ctx_clean)
    
    if m:
        after = ctx_clean[m.end():m.end()+400]
        before = ctx_clean[max(0,m.start()-200):m.start()]
        
        # Check if it's a "Voir/Voy" cross-reference
        is_crossref = False
        
        # Pattern: name followed shortly by Voy./Voir
        if re.search(r'^[\s\(\)A-Za-zéèêëàâäùûüïîôöç,\.\-\']{0,60}(Voy\.|Voir|V\.)\s', after, re.IGNORECASE):
            is_crossref = True
        
        # Pattern: within a larger entry, mentioned as cross-ref
        if re.search(r'(Voy\.|Voir)\s.*?' + re.escape(name), ctx_clean, re.IGNORECASE):
            # This name appears as the TARGET of a Voir reference, not as its own entry
            pass
        
        if is_crossref:
            r['type'] = 'CROSS_REF'
            # Extract the redirect target
            voir_match = re.search(r'(Voy\.|Voir|V\.)\s+([A-ZÉÈ][A-Za-zéèêëàâäùûüïîôöç\s\-\']+)', after)
            if voir_match:
                r['final_notes'] = f"Redirects to {voir_match.group(2).strip()}"
            else:
                r['final_notes'] = f"Cross-reference detected"
        else:
            # Check if it's a substantial bio or just a mention
            # Look for typical bio markers: birth/death dates, parenthetical descriptions
            # A real bio entry usually has the name in caps/bold followed by descriptive text
            
            # Check if name appears as a heading (caps, possibly with parenthetical info)
            heading_pat = re.compile(r'(' + re.escape(name) + r'[A-ZÉÈ\s]*[\(\s])', re.IGNORECASE)
            if heading_pat.search(ctx_clean):
                # Looks like a heading - check content length
                r['type'] = 'FULL_BIO'
                r['final_notes'] = f"Entry found"
            else:
                r['type'] = 'NEEDS_REVIEW'
                r['final_notes'] = f"Unclear - needs context review"
    else:
        r['type'] = 'FALSE_POSITIVE'
        r['final_notes'] = 'Pattern match issue'
    
    print(f"{r['page']:<6} {r['name']:<25} {r['type']:<15} {r['final_notes']}")

print("\n\n")
print("=" * 120)
print("DETAILED CONTEXT FOR EACH ENTRY (for manual verification)")
print("=" * 120)

for r in results:
    ctx = r.get('context', 'NOT FOUND')
    if ctx:
        ctx_display = re.sub(r'\s+', ' ', ctx).strip()[:500]
    else:
        ctx_display = "NOT FOUND ON PAGE"
    print(f"\n--- Page {r['page']} | {r['name']} | {r['type']} ---")
    print(ctx_display)
    print()

doc.close()
