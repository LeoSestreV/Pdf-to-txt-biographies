# Based on the detailed context review, here's the final classification

results = [
    # Page 83
    (83, "ADRIANO", "CROSS_REF", "Redirects to WILLAERT (Adrien). 'ADRIANO, musicien... Voir WILLAERT (Adrien).'"),
    (83, "ADRIANI (Adr.)", "CROSS_REF", "Redirects to ADRIAENSSENS (Adr.). 'ADRIANI (Adr.), écrivain ecclésiastique... Voir ADRIAENSSENS (Adr.).'"),
    
    # Page 86
    (86, "A GANDAVO (ÆGIDIUS)", "CROSS_REF", "Redirects to GILLES DE GAND. 'ÆGIDIUS A GANDAVO... Voir GILLES DE GAND.'"),
    
    # Page 104
    (104, "AFFLIGHEM (Guillaume D')", "CROSS_REF", "Redirects to GUILLAUME D'AFFLIGHEM. 'AFFLIGHEM (Guilllaume D')... Voir GUILLAUME D'AFFLIGHEM.'"),
    (104, "AGATHOCHRONUS (A.)", "CROSS_REF", "Redirects to BONTEMPS. 'AGATHOCHRONUS (A.), moine de Lobbes... Voir BONTEMPS.'"),
    (104, "AGNUS (Jean)", "CROSS_REF", "Redirects to LAMMENS (Jean). 'AGNUS (Jean), ecrivain ecclesiastique... Voir LAMMENS (Jean.)'"),
    
    # Page 112
    (112, "AINEFFE (Georg.-Aur. D')", "CROSS_REF", "Redirects to DAYNEFFE. 'AINEFFE (Georg.-Aur. D'), théologien... Voir DAYNEFFE.'"),
    (112, "ÉMARD / ÉNARD", "ALREADY_EXISTS", "Alternative names for AINARD (évêque de Tournai). Entry is under AINARD. 'AINARD, aussi nommé AMARD, ANAARD, AYMARD, AYRARD, ÉMARD, ÉNARD'"),
    
    # Page 142
    (142, "ALBUS (Jean)", "CROSS_REF", "Redirects to DE WITTE (Jean). 'ALBUS (Jean), évêque, né à Bruges... Voir DE WITTE (Jean).'"),
    
    # Page 143
    (143, "ALDENARDO (Arn. DE)", "CROSS_REF", "Redirects to WIEMERSCHE (Arn. DE). 'ALDENARDO (Arn. DE), jurisconsulte... Voir WIEMERSCHE (Arn. DE).'"),
    
    # Page 158
    (158, "ALLAUDA / ALAUDA", "CROSS_REF", "Redirects to LEEUWERICK (Eustache). 'ALLAUDA ou ALAUDA, théologien... Voir LEEUWERICK (EUstache).'"),
    
    # Page 160
    (160, "ALSACE (Thomas D')", "FALSE_POSITIVE", "No standalone entry. 'Thierry d'Alsace' is mentioned within narrative text about Flandre history, not as an entry heading."),
    
    # Page 171
    (171, "AMELEN (Jean) / AMELIUS", "CROSS_REF", "Redirects to APPELMANS. 'AMELEN (Jean) ou AMELIUS, architecte... Voir APPELMANS.'"),
    
    # Page 175
    (175, "ANASTASE (Olivier DE SAINT-)", "CROSS_REF", "Redirects to UEUEROCK. 'ANASTASE (Olivier DE SAINT-), prédicateur... Voir UEUEROCK.'"),
    
    # Page 188
    (188, "III", "FALSE_POSITIVE", "Not an entry. Roman numeral 'III' appears in running text about a prophecy: '...III, qui vaincra l'Antéchrist...'"),
    
    # Page 189
    (189, "ANGELIS (Guill. AB)", "CROSS_REF", "Redirects to ENGELEN (Guill. VAN). 'ANGELIS (Guill. AB), professeur, évêque... Voir ENGELEN (Guill. VAN).'"),
    
    # Page 191
    (191, "ANIEN", "CROSS_REF", "Redirects to COUSSERE (Anien). 'ANIEN, abbé d'Oudenbourg, chroniqueur... Voir COUSSERE (Anien).'"),
    (191, "ANNAPES", "CROSS_REF", "Redirects to HANAPES. 'ANNAPES, patriarche de Jérusalem... Voir HANAPES.'"),
    
    # Page 208
    (208, "AUSFRIDUS", "ALREADY_EXISTS", "Alternative name for ANSFRIDE/AUFROI (Saint). Entry is under ANSFRIDE. 'ANSFRIDE ou AUFROI (Saint), AUFRIDUS, AUSFRIDUS, ANSFRIDUS...'"),
    
    # Page 214
    (214, "ANTINES (D. François-Maur D')", "CROSS_REF", "Redirects to DANTINES. 'ANTINES (D. François-Maur D'), historien... Voir DANTINES (B. François-Maur).'"),
    
    # Page 219
    (219, "APS (Jean D')", "CROSS_REF", "Redirects to JEAN D'APS. 'APS (Jean D'), évêque de Liége... Voir JEAN D'APS.'"),
    
    # Page 224
    (224, "ARBORE (Dom. AB)", "CROSS_REF", "Redirects to VANDEN BOOM (Dominique). 'ARBORE (Dom. AB)... Voir VANDEN BOOM (Dominique).'"),
    (224, "ARCHANGELUS TENERAMUNDANUS", "CROSS_REF", "Redirects to HUYLENBROUCK (François). 'ARCHANGELUS TENERAMUNDANUS... Voir HUYLENBROUCK (François).'"),
    (224, "ARCIS (Lambert D')", "CROSS_REF", "Redirects to DARCHIS (Lambert). 'ARCIS (Lambert D')... Voir DARCHIS (Lambert).'"),
    (224, "ARCKEL (Jean D')", "CROSS_REF", "Redirects to JEAN D'ARCKEL. 'ARCKEL (Jean D'), évêque de Liége... Voir JEAN D'ARCKEL.'"),
    
    # Page 288
    (288, "ASPEL (Guillaume VAN)", "CROSS_REF", "Redirects to ABSEL (Guillaume VAN). 'ASPEL (Guillaume VAN)... Voir ABSEL (Guillaume VAN).'"),
    
    # Page 294
    (294, "ASSENEDE (Thierry VAN)", "CROSS_REF", "Redirects to DIEDERICK VAN ASSENEDE. 'ASSENEDE (Thierry VAN)... Voir DIEDERICK VAN ASSENEDE.'"),
    
    # Page 313
    (313, "AUDOMARUS A SANCTO BERTIO", "CROSS_REF", "Redirects to DE SMET. 'AUDOMARUS A SANCTO BERTIO... Voir DE SMET.'"),
    
    # Page 314
    (314, "AUFROI", "CROSS_REF", "Redirects to ANSFRIDE. 'AUFROI, évêque d'Utrecht... Voir ANSFRIDE.'"),
    (314, "AULA (Barthélemy DE)", "CROSS_REF", "Redirects to HOVE (Barthélémy VAN). 'AULA (Barthélemy DE)... Voir HOVE (Barthélémy VAN).'"),
    
    # Page 326
    (326, "AXPOELE ou AXELPOELE (VAN)", "FULL_BIO", "Real biography of artist family in Ghent, XIVe-XVe siècle. Has substantial content about the corporation of painters."),
    
    # Page 340
    (340, "BACCIUS (Martin)", "CROSS_REF", "Redirects to BACK (Martin). 'BACCIUS (Martin), théologien... Voir BACK (Martin).'"),
    (340, "BACHÆRUS (André)", "CROSS_REF", "Redirects to DE BACKER (André). 'BACHÆRUS (André), médecin... Voir DE BACKER (André).'"),
    (340, "BACHERIUS (André-Éloi)", "CROSS_REF", "Redirects to DE BACKER (André-Éloi). 'BACHERIUS (André-Éloi)... Voir DE BÄCKER (André-Éloî).'"),
    (340, "BACHERIUS (Jean-Aug.)", "CROSS_REF", "Redirects to DE BACKER (Jean). 'BACHERIUS (Jean-Aug.)... Voir DE BÄCKER (Jean).'"),
    (340, "BACHERIUS (Josse)", "CROSS_REF", "Redirects to DE BACKER (Josse). 'BACHERIUS (Josse), poëte latin... Voir DE BACKER.'"),
    
    # Page 341
    (341, "BACHERIUS (Pierre)", "CROSS_REF", "Redirects to DE BACKER (Pierre). 'BACHERIUS (Pierre), poëte flamand... Voir DE BACKEK (Pierre).'"),
    
    # Page 346
    (346, "BACQUERE (Benoît)", "CROSS_REF", "Redirects to DEBACQUERE (Benoit). 'BACQUERE (Benoît), poëte... Voir DEBACQUERE (Benoit).'"),
    (346, "BACULETO (Michel DE)", "CROSS_REF", "Redirects to MICHEL DE BACULETO. 'BACULETO (Michel DE)... Voir MICHEL DE BACULETO.'"),
    (346, "BACX (Nicaise)", "CROSS_REF", "Redirects to BAXIUS (Nicaise). 'BACX (Nicaise), grammairien... Voir BAXIUS (Nicaise).'"),
    
    # Page 356
    (356, "BAERSIUS (Henri)", "CROSS_REF", "Redirects to DE BAER (Henri). 'BAERSIUS (Henri), imprimeur... Voir DE BAER (Henri).'"),
    (356, "D E BAER (Henri)", "ALREADY_EXISTS", "The redirect target DE BAER (Henri) - should be extracted under that name if not already."),
    
    # Page 365
    (365, "BAILLEUL (Nicolas DE)", "CROSS_REF", "Redirects to BELLE (Nicolas VAN). 'BAILLEUL (Nicolas DE), architecte... Voir BELLE (Nicolas VAN).'"),
    
    # Page 369
    (369, "BAIUS (Jacques)", "CROSS_REF", "Redirects to BAY (Jacques DE). 'BAIUS (Jacques), professeur... Voir BAY (Jacques DE).'"),
    
    # Page 380
    (380, "COSTERE / PIERKEN (Balten)", "ALREADY_EXISTS", "These are alternative names mentioned within the BALTENS biography. 'BALTEN JANSSONE COSTERE' and 'PIERKEN (Balten) CUSTODIS' are guild register entries within the BALTENS article."),
    
    # Page 400
    (400, "BAREND VAN BRUSSEL", "CROSS_REF", "Redirects to ORLEY (Bernard VAN). 'BAREND VAN BRUSSEL, peintre... Voir ORLEY (Bernard VAN).'"),
    
    # Page 403
    (403, "BARLENUS (Jean)", "CROSS_REF", "Redirects to BAERLE (Jean DE). 'BARLENUS (Jean), écrivain ecclésiastique... Voir BAERLE (Jean DE).'"),
    (403, "BARRAL (Guillaume DE)", "CROSS_REF", "Redirects to GUILLAUME DE BARRAL. 'BARRAL (Guillaume DE), trouvère... Voir GUILLAUME DE BARRAL.'"),
    
    # Page 412
    (412, "BARTIUS (Arn.)", "CROSS_REF", "Redirects to BAERT (Arn.). 'BARTIUS (Arn.), jurisconsulte... Voir BAERT (Arn.).'"),
    (412, "BARTOLLET (Laurent)", "CROSS_REF", "Redirects to BERTHOLET (Laurent). 'BARTOLLET (Laurent), jurisconsulte... Voir BERTHOLET (Laurent).'"),
    
    # Page 413
    (413, "BASILIDES D'ATH", "CROSS_REF", "Redirects to DE LA PLACE (Jean). 'BASILIDES D'ATH, hagiographe... Voir DE LA PLACE (Jean).'"),
]

# Print final table
print(f"{'Page':<6} {'Name':<40} {'Type':<16} Notes")
print("=" * 140)

counts = {"CROSS_REF": 0, "FULL_BIO": 0, "FALSE_POSITIVE": 0, "ALREADY_EXISTS": 0}

for page, name, typ, notes in results:
    counts[typ] += 1
    print(f"{page:<6} {name:<40} {typ:<16} {notes}")

print("\n" + "=" * 140)
print("\nSUMMARY:")
print(f"  CROSS_REF:      {counts['CROSS_REF']} entries (Voir/Voy redirects - should NOT be extracted)")
print(f"  FULL_BIO:       {counts['FULL_BIO']} entries (Real biographies - NEED extraction)")
print(f"  FALSE_POSITIVE: {counts['FALSE_POSITIVE']} entries (Not real entries)")
print(f"  ALREADY_EXISTS: {counts['ALREADY_EXISTS']} entries (Already covered under different name)")
print(f"  TOTAL:          {sum(counts.values())} entries checked")

print("\n\nENTRIES REQUIRING EXTRACTION (FULL_BIO):")
print("-" * 80)
for page, name, typ, notes in results:
    if typ == "FULL_BIO":
        print(f"  Page {page}: {name} - {notes}")

