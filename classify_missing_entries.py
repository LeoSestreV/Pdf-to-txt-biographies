# Based on manual review of the extracted contexts, classify each entry

results = []

# Format: (Page, Name_as_listed, Type, Notes)

# Page 83
results.append((83, "ADRIANO", "CROSS_REF", "Voir WILLAERT (Adrien) - redirect to Willaert"))
results.append((83, "ADRIANI (Adr.)", "CROSS_REF", "Voir ADRIAENSSENS (Adr.) - redirect"))

# Page 86
results.append((86, "AEGIDIUS A GANDAVO", "CROSS_REF", "Voir GILLES DE GAND - redirect"))

# Page 104
results.append((104, "AFFLIGHEM (Guillaume D')", "CROSS_REF", "Voir GUILLAUME D'AFFLIGHEM - redirect"))
results.append((104, "AGATHOCHRONUS (A.)", "CROSS_REF", "Voir BONTEMPS - redirect"))
results.append((104, "AGNUS (Jean)", "CROSS_REF", "Voir LAMMENS (Jean) - redirect"))

# Page 112
results.append((112, "AINEFFE (Georg.-Aur. D')", "CROSS_REF", "Voir DAYNEFFE - redirect"))
results.append((112, "EMARD / ENARD", "ALREADY_EXISTS", "Alternate names listed in AINARD entry header, not separate entries"))

# Page 142
results.append((142, "ALBUS (Jean)", "CROSS_REF", "Voir DE WITTE (Jean) - redirect"))

# Page 143
results.append((143, "ALDENARDO (Arn. DE)", "CROSS_REF", "Voir WIEMERSCHE (Arn. DE) - redirect"))

# Page 158
results.append((158, "ALLAUDA / ALAUDA", "CROSS_REF", "Voir LEEUWERICK (Eustache) - redirect"))

# Page 160
results.append((160, "ALSACE (Thomas D')", "FALSE_POSITIVE", "No entry for 'Thomas d'Alsace'; text mentions Thierry d'Alsace in body of another bio"))

# Page 171
results.append((171, "AMELEN (Jean) / AMELIUS", "CROSS_REF", "Voir APPELMANS - redirect"))

# Page 175
results.append((175, "ANASTASE (Olivier DE SAINT-)", "CROSS_REF", "Voir DEUROCK - redirect"))

# Page 188
results.append((188, "III", "FALSE_POSITIVE", "Roman numeral 'III' in text body (prophecy numbering), not an entry name"))

# Page 189
results.append((189, "ANGELIS (Guill. AB)", "CROSS_REF", "Voir ENGELEN (Guill. VAN) - redirect"))

# Page 191
results.append((191, "ANIEN", "CROSS_REF", "Voir COUSSERE (Anien) - redirect"))
results.append((191, "ANNAPES", "CROSS_REF", "Voir HANAPES - redirect"))

# Page 208
results.append((208, "AUSFRIDUS", "ALREADY_EXISTS", "Alternate name listed in ANSFRIDE entry header, not a separate entry"))

# Page 214
results.append((214, "ANTINES (D. Francois-Maur D')", "CROSS_REF", "Voir DANTINES (B. Francois-Maur) - redirect"))

# Page 219
results.append((219, "APS (Jean D')", "CROSS_REF", "Voir JEAN D'APS - redirect"))

# Page 224
results.append((224, "ARBORE (Dom. AB)", "CROSS_REF", "Voir VANDEN BOOM (Dominique) - redirect"))
results.append((224, "ARCHANGELUS TENERAMUNDANUS", "CROSS_REF", "Voir HUYLENBROUCK (Francois) - redirect"))
results.append((224, "ARCIS (Lambert D')", "CROSS_REF", "Voir DARCHIS (Lambert) - redirect"))
results.append((224, "ARCKEL (Jean D')", "CROSS_REF", "Voir JEAN D'ARCKEL - redirect"))

# Page 288
results.append((288, "ASPEL (Guillaume VAN)", "CROSS_REF", "Voir ABSEL (Guillaume VAN) - redirect"))

# Page 294
results.append((294, "ASSENEDE (Thierry VAN)", "CROSS_REF", "Voir DIEDERICK VAN ASSENEDE - redirect"))

# Page 313
results.append((313, "AUDOMARUS A SANCTO BERTIO", "CROSS_REF", "Voir DE SMET - redirect"))

# Page 314
results.append((314, "AUFROI", "CROSS_REF", "Voir ANSFRIDE - redirect"))
results.append((314, "AULA (Barthelemy DE)", "CROSS_REF", "Voir HOVE (Barthelemy VAN) - redirect"))

# Page 326
results.append((326, "AXPOELE ou AXELPOELE (VAN)", "FULL_BIO", "Full biography of artist family in Ghent, 14th-15th century painters/sculptors guild"))

# Page 340
results.append((340, "BACCIUS (Martin)", "CROSS_REF", "Voir BACK (Martin) - redirect"))
results.append((340, "BACHAERUS (Andre)", "CROSS_REF", "Voir DE BACKER (Andre) - redirect"))
results.append((340, "BACHERIUS (Andre-Eloi)", "CROSS_REF", "Voir DE BACKER (Andre-Eloi) - redirect"))
results.append((340, "BACHERIUS (Jean-Aug.)", "CROSS_REF", "Voir DE BACKER (Jean) - redirect"))
results.append((340, "BACHERIUS (Josse)", "CROSS_REF", "Voir DE BACKER (Josse) - redirect"))

# Page 341
results.append((341, "BACHERIUS (Pierre)", "CROSS_REF", "Voir DE BACKER (Pierre) - redirect"))

# Page 346
results.append((346, "BACULETO (Michel DE)", "CROSS_REF", "Voir MICHEL DE BACULETO - redirect"))
results.append((346, "BACX (Nicaise)", "CROSS_REF", "Voir BAXIUS (Nicaise) - redirect"))
results.append((346, "BACQUERE (Benoit)", "CROSS_REF", "Voir DEBACQUERE (Benoit) - redirect"))

# Page 356
results.append((356, "BAERSIUS (Henri)", "CROSS_REF", "Voir DE BAER (Henri) - redirect"))
results.append((356, "D E BAER (Henri)", "CROSS_REF", "Same as BAERSIUS - Voir DE BAER (Henri), 'D EBAER' is OCR artifact of 'DE BAER'"))

# Page 365
results.append((365, "BAILLEUL (Nicolas DE)", "CROSS_REF", "Voir BELLE (Nicolas VAN) - redirect"))

# Page 369
results.append((369, "BAIUS (Jacques)", "CROSS_REF", "Voir BAY (Jacques DE) - redirect"))

# Page 380
results.append((380, "COSTERE / PIERKEN (Balten)", "FALSE_POSITIVE", "Names appear inside body of BALTENS (Pieter) bio - guild register citations, not separate entries"))

# Page 400
results.append((400, "BAREND VAN BRUSSEL", "CROSS_REF", "Voir ORLEY (Bernard VAN) - redirect"))

# Page 403
results.append((403, "BARLENUS (Jean)", "CROSS_REF", "Voir BAERLE (Jean DE) - redirect"))
results.append((403, "BARRAL (Guillaume DE)", "CROSS_REF", "Voir GUILLAUME DE BARRAL - redirect"))

# Page 412
results.append((412, "BARTIUS (Arn.)", "CROSS_REF", "Voir BAERT (Arn.) - redirect"))
results.append((412, "BARTOLLET (Laurent)", "CROSS_REF", "Voir BERTHOLET (Laurent) - redirect"))
results.append((412, "BRA", "FALSE_POSITIVE", "Fragment 'LIBRA' in body of BARTOLOMAEI bio, not an entry name"))

# Page 413
results.append((413, "BASILIDES D'ATH", "CROSS_REF", "Voir DE LA PLACE (Jean) - redirect"))

# Print summary table
print("=" * 130)
print(f"{'Page':<6} {'Name':<40} {'Type':<18} {'Notes'}")
print("=" * 130)

counts = {"CROSS_REF": 0, "FALSE_POSITIVE": 0, "FULL_BIO": 0, "ALREADY_EXISTS": 0}

for page, name, typ, notes in sorted(results, key=lambda x: (x[0], x[1])):
    counts[typ] += 1
    print(f"{page:<6} {name:<40} {typ:<18} {notes}")

print("=" * 130)
print(f"\nSUMMARY:")
print(f"  Total entries checked: {len(results)}")
for k, v in sorted(counts.items()):
    print(f"  {k}: {v}")
print(f"\n  REAL MISSING BIOGRAPHIES THAT NEED EXTRACTION: {counts['FULL_BIO']}")
print(f"  (All others are cross-references, false positives, or already extracted under different names)")

