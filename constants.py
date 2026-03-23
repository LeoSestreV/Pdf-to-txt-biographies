PYMUPDF_BOLD_BIT = 1 << 4
PYMUPDF_ITALIC_BIT = 1 << 1

UC = r'A-ZÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖÙÚÛÜÝÞ'

DESCRIPTORS = frozenset({
    'abbé', 'abbesse', 'administrateur', 'agronome', 'amiral', 'ancien',
    'annaliste', 'antiquaire', 'apôtre', 'architecte', 'archéologue',
    'archidiacre', 'archiduchesse', 'archevêque', 'arrière',
    'artisan', 'artiste', 'artistes', 'astronome', 'auteur',
    'baron', 'baronne', 'bienfaiteur', 'bienheureux', 'biographe',
    'bourgmestre', 'bourgeois', 'bénédictin', 'belge',
    'calligraphe', 'calligraphes', 'capitaine', 'cardinal', 'cartographe',
    'célèbre', 'chanoine', 'chantre', 'chapelain', 'chef', 'chevalier',
    'chirurgien', 'chroniqueur', 'chronologiste', 'coadjuteur', 'colonel',
    'combattant', 'commerçant', 'commandant', 'commandeur', 'commentateur',
    'compilateur', 'compositeur', 'comte', 'comtesse', 'confesseur',
    'conseiller', 'constructeur', 'consul', 'controversiste', 'coseigneur',
    'curé',
    'dame', 'dessinateur', 'diacre', 'diplomate', 'directeur', 'docteur',
    'dominicain', 'dont', 'doyen', 'duc', 'duchesse', 'décédé', 'défenseur',
    'ecclésiastique', 'empereur', 'enseigna', 'envoyé', 'ermite',
    'escrimeur', 'est', 'ethnologue', 'exploitant',
    'évêque', 'écolâtre', 'écrivain', 'érudit', 'époux', 'épouse', 'était',
    'facteur', 'famille', 'feld', 'feldmaréchal', 'femme', 'fils',
    'financier', 'fille', 'florissait', 'fondateur', 'fondatrice', 'forme',
    'frère', 'fut',
    'gardien', 'gentilhomme', 'gouverneur', 'grammairien', 'graveur',
    'greffier', 'guerrier', 'général', 'géographe', 'géologue',
    'hagiographe', 'helléniste', 'héraldiste', 'historien', 'homme',
    'humaniste', 'hébraïsant',
    'il', 'imprimeur', 'industriel', 'infante', 'infant', 'ingénieur',
    'instituteur',
    'jésuite', 'jurisconsulte', 'juriste',
    'lazariste', 'lecteur', 'libraire', 'licencié', 'littérateur',
    'lieutenant', 'luthiste',
    'magistrat', 'major', 'marchand', 'marquis', 'maréchal',
    'mathématicien', 'maître', 'membre', 'militaire', 'minéralogiste',
    'ministre', 'missionnaire', 'moine', 'moraliste', 'musicien',
    'mère', 'médecin', 'ménestrel',
    'naquit', 'natif', 'native', 'navigateur', 'neveu', 'noble', 'nommé',
    'notaire', 'né', 'née', 'négociateur', 'numismate',
    'officier', 'on', 'organiste', 'orientaliste', 'ornithologue',
    'parti', 'partit', 'patriarche', 'patriote', 'patron',
    'peintre', 'peintres', 'père', 'près',
    'personnage', 'philologue', 'philosophe', 'physicien', 'plus',
    'poète', 'poëte', 'poétesse', 'prédicateur', 'prélat', 'président',
    'prêtre',
    'prince', 'princesse', 'prieur', 'procureur', 'professeur',
    'protonotaire', 'prévôt', 'publiciste',
    'recteur', 'religieux', 'religieuse', 'roi', 'reine', 'récollet',
    'savant', 'sculpteur', 'secrétaire', 'seigneur', 'sénateur', 'sire',
    'soldat', 'souveraine', 'souverain', 'statuaire', 'succéda',
    'successivement', 'surnommé',
    'théologien', 'théoricien', 'topographe', 'trouvère',
    'vicaire', 'village', 'vit', 'vivait', 'voyageur',
    'premier', 'première', 'deuxième', 'troisième', 'quatrième',
    'cinquième', 'sixième', 'septième', 'huitième', 'neuvième',
    'dixième', 'onzième', 'douzième', 'treizième', 'quatorzième',
    'quinzième', 'seizième', 'dix-septième', 'dix-huitième',
    'dix-neuvième', 'vingtième', 'vingt', 'trentième', 'trente',
    'quarantième', 'quarante', 'cinquantième', 'cinquante',
    'soixantième', 'soixante',
})

NAME_PARTICLES = frozenset({
    'DE', 'DU', 'DES', 'LE', 'LA', 'LES', 'VAN', 'DEN', 'DER',
    'VANDER', 'VANDEN', 'OU', 'ET', 'D', 'VON', 'VER', 'TER',
})

NAME_LINKS = frozenset({
    'ou', 'dit', 'dite', 'surnommé', 'nommé', 'appelé', 'appelée',
})

FRAGMENT_STARTERS = frozenset({
    'Il', 'Elle', 'Son', 'Sa', 'Ses', 'Les', 'Le', 'La', 'Un', 'Une',
    'Ce', 'Cette', 'Ces', 'On', 'Nous', 'Des', 'Du', 'En', 'Au',
    'Après', 'Avant', 'Dans', 'Sous', 'Sur', 'Par', 'Pour', 'Avec',
    'Parmi', 'Selon',
})

BLACKLISTED_STARTS = frozenset({
    'IDEM', 'DOMINUS', 'FEBRUARII', 'ITEM', 'ANNO', 'OBIIT',
    'HIC', 'LIBER', 'HUJUS', 'DIXIT', 'QUI', 'QUOD',
    'BIBLIOGRAPHIE', 'BIBLIOTHECA', 'BIBLIOTHÈQUE',
})

LATIN_FRAGMENT_WORDS = frozenset({
    'INCLYTA', 'GESTA', 'CECINIT', 'TRIUMPHOS', 'NATURASI', 'MORES',
    'MYSTICA', 'VERBA', 'DEI', 'ARTES', 'DEPINGENS', 'MILITIAMQUE',
    'POLI', 'ELOQUII', 'PICTOR', 'HORUM', 'CENSOR', 'CYTIIARISTA',
    'PYERIDUM', 'PIDEI', 'ERAT', 'REQUIES', 'ANIMÆ', 'COELESTI',
    'DETUR', 'ARCE', 'EXOPTAT', 'ROGITES', 'LECTOR', 'AMICE', 'DEUM',
    'EGREGIE', 'SCRIBENS', 'PLANXIT', 'DOCUIT', 'CULTOR', 'CUBAT',
    'ALANUS', 'DOCTOR', 'QUEM', 'DECET', 'ALMUS', 'HONOR',
})

LATIN_INDICATORS = frozenset({
    'ET', 'QUI', 'QUOD', 'HIC', 'EST', 'FUIT', 'OBIIT',
    'ANNO', 'DOMINI', 'JACET', 'CUBAT', 'HUJUS', 'POST',
    'DIXIT', 'PONDUS', 'DOCUIT', 'CULTOR', 'FILIT',
    'SEDE', 'USQUE', 'ANNUM', 'VIXIT', 'MORTUUS', 'PACE',
    'AMEN', 'LEGIS', 'NON', 'SANCTA', 'QUIESCAT',
    'ARTIS', 'DECUS', 'DECANUS', 'QUEM', 'PICTOR',
    'ALUIT', 'LUGET', 'NATUS', 'AETAT', 'SUÆ',
})

STANDALONE_PARTICLES = frozenset({
    'VAN', 'DE', 'DU', 'DES', 'LE', 'LA', 'LES', 'DEN', 'DER',
})

SPACED_PARTICLES = [
    (r'\bD E S\b', 'DES'), (r'\bD E N\b', 'DEN'), (r'\bD E R\b', 'DER'),
    (r'\bV A N\b', 'VAN'), (r'\bV O N\b', 'VON'), (r'\bL E S\b', 'LES'),
    (r'\bD E\b', 'DE'), (r'\bD U\b', 'DU'),
    (r'\bL E\b', 'LE'), (r'\bL A\b', 'LA'),
]

TRAILING_PATTERNS = [
    r',?\s+dont\s+.*$',
    r',?\s+communément\s*$',
    r',?\s+mais\s*$',
    r',?\s+Belge\s+de\s+naissance\s*$',
    r",?\s+chroni\w*,?\s+qui\b.*$",
    r",?\s+'\s*$",
    r',?\s+aussi\b.*$',
]

FRENCH_STOP_WORDS = frozenset({
    'ou', 'et', 'de', 'du', 'des', 'le', 'la', 'les', 'en', 'a', 'y',
})

NAME_CONTINUATION_PAIRS = frozenset({
    'ou le', 'ou la', 'ou les', 'ou l', 'dit le', 'dit la',
    'dite la', 'dite le', 'nommé le', 'nommé la',
})

GREEK_TO_LATIN = {
    'Α': 'A', 'Β': 'B', 'Ε': 'E', 'Ζ': 'Z', 'Η': 'H',
    'Ι': 'I', 'Κ': 'K', 'Μ': 'M', 'Ν': 'N', 'Ο': 'O',
    'Ρ': 'P', 'Τ': 'T', 'Υ': 'Y', 'Χ': 'X',
}


def build_word_sets(cfg):
    return {
        'descriptors': DESCRIPTORS | frozenset(cfg.extra_descriptors),
        'blacklisted': BLACKLISTED_STARTS | frozenset(cfg.extra_blacklisted_starts),
        'fragment_starters': FRAGMENT_STARTERS | frozenset(cfg.extra_fragment_starters),
        'latin_fragments': LATIN_FRAGMENT_WORDS | frozenset(cfg.extra_latin_fragments),
        'latin_indicators': LATIN_INDICATORS | frozenset(cfg.extra_latin_indicators),
    }
