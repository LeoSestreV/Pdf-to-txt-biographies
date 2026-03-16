import fitz
import re

doc = fitz.open("/home/user/Pdf-to-txt-biographies/BiographieNationale_Volume1.pdf")

# Define all entries to check: (page_1indexed, [names])
entries_to_check = [
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
    (313, ["AUDOMARUS", "SANCTO BERTIO"]),
    (314, ["AUFROI", "AULA"]),
    (326, ["AXPOELE", "AXELPOELE"]),
    (340, ["BACCIUS", "BACHERIUS", "BACHÆRUS", "BACHAERUS"]),
    (341, ["BACHERIUS"]),
    (346, ["BACULETO", "BACX", "BACQUERE"]),
    (356, ["BAERSIUS", "EBAER"]),
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

def extract_context(text, name, context_chars=400):
    """Find name in text and return surrounding context"""
    # Try case-insensitive search
    pattern = re.compile(re.escape(name), re.IGNORECASE)
    match = pattern.search(text)
    if match:
        start = max(0, match.start() - 150)
        end = min(len(text), match.end() + context_chars)
        return text[start:end]
    return None

def classify_entry(context, name):
    """Classify an entry based on its surrounding text"""
    if context is None:
        return "FALSE_POSITIVE", "Name not found on page"
    
    # Normalize for checking
    ctx_lower = context.lower()
    
    # Check for Voir/Voy. cross-references near the name
    # Look for patterns like "Voir X" or "Voy." shortly after the name
    name_pos = ctx_lower.find(name.lower())
    if name_pos == -1:
        name_pos = 0
    
    after_name = ctx_lower[name_pos:]
    
    # Cross-reference patterns
    voir_patterns = [
        r'voir\s+\w+', r'voy\.\s+\w+', r'voyez\s+\w+',
        r'v\.\s+\w+', r'voir\s+ce\s+nom', r'voir\s+ce\s+mot',
    ]
    
    is_cross_ref = False
    for pat in voir_patterns:
        m = re.search(pat, after_name[:200])
        if m:
            is_cross_ref = True
            break
    
    # Check if it's a substantial entry (has multiple lines of content)
    # A full bio typically has dates, descriptions, etc.
    after_text = context[name_pos:] if name_pos > 0 else context
    
    # Count substantial text after the name
    lines = [l.strip() for l in after_text.split('\n') if l.strip()]
    
    if is_cross_ref:
        return "CROSS_REF", f"Contains cross-reference redirect"
    
    return "NEEDS_REVIEW", "Found on page"

# Now do the actual checking with detailed output
results = []

print("=" * 120)
print(f"{'Page':<6} {'Name':<35} {'Type':<18} {'Notes'}")
print("=" * 120)

for page, names in entries_to_check:
    text = get_page_text(page)
    # Also get adjacent pages for context
    text_prev = get_page_text(page - 1)
    text_next = get_page_text(page + 1)
    combined = text_prev + "\n===PAGE_BREAK===\n" + text + "\n===PAGE_BREAK===\n" + text_next
    
    for name in names:
        context = extract_context(text, name, 500)
        if context is None:
            # Try combined text
            context = extract_context(combined, name, 500)
        
        # Print the raw context for manual review
        print(f"\n--- Page {page}: {name} ---")
        if context:
            # Clean up for display
            display = context.replace('\n', ' | ')
            # Truncate
            if len(display) > 600:
                display = display[:600] + "..."
            print(f"CONTEXT: {display}")
        else:
            print(f"CONTEXT: [NOT FOUND on page {page} or adjacent pages]")
        
        results.append((page, name, context))

doc.close()
