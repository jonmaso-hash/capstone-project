"""
A US jurisdiction derived from a profile's free-text `geography`.

Its own module rather than part of `filed.py`, because a state code is not a
Filed concept: USAspending disambiguates recipients by location too, and SEC
submissions carry `stateOrCountry`. One table, one parser.

WHAT IT IS FOR. Search context -- narrowing a fuzzy nationwide query, and
enabling the officer reverse lookup, which returns zero rows without a state.

WHAT IT IS NOT. A statement about where a business is legally registered, and
never identity authority. A profile saying Atlanta may belong to a Delaware
corporation; the detail record's own `state` and `meta.source` say where it is
registered, and the existing nationwide-name -> exact candidate -> detail path
still decides whether a returned entity is the subject at all.

Both Entity Integrity subjects already carry `geography`, which is already the
profile's location authority: it is in the field-visibility defaults, in
`DIRECTORY_DISCLOSING_FIELDS` and in the match vectors. Adding a second
location field would have created two authorities for one fact and a new
onboarding input, for a measured gain of one record in eleven.

ONLY THE LAST COMMA-SEPARATED SEGMENT IS CONSIDERED, and it must match a code
or a full state name exactly. Scanning for any two-letter token would read OR
out of "Portland or Seattle" and IN out of "moved in 2024" -- both are real
state codes and ordinary English words. Returning None is always preferable to
a confident wrong jurisdiction: a miss falls back to the nationwide search that
already works, while a wrong state searches a register the company was never
in and reports what it finds there.
"""
import re

US_STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut',
    'DE': 'Delaware', 'DC': 'District of Columbia', 'FL': 'Florida',
    'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois',
    'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky',
    'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota',
    'MS': 'Mississippi', 'MO': 'Missouri', 'MT': 'Montana',
    'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire',
    'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania',
    'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota',
    'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming',
}

_NAME_TO_CODE = {name.lower(): code for code, name in US_STATES.items()}


def state_from_geography(text):
    """
    A two-letter US state code, or None when the text does not name one.

    None is a first-class answer, not a failure: 'san diego' names no state,
    and inferring California from the city would be a guess presented as a
    jurisdiction.
    """
    if not text:
        return None
    segments = [part.strip() for part in str(text).split(',') if part.strip()]
    if not segments:
        return None
    last = re.sub(r'\s+', ' ', segments[-1])
    # A code before a name. DEFENSIVE, not load-bearing: no US state name is
    # two letters, so a segment can match a code or a name but never both,
    # and a mutation swapping the order changed no observable behaviour.
    if len(last) == 2 and last.upper() in US_STATES:
        return last.upper()
    return _NAME_TO_CODE.get(last.lower())
