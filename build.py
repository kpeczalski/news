#!/usr/bin/env python3
"""Facts builder. No AI, no dependencies: counting and fixed rules only.

Every run:
  1. downloads the GDELT 15-minute files not yet processed (English + translated feeds),
  2. groups headlines about the same event by shared words and shared rare names,
  3. compresses each group to the words most outlets share, keeping negations,
  4. ranks groups by distinct wordings (so reprinted wire copy counts once),
  5. writes data.json, the day's archive file and state.json.gz (memory for the next run).

Every rule and threshold a reader might question is a named constant below or a line in rules/.
"""
import calendar, csv, gzip, html, io, json, math, os, re, shutil, ssl, sys, time, zipfile, zlib
import urllib.request, urllib.error
from collections import Counter, defaultdict

BASE = os.environ.get("GDELT_BASE", "https://data.gdeltproject.org/gdeltv2")
COUNTRY_URL = os.environ.get(
    "COUNTRY_URL",
    "https://blog.gdeltproject.org/wp-content/uploads/2021-news-outlets-by-countrycode-2015-2021.csv")
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "site")              # static page files
RULES = os.path.join(HERE, "rules")           # editable blocklists
OUT = os.environ.get("OUT_DIR", os.path.join(HERE, "out"))
STATE_DIR = os.environ.get("STATE_DIR", OUT)  # where the previous run's output lives
NOTE = os.environ.get("NOTE", "")

SLOT = 900                                    # GDELT publishes every 15 minutes
WINDOW = 96                                   # slots kept: 24 h
RANK_WINDOW = WINDOW                          # ranking counts the whole 24 h
NEW_AGE = 12                                  # a story first seen within 3 h goes in the "new" section
REPRINT_WEIGHT = 0.1                          # ten word-for-word reprints count as one report
OTHER_LANG_WEIGHT = 0.5                       # an outlet in another language (matched by names) counts this much
SPREAD_FULL = 4                               # full weight at this many countries' worth of even coverage
SPREAD_FLOOR = 0.25                           # a story carried almost only in one country keeps this share
DOMESTIC_SHARE = 0.6                          # over this share of outlets in the country where it happened...
DOMESTIC_WEIGHT = 0.1                         # ...the story is domestic news and keeps this share
AGENCY_WEIGHT = 0.3                           # a reprint counts this much once the story is carried in 3+ countries
MIN_SPREAD = float(os.environ.get("MIN_SPREAD", "2.5"))   # to be listed: this many countries' worth of even coverage...
MIN_OTHER_LANG = 3                            # ...or this many outlets in other languages
NO_OTHER_LANG = 0.6                           # a story no outlet in another language carries keeps this share
DOMESTIC_KEEP = 50                            # domestic news is listed only if this many outlets in other languages carry it
LIFE_WEIGHT = 0.5                             # a story whose reports mostly tell of deaths counts up to 1.5 times
DEATH_WORDS = set("killed kills kill dead dies died death deaths wounded injured injures casualties massacre".split())
CRISIS_WORDS = set("""war airstrike airstrikes bombing shelling missile missiles drone
drones troops military ceasefire hostages hostage refugees famine siege offensive invasion militants fighting
earthquake flood floods cyclone hurricane typhoon displaced humanitarian genocide gunmen""".split())
CRISIS_SECTION = True
ONGOING_LINES = 4                             # "ongoing": crises covered most over the last days
VIOLENT_DEATH = set("killed kills kill wounded injured casualties massacre".split())   # not "dies"
# Known armed conflicts (from the list of ongoing wars with 1,000+ deaths a year; check it now and
# then). Countries of one conflict count as one crisis: one line, history added together.
CONFLICTS = {
    "Russia–Ukraine war": "RS UP", "Israel and the Palestinian territories": "IS GZ WE", "Iran war": "IR", "Lebanon": "LE",
    "Sudan war": "SU OD", "Myanmar civil war": "BM", "DR Congo conflict": "CG", "Ethiopia conflict": "ET",
    "Somalia conflict": "SO", "Sahel insurgency": "ML UV NG", "Nigeria conflict": "NI", "Yemen war": "YM",
    "Syria conflict": "SY", "Afghanistan and Pakistan insurgencies": "AF PK", "Mexico drug war": "MX",
    "Haiti gang war": "HA", "Colombia conflict": "CO",
}
CONFLICT = {c: name for name, codes in CONFLICTS.items() for c in codes.split()}
BIG_DISASTER_COUNTRIES = 20                   # outside known wars: a disaster or attack the world covers
BIG_EVENT = set("resigns resign resigned dies died arrested ousted sacked quits assassinated impeached".split())
ONGOING_DAYS = 7
ONGOING_STORIES = 4                           # separate crisis stories about one country in a day
ONGOING_MIN = 30                              # outlets over those days, all of a crisis's stories together
PER_COUNTRY = 2                               # at most this many lines about events in one country
PER_REGION = 3                                # and at most this many about one world region
# Regions by GDELT (FIPS) country code; anything not listed counts as "other".
REGIONS = {
    "americas": "US CA MX BR AR CI CO PE VE EC BO UY PA GT HO CS CU DR HA JM".split(),
    "europe": "UK EI FR GM IT SP PO NL BE LU SZ AU DA NO SW FI IC EZ LO PL HU RO BU GR UP RS BO MD LH LG EN HR SI BK MK AL MJ RI".split(),
    "mideast_africa": "IS WE GZ LE SY IZ IR SA AE KU QA BA MU YM JO EG LY TS AG MO SU OD ET SO KE UG TZ RW CG NI GH SF ZI AO SG ML NG".split(),
    "asia_pacific": "CH JA KS KN TW HK IN PK BG CE NP AF ID MY SN RP TH VM BM CB LA AS NZ MG KZ UZ".split(),
}
REGION_OF = {c: r for r, cs in REGIONS.items() for c in cs}
# Spellings that differ between languages and transliterations, folded to one name for matching.
ALIASES = {"kiev": "kyiv", "kiew": "kyiv", "kijev": "kyiv", "peking": "beijing", "bombay": "mumbai",
           "calcutta": "kolkata", "rangoon": "yangon", "burma": "myanmar", "ivory coast": "cote divoire",
           "zelenskiy": "zelensky", "zelenskyy": "zelensky", "selenskyj": "zelensky", "putin wladimir": "vladimir putin",
           "kharkov": "kharkiv", "odessa": "odesa", "gaza strip": "gaza", "north korea": "korea north"}
# Words that tie a person to wrongdoing. A line using one about a named person must say who
# says so, or keep a qualifier ("alleged", "accused", "charged", "denies").
WRONGDOING = set("""spy spying espionage affair fraud corruption corrupt bribe bribery abuse abused assault
harassment rape murder murdered killer theft stole stolen scam embezzlement misconduct lied lying
cheated cheating treason traitor terrorist extremist racist""".split())
ATTRIBUTED = set("""says said say claims claim claimed according alleged allegedly allegation allegations
accused accuses accusation accusations charged charges denies denied suspected reportedly probe
investigation investigated sources""".split())
STATE_BOOST = 1.5                             # affairs of state weigh more than accidents and crime
STATE_WORDS = set("""president presidential minister premier chancellor parliament government election elected
coup impeach sanction tariff ceasefire truce treaty summit envoy talks
strike airstrike missile troops invasion war offensive hostage referendum""".split())
PENDING = 8                                   # slots an unmatched translated article waits for its story
RECENT = 12                                   # numbers come from headlines of the last 3 h
EARLY = 8                                     # stories younger than 2 h are tagged "early"
BOOTSTRAP = int(os.environ.get("BOOTSTRAP_SLOTS", "32"))    # first run looks back 8 h
MAX_CATCHUP = 32
BUDGET = int(os.environ.get("BUDGET_SECONDS", "420"))       # stop taking new slots after this
NEW_LINES = int(os.environ.get("NEW_LINES", "5"))            # lines in "new in the last 3 hours"
DAY_LINES = int(os.environ.get("DAY_LINES", "9"))            # lines in "last 24 hours"
NEW_MIN_SCORE = float(os.environ.get("NEW_MIN_SCORE", "6"))  # a new story needs this much coverage to be listed
DAY_MIN_SCORE = float(os.environ.get("DAY_MIN_SCORE", "12"))  # so does an older one: a short list beats a padded one
COUNTED_MIN_SCORE = float(os.environ.get("COUNTED_MIN_SCORE", "1e9"))  # a line left as counted words: never shown
ONE_LINE = 80                                 # characters that fit on one line of the page
SPARE_LINES = 3                               # extra candidates, in case some get no clear sentence
MIN_OUTLETS = int(os.environ.get("MIN_OUTLETS", "5"))       # outlets needed to appear at all
NAME_MIN = int(os.environ.get("NAME_MIN", "10"))            # wordings needed before a person is named
HEADLINES = int(os.environ.get("HEADLINES", "3"))           # real headlines shown on tap (0 = none)
TITLE_CAP = 300

# Optional sentence writer: a small open-source model running on this computer through Ollama.
# It only rewords; grouping, ranking, numbers and labels stay with the counting rules above, and
# every sentence must pass check_sentence() or the counted line is shown instead.
AI = os.environ.get("AI", "auto")                           # "auto": use it if Ollama is running; "off"
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
AI_MODEL = os.environ.get("AI_MODEL", "")                   # empty: first installed of AI_PREFER
AI_PREFER = ["qwen3:8b", "qwen3:14b", "gemma3:12b", "llama3.1:8b", "mistral:7b", "qwen3:4b", "qwen3:1.7b", "qwen3:0.6b"]
AI_TRIES = int(os.environ.get("AI_TRIES", "4"))             # attempts per story (fewer for slow models)
AI_WORDS = 12                                               # longest sentence accepted
AI_HEADLINES = 8                                            # headlines shown to the model per story
AI_BUDGET = 90                                             # seconds per run spent on sentences
AI_RULES = 27                                                # raise when the prompt or checker changes: retries every line
AI_PROMPT = """You compress news headlines about one event into one plain sentence.
Rules:
- Use only facts, names and numbers that appear in the headlines. Add nothing.
- State the one core fact most headlines agree on, so that a reader with no other news understands
  it: who, what, where, and what it is about (for example "on Ukraine peace talks").
- One clause only. No add-ons starting with "as", "after", "amid", "while" or "and".
- Leave out background, reactions and consequences.
- Write it as subject, verb, object: who did what to whom, in that order, with the right small
  words ("strike on a hospital", not "strike to a hospital"). No "-ing" add-ons such as
  "drawing", "prompting", "sparking", "raising".
- At most 12 words. Sentence case. Present tense. Write numbers as digits.
- No opinion, no judgment words, no speculation, no quotation marks, no outlet names.
- If headlines give different numbers for the same thing, write the range, like 4–5.
- Output the sentence only."""
SHARE = 0.35                                  # a word must be in this share of headlines
HEDGE_SHARE = 0.25
DISPUTE_SHARE = 0.20

# Renowned agencies and public broadcasters, shown first among sources and preferred for a
# fallback headline. Not a ranking input. Overridden by rules/preferred_sources.txt.
PREFERRED = ["nytimes.com", "theguardian.com", "ft.com", "wsj.com", "washingtonpost.com", "economist.com",
             "lemonde.fr", "elpais.com", "spiegel.de", "bloomberg.com", "scmp.com", "thehindu.com",
             "japantimes.co.jp", "straitstimes.com", "hs.fi", "irishtimes.com", "rte.ie", "nos.nl", "dutchnews.nl", "nzz.ch", "corriere.it", "lefigaro.fr", "faz.net", "sueddeutsche.de", "lanacion.com.ar", "elcomercio.pe", "folha.uol.com.br", "eluniversal.com.mx", "theglobeandmail.com", "smh.com.au", "dawn.com", "haaretz.com", "timesofisrael.com", "nation.africa", "dailymaverick.co.za", "premiumtimesng.com", "kyivindependent.com", "themoscowtimes.com", "koreaherald.com", "yna.co.kr", "asahi.com", "mainichi.jp", "bangkokpost.com", "thejakartapost.com", "rappler.com", "reuters.com", "apnews.com", "afp.com",
             "wire.reprint", "bbc.com", "bbc.co.uk", "dw.com", "france24.com", "npr.org", "pbs.org", "yle.fi",
             "cbc.ca", "abc.net.au", "nhk.or.jp", "swissinfo.ch", "euronews.com", "aljazeera.com", "rfi.fr",
             "kyodonews.net"]


def pref_rank(domain):
    """Position of an outlet in the preferred list (lower is better), 999 if not on it."""
    for i, d in enumerate(PREFERRED):
        if domain == d or domain.endswith("." + d):
            return i
    return 999


WIRES = {"reuters": ("Reuters", "reuters.com"), "ap": ("AP", "apnews.com"), "afp": ("AFP", "afp.com")}


def wire_of(url):
    """News-agency copy reprinted on another site, from a folder in its address
    (".../ap/business/...", ".../news_reuters/...", ".../ultime-notizie-reuters/...")."""
    folders = (url.split("//", 1)[-1].split("?")[0].split("/")[1:-1])
    for f in folders:
        for part in re.split(r"[_-]", f.lower()):
            if part in WIRES:
                return WIRES[part]
    return None


def source_rank(domain, url):
    """Preferred-list rank of the outlet, or of the agency whose copy it reprints."""
    w = wire_of(url)
    return min(pref_rank(domain), pref_rank("wire.reprint")) if w else pref_rank(domain)


# Dropped from lines and matching: grammar and newsroom filler. Negations and modal verbs
# (not, no, never, may, could, might) are deliberately NOT here: they change the meaning.
STOP = set("""a an the and or but if then than so of in on at by for from to into onto with within
about above across after against along amid among around as before behind below beneath beside between beyond
during except inside near off out outside over past since through throughout toward towards under until up upon
via is are was were be been being am do does did done has have had having will it its he she they them his her
their our your my we you i this that these those there here who whom whose which what when where why how only
just also still yet more most less least very much many some any each every all both few other another such own
same too again once ever now new news told tells report reports reported according officials official live
update updates breaking watch video photos latest today yesterday tomorrow week amp vs per get gets got make
makes made take takes including others us
monday tuesday wednesday thursday friday saturday sunday january february march april june july august
september october november december jan feb mar apr jun jul aug sep sept oct nov dec th st nd rd""".split())

# Attribution and doubt. Not printed in the line; they set the "claim" tag instead.
HEDGE = set("""says said say saying claims claim claimed alleged allegedly reportedly accused accuses
unconfirmed rumor rumour rumors rumours suspected purported purportedly""".split())
DENIAL = set("denies denied deny rejects rejected refutes refuted disputes disputed".split())
RETRACT = set("correction corrected retracted retraction retracts debunked hoax".split())
SPEECH = set("says said say saying claims claim claimed according".split())      # someone is quoted
QUALIFIER = set("alleged allegedly reportedly suspected purported purportedly unconfirmed".split())
NEGATION = {"not", "never"}
# Attention-seeking words. Never printed, never used for matching, and a model sentence
# containing one is rejected.
FLASH = set("""shocking shock shocks stunning stuns stunned bombshell explosive slams slammed blasts blasted
rips ripped destroys destroyed epic insane unbelievable incredible amazing horrific horrifying terrifying
devastating heartbreaking tragic chaos fury furious outrage outraged meltdown nightmare jaw-dropping
exclusive urgent revealed finally massive huge emotional beloved dramatic iconic heartfelt historic
stunned furious bizarre chilling brutal savage
scandal scandals disgraced disgrace shamed notorious infamous embattled nonsense quietly bluntly rekindles heartwarming""".split())   # verdicts, not facts

NUMWORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
            "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
            "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17", "eighteen": "18",
            "nineteen": "19", "twenty": "20"}
# Tiny fixed lexicon so "8 killed" and "8 dead" count as the same fact.
SYN = {"killed": "dead", "kills": "dead", "kill": "dead", "killing": "dead", "dies": "dead",
       "die": "dead", "died": "dead",
       "hurt": "injured", "wounded": "injured", "injures": "injured", "injuring": "injured",
       "wounds": "injured", "wounding": "injured"}

# Folded for matching only (display keeps the original word).
FOLD = {"children": "child", "people": "person", "men": "man", "women": "woman", "rose": "rise",
        "risen": "rise", "fell": "fall", "fallen": "fall", "percent": "%", "shot": "shoot", "shots": "shoot",
        "shooting": "shoot", "shootings": "shoot"}
# Small words that carry meaning; a model sentence may use one only if the headlines do.
CHECKED = set("against for before after without under over than will may could might not no never".split())
GLUE = {"leaves", "leave", "left", "and"}        # neutral connectors a sentence may add
KILL = {"kill", "kills", "killed", "killing"}
DIE = {"die", "dies", "died"}

GENERIC_TLD = set("com org net info news tv io co me ai app dev biz online site live today world press "
                  "media blog xyz eu int edu gov mil".split())
TLD_COUNTRY = {"uk": "UK", "de": "GM", "fr": "FR", "es": "SP", "it": "IT", "fi": "FI", "se": "SW",
               "no": "NO", "dk": "DA", "nl": "NL", "be": "BE", "ch": "SZ", "at": "AU", "ie": "EI",
               "pt": "PO", "pl": "PL", "cz": "EZ", "gr": "GR", "tr": "TU", "ru": "RS", "ua": "UP",
               "in": "IN", "pk": "PK", "bd": "BG", "cn": "CH", "jp": "JA", "kr": "KS", "au": "AS",
               "nz": "NZ", "ca": "CA", "mx": "MX", "br": "BR", "ar": "AR", "cl": "CI", "za": "SF",
               "ng": "NI", "ke": "KE", "eg": "EG", "il": "IS", "sa": "SA", "ae": "AE", "id": "ID",
               "my": "MY", "sg": "SN", "ph": "RP", "th": "TH", "vn": "VM", "hk": "HK", "tw": "TW",
               "us": "US"}

TOKEN_RE = re.compile(r"\d[\d,]*(?:\.\d+)?%?|[^\W\d_](?:[^\W_]|['’.](?=[^\W_]))*", re.UNICODE)
TITLE_RE = re.compile(r"<PAGE_TITLE>(.*?)</PAGE_TITLE>", re.S)


DIAG = {"rejected": [], "merged": 0}            # facts about the last run, written to diag.json


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ---------- text ----------

def clean_title(t):
    t = html.unescape(html.unescape(t))
    t = re.sub(r"\s+", " ", t).strip()
    if " | " in t:                                   # "Headline | Outlet"
        parts = [p.strip() for p in t.split(" | ")]
        t = parts[0] if len(parts[0].split()) >= 4 else max(parts, key=len)
    t = re.sub(r"^(?:the latest|live|update|breaking|watch|video)\s*:\s*", "", t, flags=re.I)
    for sep in (" - ", " – ", " — ", " : "):         # "Headline - Outlet", "Headline : NPR"
        if sep in t:
            head, tail = t.rsplit(sep, 1)
            if len(tail.split()) <= 4 and len(head.split()) >= 4:
                t = head
    return t.strip()


def slug_title(url):
    """Fallback when a record has no page title: words from the URL's last path segment."""
    path = re.sub(r"[?#].*$", "", url).rstrip("/")
    seg = re.sub(r"\.(html?|php|aspx?)$", "", path.rsplit("/", 1)[-1])
    words = [w for w in re.split(r"[-_]+", seg) if w and not w.isdigit()]
    return " ".join(words) if len(words) >= 4 else ""


def is_num(k):
    return k[:1].isdigit()


def raw_words(title):
    out = []
    for m in TOKEN_RE.finditer(title):
        w = m.group(0).replace("’", "'").lower()
        if w.endswith("n't"):
            out.append("not")
        out.append(w)
    return out


def title_flags(title):
    """(hedged, negated, denied_or_retracted) from fixed word lists."""
    ws = set(raw_words(title))
    return bool(ws & HEDGE), bool(ws & NEGATION), bool(ws & (DENIAL | RETRACT))


def scan(title):
    """Every kept token in order as (raw_index, key, surface). key is for matching, surface for display."""
    letters = [c for c in title if c.isalpha()]
    shouting = bool(letters) and sum(c.isupper() for c in letters) > 0.7 * len(letters)
    out = []
    for i, m in enumerate(TOKEN_RE.finditer(title)):
        w = m.group(0)
        if w[0].isdigit():
            n = w.replace(",", "")
            before = title[m.start() - 1] if m.start() else " "
            after = title[m.end()] if m.end() < len(title) else " "
            label = before.isalpha() or after.isalpha() or (
                before == "-" and m.start() > 1 and title[m.start() - 2].isalpha())
            if label:                                # GLP-1, COVID-19, F-16, G7, 5G: part of a name
                continue
            if not (len(n) == 4 and n.isdigit() and 1900 <= int(n) <= 2100):   # a year is not a fact
                out.append((i, n, n))
            continue
        w = w.replace("’", "'")
        lw = w.lower()
        if lw.endswith("n't"):                       # didn't, won't, isn't -> not
            out.append((i, "not", "not"))
            continue
        if lw.endswith("'s"):
            w = w[:-2]
        w = w.replace(".", "").replace("'", "")
        if not w:
            continue
        if w.isupper() and 2 <= len(w) <= 5 and not shouting:
            out.append((i, w.lower(), w))            # acronym: US, EU, UN, NATO (matched in any case)
            continue
        lw = w.lower()
        if lw in STOP or lw in HEDGE or lw in FLASH or len(lw) < 2:
            continue
        lw = NUMWORDS.get(lw, lw)
        lw = SYN.get(lw, lw)
        key = FOLD.get(lw, lw)
        if len(key) > 4 and key.endswith("s") and not key.endswith(("ss", "us", "is")):
            key = key[:-1]                           # crude plural fold, matching only
        out.append((i, key, lw))
    return out


def tokenise(title):
    """Ordered, de-duplicated list of (key, surface)."""
    out, seen = [], set()
    for _, key, surf in scan(title):
        if key not in seen:
            seen.add(key)
            out.append((key, surf))
    return out


def number_units(title):
    """(number, unit) pairs where the unit word directly follows the number: "8 dead" yes,
    "8 in Brooklyn" no. "5 people shot" counts as (5, shot); "toll rises to 8" as (8, dead)."""
    sc = scan(title)
    raw = [m.group(0).lower() for m in TOKEN_RE.finditer(title)]
    spans = [m.span() for m in TOKEN_RE.finditer(title)]
    toll = any(k == "toll" for _, k, _ in sc)
    out = []
    for j, (i, k, _) in enumerate(sc):
        if not is_num(k):
            continue
        nxt = sc[j + 1] if j + 1 < len(sc) else None
        tight = lambda a, b: not title[spans[a][1]:spans[b][0]].strip()     # only spaces between two tokens
        if nxt and not is_num(nxt[1]) and nxt[0] == i + 1 and tight(i, i + 1):
            if nxt[1] != "person":
                out.append((k, nxt[1]))
                continue
            if j + 2 < len(sc) and sc[j + 2][0] == i + 2 and not is_num(sc[j + 2][1]) and tight(i + 1, i + 2):
                out.append((k, sc[j + 2][1]))
                continue
        if toll and i > 0 and raw[i - 1] in ("to", "at", "reaches", "hits", "tops"):
            out.append((k, "dead"))
            continue
        # "kills 6", "killing at least six", "injures 4": the verb before the number names the unit
        prev = sc[j - 1] if j else None
        if prev and prev[1] in ("dead", "injured") and prev[0] in (i - 1, i - 3):
            gap = title[spans[prev[0]][1]:spans[i][0]]              # nothing but spaces (or "at least") between
            if re.fullmatch(r"\s+(?:at least\s+)?", gap, re.I):
                out.append((k, prev[1]))
    return out


def counted_numbers(text):
    """Numbers a counted line states, as (set of strings, list of (low, high) ranges)."""
    nums, ranges = set(), []
    for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?%?)(?:–(\d[\d,]*(?:\.\d+)?%?))?", text):
        a, b = m.group(1).replace(",", ""), (m.group(2) or "").replace(",", "")
        nums.add(a)
        if b:
            nums.add(b)
            try:
                ranges.append((float(a.rstrip("%")), float(b.rstrip("%"))))
            except ValueError:
                pass
    return nums, ranges


def proper_keys(texts):
    """Keys of words written with a capital in mid-sentence, in texts that are not Title Case."""
    out = set()
    for t in texts:
        ms = [m.group(0) for m in TOKEN_RE.finditer(t)]
        alpha = [w for w in ms if w[0].isalpha()]
        if not alpha or sum(w[0].isupper() for w in alpha) > 0.6 * len(alpha):
            continue
        caps = {i for i, w in enumerate(ms) if i > 0 and w[0].isupper()}
        out.update(k for i, k, _ in scan(t) if i in caps)
    return out


# ---------- rules ----------

def load_rules():
    def lines(name):
        p = os.path.join(RULES, name)
        if not os.path.exists(p):
            return []
        with open(p, encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip() and not l.startswith("#")]
    domains = {d.lower() for d in lines("blocked_domains.txt")}
    preferred = [d.lower() for d in lines("preferred_sources.txt")]
    if preferred:
        PREFERRED[:] = preferred
    pats = lines("blocked_titles.txt")
    title_re = re.compile("|".join("(?:%s)" % p for p in pats), re.I) if pats else None
    return domains, title_re


# ---------- network ----------

_PLAIN_HTTP = set()                    # hosts whose HTTPS certificate failed; public data only


def fetch(url, timeout=90):
    """Bytes, or None when the file does not exist. Other failures raise."""
    host = url.split("/")[2] if "://" in url else ""
    if host in _PLAIN_HTTP and url.startswith("https://"):
        url = "http://" + url[8:]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "facts/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except urllib.error.URLError as e:
        if isinstance(e.reason, FileNotFoundError):
            return None
        if isinstance(e.reason, ssl.SSLError) and url.startswith("https://"):
            # GDELT's download host has at times served a certificate for another name.
            log("certificate problem on", host, "- using plain http for this public data")
            _PLAIN_HTTP.add(host)
            return fetch(url, timeout)
        raise
    except FileNotFoundError:
        return None


def stamp(slot):
    return time.strftime("%Y%m%d%H%M%S", time.gmtime(slot * SLOT))


def iso(slot):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(slot * SLOT))


def latest_slot(name):
    raw = fetch("%s/%s" % (BASE, name))
    if not raw:
        return None
    m = re.search(r"(\d{14})(?:\.translation)?\.gkg\.csv\.zip", raw.decode("utf-8", "replace"))
    if not m:
        return None
    return calendar.timegm(time.strptime(m.group(1), "%Y%m%d%H%M%S")) // SLOT


SPORT_THEME = re.compile(r"SPORT|ATHLET|_PLAYER|FOOTBALL|SOCCER|CRICKET|OLYMPIC", re.I)
CRISIS_THEME = re.compile(r"ARMEDCONFLICT|MILITARY|TERROR|KILL|REFUGEE|HUMANITARIAN|FAMINE|NATURAL_DISASTER|"
                          r"CEASEFIRE|DISPLACED|EPIDEMIC|GENOCIDE|AIRSTRIKE|SIEGE", re.I)
CELEB_THEME = re.compile(r"TAX_FNCACT_(ACTRESS|ACTOR|SINGER|CELEBRIT|MUSICIAN|RAPPER|COMEDIAN|POPSTAR)|ENTERTAINMENT", re.I)


def alias(name):
    return ALIASES.get(name, name)


def entities(f):
    ents = set()
    if SPORT_THEME.search(f[7] or "") or SPORT_THEME.search(f[8] or ""):
        ents.add("T:sport")                           # GDELT's own topic tags mark it as sport
    if CRISIS_THEME.search(f[7] or "") or CRISIS_THEME.search(f[8] or ""):
        ents.add("T:crisis")                          # war, attacks, disasters, famine, refugees
    if re.search(r"(^|;)(KILL|WOUND)#", f[5] or ""):
        ents.add("T:death")                           # GDELT counted people killed or wounded
    if CELEB_THEME.search(f[7] or "") or CELEB_THEME.search(f[8] or ""):
        ents.add("T:celeb")                           # ... or about actors, singers, celebrities
    for p in f[11].split(";")[:15]:
        if p.strip():
            ents.add("P:" + alias(p.strip().lower()))
    for o in f[13].split(";")[:10]:
        if o.strip():
            ents.add("O:" + o.strip().lower())
    for block in f[9].split(";")[:10]:
        parts = block.split("#")
        if len(parts) > 1 and parts[1]:
            name = alias(parts[1].split(",")[0].strip().lower())
            ents.add(("C:" if parts[0] == "1" else "L:") + name)
            if len(parts) > 2 and parts[2].strip():
                ents.add("K:" + parts[2].strip().upper())       # country code of the place
    return ents


def read_gkg(slot, translated, rules, stats):
    """Parse one 15-minute GKG file into article dicts. Missing or broken files give []."""
    blocked_domains, blocked_titles = rules
    url = "%s/%s%s.gkg.csv.zip" % (BASE, stamp(slot), ".translation" if translated else "")
    try:
        raw = fetch(url)
        if not raw:
            return []
        zf = zipfile.ZipFile(io.BytesIO(raw))
        text = zf.read(zf.namelist()[0]).decode("utf-8", "replace")
    except Exception as e:                           # one bad file must not stop the run
        log("skip", url, repr(e))
        return []
    arts = []
    for line in text.split("\n"):
        f = line.split("\t")
        if len(f) < 27:
            continue
        domain = f[3].strip().lower()
        if domain.startswith("www."):
            domain = domain[4:]
        url_ = f[4].strip()
        if not domain or not url_.startswith("http") or domain in blocked_domains:
            continue
        m = TITLE_RE.search(f[26])
        title, slug = (clean_title(m.group(1)) if m else ""), False
        if not translated:
            stats["rows"] += 1
            if title:
                stats["titled"] += 1
            else:
                title, slug = slug_title(url_), True
        if title and blocked_titles and blocked_titles.search(title):
            continue
        codes = Counter(b.split("#")[2].strip().upper() for b in f[9].split(";")
                        if len(b.split("#")) > 2 and b.split("#")[2].strip())
        arts.append({"domain": domain, "url": url_, "title": title, "slug": slug,
                     "cc": codes.most_common(1)[0][0] if codes else "",
                     "ents": entities(f),
                     "toks": tokenise(title) if (title and not translated) else []})
    return arts


def tally_crises(state, arts, slot, weight=1):
    """Per country and day: articles about a war, attack or disaster, and all articles. Feeds the
    "ongoing crises" section, which needs days of history that the stories themselves do not keep."""
    day = time.strftime("%Y-%m-%d", time.gmtime(slot * SLOT))
    tally = state.setdefault("ongoing", {})
    for a in arts:
        if not a.get("cc") or {"T:sport", "T:celeb"} & a["ents"]:
            continue
        row = tally.setdefault(a["cc"], {}).setdefault(day, [0, 0])
        if not isinstance(row, list):                 # (an older format kept one number)
            row = tally[a["cc"]][day] = [0, 0]
        row[1] += weight
        if {"T:crisis", "T:death"} & a["ents"]:
            row[0] += weight


BACKFILL_FILES = 24                           # past files read per run until a week is covered


def backfill(state, latest, rules, started):
    """Once: read every 4th past file of the last 7 days (English only), a few per run, so the
    "ongoing" section has a week of history from the start."""
    nxt = state.get("backfill_next")
    if nxt is None:
        nxt = state["backfill_next"] = latest - 96 * 7
        state["backfill_end"] = latest
    done = 0
    stats = {"rows": 0, "titled": 0}
    while nxt < state["backfill_end"] and done < BACKFILL_FILES and time.time() - started < BUDGET / 2:
        tally_crises(state, read_gkg(nxt, False, rules, stats), nxt, weight=4)
        nxt += 4
        done += 1
    state["backfill_next"] = nxt
    if done:
        log("backfill: read", done, "past files, now at", stamp(nxt))


def load_countries():
    """domain -> country code, from GDELT's outlet lookup. Cached next to the state file.
    Failure is not fatal: the domain-ending fallback in country_of() still works."""
    cache = os.path.join(STATE_DIR, "countries.json.gz")
    if os.path.exists(cache):
        try:
            with gzip.open(cache, "rt", encoding="utf-8") as f:
                data = json.load(f)
            if time.time() - data.get("fetched", 0) < 30 * 86400 and "size" in data:
                return data
        except (OSError, ValueError, EOFError):
            pass
    try:
        raw = fetch(COUNTRY_URL, timeout=120)
        if not raw:
            raise ValueError("lookup not found")
        best, size = {}, Counter()
        for row in csv.reader(io.StringIO(raw.decode("utf-8", "replace"))):
            if len(row) < 3 or not row[2].strip().isdigit():
                continue
            dom, cc, cnt = row[0].strip().lower(), row[1].strip().upper(), int(row[2])
            size[dom] += cnt
            if dom and cc and cnt > best.get(dom, ("", -1))[1]:
                best[dom] = (cc, cnt)
        if len(best) < 100:
            raise ValueError("lookup looks wrong: %d rows" % len(best))
        big = dict(size.most_common(5000))               # the 5,000 largest outlets by articles seen
        return {"fetched": int(time.time()), "map": {d: v[0] for d, v in best.items()}, "size": big}
    except Exception as e:
        log("country lookup unavailable, using domain endings only:", repr(e))
        return {"fetched": 0, "map": {}, "size": {}}


def country_of(domain, cmap):
    parts = domain.split(".")
    for i in range(len(parts) - 1):
        cc = cmap.get(".".join(parts[i:]))
        if cc:
            return cc
    tld = parts[-1]
    if tld in GENERIC_TLD:
        return None
    return TLD_COUNTRY.get(tld, "tld:" + tld)


# ---------- stories ----------

def new_state():
    return {"v": 6, "last": 0, "last_tr": 0, "next": 1, "ndocs": 0, "ndocs_e": 0, "df": {},
            "edf": {}, "stories": {}, "dom": {}, "arts": {}, "ai": {}, "pending": []}


def new_story(slot):
    return {"n": 0, "t": {}, "e": {}, "d": {}, "f": {}, "ti": {}, "first": slot}


def top_tokens(s):
    n = s["n"]
    need = 1 if n < 3 else max(2, math.ceil(0.3 * n))
    items = sorted(((c, t) for t, c in s["t"].items() if c >= need), reverse=True)
    return [t for _, t in items[:12]]


def top_ents(s):
    need = max(2, math.ceil(0.4 * s["n"]))
    items = sorted(((c, e) for e, c in s["e"].items() if c >= need and e[0] in "POL"), reverse=True)
    return [e for _, e in items[:6]]


def add_to_story(s, a, slot):
    """One vote per outlet. A later headline from the same outlet replaces its earlier one,
    so updated figures and corrections reach the line."""
    dom = a["domain"]
    if dom in s["d"]:
        s["d"][dom][1] = slot
        old = s["ti"].get(dom)
        if old and old[0] != a["title"]:
            for k, _ in tokenise(old[0]):
                if s["t"].get(k, 0) > 1:
                    s["t"][k] -= 1
                else:
                    s["t"].pop(k, None)
            for k, _ in a["toks"]:
                s["t"][k] = s["t"].get(k, 0) + 1
            s["ti"][dom] = [a["title"], a["url"], slot, a["slug"]]
        elif old:
            old[2] = slot
        return
    s["f"].pop(dom, None)
    s["n"] += 1
    s["d"][dom] = [slot, slot]
    for k, _ in a["toks"]:
        s["t"][k] = s["t"].get(k, 0) + 1
    for e in a["ents"]:
        s["e"][e] = s["e"].get(e, 0) + 1
    if len(s["ti"]) < TITLE_CAP or pref_rank(dom) < 999:
        s["ti"][dom] = [a["title"], a["url"], slot, a["slug"]]
    if len(s["e"]) > 200:
        s["e"] = {k: c for k, c in s["e"].items() if c > 1}


def rare_entity(state, s, e, also=None, slack=1):
    """A name is evidence that two reports cover one event only if it belongs to this story:
    it must occur here at least as often as in all other articles together. Heads of state
    and capital cities, which turn up everywhere, fail this."""
    own = s["e"].get(e, 0) + (also["e"].get(e, 0) if also else 0)
    return state["edf"].get(e, 0) - own <= max(5, slack * own)


def count_entities(state, arts):
    edf = state["edf"]
    for a in arts:
        for e in a["ents"]:
            edf[e] = edf.get(e, 0) + 1
    state["ndocs_e"] += len(arts)


def cluster_slot(state, arts, slot):
    """Greedy single pass: each English headline joins the best-matching story or starts one."""
    stories, df = state["stories"], state["df"]
    for a in arts:
        for k, _ in a["toks"]:
            df[k] = df.get(k, 0) + 1
    state["ndocs"] += len(arts)
    count_entities(state, arts)
    N = state["ndocs"]

    def w(k):
        return math.log(1 + N / (df.get(k, 0) + 1))

    index, tops, ent_tops = defaultdict(set), {}, {}

    def refresh(sid):
        s = stories[sid]
        tp = top_tokens(s)
        tops[sid] = (set(tp), sum(w(k) for k in tp))
        names = top_ents(s) if s["n"] >= 2 else [e for e in s["e"] if e[0] in "POL"]
        ent_tops[sid] = {e for e in names if rare_entity(state, s, e)}
        for k in tp:
            index[k].add(sid)

    for sid in stories:
        refresh(sid)

    for a in arts:
        T = {k for k, _ in a["toks"]}
        if len(T) < 3:
            continue
        wT = sum(w(k) for k in T)
        E = {e for e in a["ents"] if e[0] in "POL"}
        cand = Counter()
        for k in T:
            ids = index.get(k)
            if ids and len(ids) < 1500:              # a word in 1500 stories identifies nothing
                cand.update(ids)
        best, best_score = None, 0.0
        need = 2 if len(T) <= 4 else 3
        for sid, c in cand.items():
            if c < 2:
                continue
            tp, wtop = tops[sid]
            shared = T & tp
            names = len(E & ent_tops[sid])
            if not wtop or len(shared) < (need if names < 2 else 2):
                continue
            ws = sum(w(k) for k in shared)
            a_cov, s_cov = ws / wT, ws / wtop
            by_words = (a_cov >= 0.4 or s_cov >= 0.45) and min(a_cov, s_cov) >= 0.2
            by_names = names >= 2 and min(a_cov, s_cov) >= 0.15
            if by_words or by_names:
                score = a_cov + s_cov
                if score > best_score:
                    best, best_score = sid, score
        if best is None:
            best = str(state["next"])
            state["next"] += 1
            stories[best] = new_story(slot)
        add_to_story(stories[best], a, slot)
        refresh(best)


def attach_translated(state, arts, slot):
    """Non-English articles have no English headline; they join a story by shared names that
    belong to that story (GDELT supplies names in English). They add to outlet and country
    counts, never to wording. An article whose story is still too small waits and is retried."""
    stories = state["stories"]
    index, tops = defaultdict(set), {}
    for sid, s in stories.items():
        if s["n"] < 3:
            continue
        te = set(top_ents(s))
        if len(te) >= 2 and any(rare_entity(state, s, e, slack=10) for e in te):
            tops[sid] = te
            for e in te:
                index[e].add(sid)
    waiting = state.get("pending", [])
    todo = [(p[0], set(p[1]), p[2]) for p in waiting] + [
        (a["domain"], {e for e in a["ents"] if e[0] in "POL"}, slot) for a in arts]
    state["pending"] = keep = []
    for dom, ents, seen in todo:
        cand = Counter()
        for e in ents:
            cand.update(index.get(e, ()))
        best, best_share = None, 0.0
        for sid, c in cand.items():
            share = c / len(tops[sid])
            # two shared main names, at least one of which belongs to this story
            if c >= 2 and share > best_share and any(
                    rare_entity(state, stories[sid], e, slack=10) for e in ents & tops[sid]):
                best, best_share = sid, share
        if best:
            s = stories[best]
            if dom in s["d"]:
                s["d"][dom][1] = max(s["d"][dom][1], seen)
            elif dom in s["f"]:
                s["f"][dom][1] = max(s["f"][dom][1], seen)
            else:
                s["f"][dom] = [seen, seen]
        elif len(ents) >= 2 and seen > slot - PENDING:
            keep.append([dom, sorted(ents)[:12], seen])


def recount(s, old_n):
    """Bring a story's counters back in line with its current outlets."""
    s["n"] = len(s["d"])
    t = Counter()
    for title, _, _, _ in s["ti"].values():
        for k, _ in tokenise(title):
            t[k] += 1
    scale = s["n"] / len(s["ti"]) if s["ti"] and len(s["ti"]) < s["n"] else 1
    s["t"] = {k: max(1, round(c * scale)) for k, c in t.items()}
    if old_n and s["n"] != old_n:
        s["e"] = {k: v for k, v in ((k, round(c * s["n"] / old_n)) for k, c in s["e"].items()) if v > 0}


def merge_story(a, b):
    total = a["n"] + b["n"]
    for k, c in b["e"].items():
        a["e"][k] = a["e"].get(k, 0) + c
    for src in ("d", "f"):
        for dom, (first, last) in b[src].items():
            cur = a["d"].get(dom) or a["f"].get(dom)
            span = [min(cur[0], first), max(cur[1], last)] if cur else [first, last]
            if src == "d" or dom in a["d"]:          # an English headline outranks a translated match
                a["f"].pop(dom, None)
                a["d"][dom] = span
            else:
                a["f"][dom] = span
    for dom, t in b["ti"].items():
        cur = a["ti"].get(dom)
        if (cur is None and len(a["ti"]) < TITLE_CAP) or (cur is not None and t[2] > cur[2]):
            a["ti"][dom] = t                         # the outlet's newer headline wins
    a["first"] = min(a["first"], b["first"])
    recount(a, total)


def apply_rules(state, rules):
    """Make a changed blocklist take effect at once: drop already-stored headlines (and their
    outlets) that the current rules would ignore."""
    blocked_domains, blocked_titles = rules
    for sid in list(state["stories"]):
        s = state["stories"][sid]
        gone = [d for d, t in s["ti"].items()
                if d in blocked_domains or (blocked_titles and blocked_titles.search(t[0]))]
        gone += [d for d in s["d"] if d in blocked_domains and d not in gone]
        if not gone:
            continue
        old_n = s["n"]
        for d in gone:
            s["ti"].pop(d, None)
            s["d"].pop(d, None)
        if not s["d"]:
            del state["stories"][sid]
        else:
            recount(s, old_n)


def prune(state, now):
    stories = state["stories"]
    for sid in list(stories):
        s = stories[sid]
        s["d"] = {d: v for d, v in s["d"].items() if v[1] > now - WINDOW}
        s["f"] = {d: v for d, v in s["f"].items() if v[1] > now - WINDOW}
        s["ti"] = {d: v for d, v in s["ti"].items() if d in s["d"]}
        if len(s["d"]) != s["n"]:
            recount(s, s["n"])
        if not s["d"] or (len(s["d"]) < 2 and s["first"] < now - 8):
            del stories[sid]
    state["dom"] = {d: v for d, v in state["dom"].items() if v > now - WINDOW}
    state["arts"] = {k: v for k, v in state["arts"].items() if int(k) > now - WINDOW}
    state["pending"] = [p for p in state.get("pending", []) if p[2] > now - PENDING]
    for name, total in (("df", "ndocs"), ("edf", "ndocs_e")):
        if len(state[name]) > 40000:
            state[name] = {k: c for k, c in state[name].items() if c > 2}
        if state[total] > 2_000_000:                 # keep the statistics fresh
            state[total] //= 2
            state[name] = {k: c // 2 for k, c in state[name].items() if c > 1}


# ---------- compression ----------

def names_ok(s, now):
    """A person may be named once the story is carried widely enough: enough differently
    worded reports, or three times that many outlets."""
    return wordings(s, now - WINDOW) >= NAME_MIN or len(s["d"]) >= 3 * NAME_MIN


def has_person(s):
    """True when a person is prominent in the story (named in 30% or more of its reports)."""
    need = max(2, math.ceil(0.3 * s["n"]))
    return any(c >= need for e, c in s["e"].items() if e.startswith("P:"))


def wordings(s, since):
    """Distinct headlines among outlets active since the given slot. Identical wire copy
    reprinted on many sites is one wording."""
    seen = set()
    for dom, t in s["ti"].items():
        if s["d"][dom][1] > since:
            seen.add(tuple(k for k, _ in tokenise(t[0])))
    return len(seen)


def consensus(s, now):
    """Returns (key, text, tags, consensus_keys). The line is the words most outlets share,
    in their usual order, plus numbers; where outlets disagree on a number, the range."""
    entries = [(tokenise(t[0]), t) for t in s["ti"].values()]
    entries = [(tk, t) for tk, t in entries if tk]
    m = len(entries)
    if not m:
        return "", "", [], set()
    df, pos, surf = Counter(), defaultdict(list), defaultdict(Counter)
    for toks, _ in entries:
        L = len(toks)
        for i, (k, sf) in enumerate(toks):
            surf[k][sf] += 1
            if not is_num(k):
                df[k] += 1
                pos[k].append(i / L)

    # Numbers come from recent headlines so that updated tolls replace early ones.
    recent = [e for e in entries if e[1][2] > now - RECENT]
    num_src = recent if len(recent) >= 5 else entries
    groups = defaultdict(list)                        # unit word -> numbers seen directly before it
    for _, t in num_src:
        for n, unit in number_units(t[0]):
            groups[unit].append(n)

    need = max(2, math.ceil(SHARE * m)) if m >= 3 else 1
    words = [k for k, c in df.most_common() if c >= need][:7]
    if len(words) < 3:
        words = [k for k, _ in df.most_common(3)]
    for k in ("not", "no", "never"):                  # a shared negation is never cut for length
        if df[k] >= need and k not in words:
            words.append(k)

    facts, fact_units = [], set()
    for unit, nums in groups.items():
        if len(nums) < max(2, math.ceil(0.25 * len(num_src))):
            continue
        cnt = Counter(nums)
        keep = [n for n, c in cnt.items() if c >= 0.2 * len(nums)] or [cnt.most_common(1)[0][0]]
        try:
            vals = sorted(keep, key=lambda x: float(x.rstrip("%")))
        except ValueError:
            vals = keep
        label = surf[unit].most_common(1)[0][0] if surf.get(unit) else unit
        rng = vals[0] if len(vals) == 1 else "%s–%s" % (vals[0], vals[-1])
        facts.append((sum(pos[unit]) / max(1, len(pos[unit])), "%s %s" % (rng, label)))
        fact_units.add(unit)
        if unit in words:
            words.remove(unit)
    # Order: a word goes before another if it does so in most headlines that contain both.
    before = Counter()
    for toks, _ in entries:
        at = {k: i for i, (k, _) in enumerate(toks)}
        for a in words:
            for b in words:
                if a != b and a in at and b in at and at[a] < at[b]:
                    before[a, b] += 1
    wins = {a: sum((before[a, b] > before[b, a]) - (before[a, b] < before[b, a]) for b in words if b != a)
            for a in words}
    words.sort(key=lambda k: (-wins[k], sum(pos[k]) / len(pos[k])))
    consensus_keys = set(words) | fact_units

    # Tags, from fixed word lists.
    flags = [title_flags(t[0]) for _, t in entries]
    hedged = sum(f[0] for f in flags) / m
    negated = sum(f[1] for f in flags) / m
    denied = sum(f[2] for f in flags) / m
    tags = []
    # A minority of headlines negate what the rest state, or a share carry denial/retraction words.
    if m >= 5 and (DISPUTE_SHARE <= negated < SHARE or denied >= DISPUTE_SHARE):
        tags.append("disputed")
    elif hedged >= HEDGE_SHARE:
        tags.append("claim")
    if s["first"] > now - EARLY:
        tags.append("early")

    # A person is named only once enough independent wordings carry the story.
    need_e = max(2, math.ceil(0.3 * s["n"]))
    if not names_ok(s, now):
        person = set()
        for e, c in s["e"].items():
            if e.startswith("P:") and c >= need_e:
                person.update(k for part in e[2:].split() for k, _ in tokenise(part))
        words = [k for k in words if k not in person]

    # Key: a place most outlets name, else the most shared word.
    key = None
    wordset = set(words)
    for prefix in ("L:", "C:"):
        for e, c in sorted(s["e"].items(), key=lambda x: (-x[1], x[0])):
            if c < need_e or not e.startswith(prefix):
                continue
            parts = [k for p in e[2:].split() for k, _ in tokenise(p)]
            if parts and all(p in wordset for p in parts):
                key = "_".join(surf[p].most_common(1)[0][0] for p in parts)
                words = [k for k in words if k not in parts]
                break
        if key:
            break
    if not key and words:
        k0 = max(words, key=lambda k: (df[k], -words.index(k)))
        key = surf[k0].most_common(1)[0][0]
        words.remove(k0)
    text = " ".join(surf[k].most_common(1)[0][0] for k in words)
    for _, f in sorted(facts):
        text = (text + ", " + f) if text else f
    key = key or ""
    return (key if key.isupper() else key.lower()), text, tags, consensus_keys


OUTLET_SIZE = {}                       # domain -> articles seen by GDELT 2015-2021; filled at run time


# Countries whose press is largely state-controlled: their outlets get no home advantage.
STATE_PRESS = set("CH RS IR KN SA BM VM CU ER TX BO SY AE QA LA EG".split())
LOCAL_BIG = 0.75                              # a local outlet counts as major in the top quarter by size


def sources(s, consensus_keys, local=None, cmap=None):
    """(headlines, links). Renowned outlets from the country where it happened come first (they
    know it best), then the renowned list in order, then major local outlets, then the largest
    outlets; within each, the headlines closest to the shared wording."""
    if local in STATE_PRESS or not cmap:
        local = None
    sizes = sorted(OUTLET_SIZE.values())
    big = sizes[int(LOCAL_BIG * (len(sizes) - 1))] if sizes else 0
    rows, seen_wording = [], set()
    for dom, (title, url, _, slug) in s["ti"].items():
        keys = tuple(k for k, _ in tokenise(title))
        pr = source_rank(dom, url)
        home = bool(local) and country_of(dom, cmap) == local
        tier = 0 if pr < 999 and home else 1 if pr < 999 else 2 if home and OUTLET_SIZE.get(dom, 0) >= big else 3
        rows.append((tier, pr, -(len(consensus_keys & set(keys))), -OUTLET_SIZE.get(dom, 0),
                     dom, title, url, slug, keys))
    rows.sort()
    heads, links = [], []
    for _, _, _, _, dom, title, url, slug, keys in rows:
        if len(heads) < HEADLINES and not slug and keys not in seen_wording:
            seen_wording.add(keys)
            w = wire_of(url)
            heads.append({"t": title, "d": (w[0] + " via " + dom) if w else dom, "u": url})
        elif len(links) < 8:
            links.append({"d": dom, "u": url})
    return heads, links


# ---------- optional sentence writer ----------

def ollama(path, payload=None, timeout=60):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(OLLAMA + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


API_KEY = os.environ.get("LLM_API_KEY", "")                # a free hosted model (Groq); local model if unset or down
API_URL = os.environ.get("LLM_API_URL", "https://api.groq.com/openai/v1")
API_MODELS = os.environ.get("LLM_API_MODEL", "openai/gpt-oss-120b qwen/qwen3.8-27b llama-3.3-70b-versatile").split()
API_STATE = {"local": None, "failed": 0}


def api(path, payload=None, timeout=30):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API_URL + path, data=data, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + API_KEY, "User-Agent": "news/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def pick_model():
    """The hosted model when a key is set and it answers; otherwise the local model, or None."""
    if AI == "off":
        return None
    API_STATE["local"] = local_model()
    if API_KEY:
        try:
            ids = [m.get("id", "") for m in api("/models", timeout=10).get("data", [])]
            for want in API_MODELS:
                if want in ids:
                    return "api:" + want
            log("no hosted model offered of", API_MODELS, "available:", ", ".join(sorted(ids))[:400])
        except Exception as e:
            log("hosted model unavailable:", repr(e)[:200])
    return API_STATE["local"]


def local_model():
    try:
        names = [m.get("name", "") for m in ollama("/api/tags", timeout=5).get("models", [])]
    except Exception:
        return None
    if AI_MODEL:
        return AI_MODEL if AI_MODEL in names else None
    for want in AI_PREFER:
        if want in names:
            return want
    return names[0] if names else None


def write_sentence(model, headlines, extra=""):
    if model and model.startswith("api:"):
        if API_STATE["failed"] < 3:
            try:
                payload = {"model": model[4:], "temperature": 0, "max_tokens": 60,
                           "messages": [{"role": "system", "content": AI_PROMPT + extra},
                                        {"role": "user", "content": "Headlines:\n" + "\n".join("- " + h for h in headlines)}]}
                if "gpt-oss" in model:                    # a reasoning model: think briefly, show only the answer
                    payload.update({"reasoning_effort": "low", "include_reasoning": False, "max_tokens": 600})
                elif "qwen3" in model:
                    payload.update({"reasoning_format": "hidden", "reasoning_effort": "none", "max_tokens": 600})
                out = api("/chat/completions", timeout=30, payload=payload)
                text = ((out.get("choices") or [{}])[0].get("message") or {}).get("content", "")
                API_STATE["answered_by"] = "api"
                return clean_reply(text)
            except Exception as e:
                API_STATE["failed"] += 1                  # rate limit or outage: the local model takes over
                log("hosted model call failed:", repr(e)[:200])
        model = API_STATE["local"]
        if not model:
            return ""
    API_STATE["answered_by"] = "local"
    # Learning from the bigger model: its accepted sentences for the most similar past stories
    # are shown to the small model as worked examples (no training run needed).
    shots = []
    for ex in similar_examples(headlines, 3):
        shots += [{"role": "user", "content": "Headlines:\n" + "\n".join("- " + h for h in ex["h"])},
                  {"role": "assistant", "content": ex["s"]}]
    out = ollama("/api/chat", timeout=40, payload={
        "model": model, "stream": False, "think": False,
        "options": {"temperature": 0, "num_predict": 60},
        "messages": [{"role": "system", "content": AI_PROMPT + extra}] + shots +
                    [{"role": "user", "content": "Headlines:\n" + "\n".join("- " + h for h in headlines)}],
    })
    return clean_reply((out.get("message") or {}).get("content", ""))


EXAMPLES = []                                  # accepted (headlines -> sentence) pairs, kept in state["ex"]
EXAMPLES_MAX = 300


def similar_examples(headlines, k):
    want = {w for h in headlines for w, _ in tokenise(h)}
    scored = []
    for ex in EXAMPLES:
        have = {w for h in ex["h"] for w, _ in tokenise(h)}
        scored.append((len(want & have) / (1 + len(have)), ex))
    scored.sort(key=lambda x: -x[0])
    return [ex for sc, ex in scored[:k] if sc > 0] or [ex for _, ex in scored[:k]]


def remember_example(headlines, sentence, by):
    """Keep a sentence that passed every check, written by the bigger model or printed as a headline."""
    if not sentence or any(ex["s"] == sentence for ex in EXAMPLES):
        return
    EXAMPLES.append({"h": list(headlines[:6]), "s": sentence, "by": by})
    del EXAMPLES[:-EXAMPLES_MAX]


def clean_reply(text):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    text = text.split("\n")[0].strip().strip("\"'“”‘’ ").rstrip(".").strip()
    return re.sub(r"\s+", " ", text)


def stem(k):
    """Light folding so "warns", "warned" and "warning" support each other. Matching only."""
    for end in ("ing", "ed", "es", "s"):
        if len(k) > len(end) + 3 and k.endswith(end) and not k.endswith("ss"):
            return k[:-len(end)]
    return k


CLAUSE = r",\s+|\s(?:as|after|amid|while|and|but|following|if|unless|because|despite|until|drawing|prompting|sparking|raising|triggering|leaving|fuelling|fueling)\s"


def check_sentence(sentence, titles, must_negate, consensus_keys=(), claim=False, counted=None,
                   max_words=None, clauses=True, min_support=None, persons=()):
    """Rule-based gate on a model sentence. Returns "" if it passes, else the reason.
    titles are the story's own headlines. Nothing here trusts the model."""
    if re.search(r"[;:!?]\s|(?<![A-Z])\.\s", sentence) or "\n" in sentence:
        return "more than one sentence"
    words = sentence.split()
    if not 3 <= len(words) <= (max_words or AI_WORDS + (4 if claim else 2)):
        return "length"
    raw = raw_words(sentence)
    if set(raw) & FLASH:
        return "flash word"

    # One fact: an add-on clause must itself be made of the story's shared words.
    cut = re.search(CLAUSE, sentence)
    if consensus_keys and cut and clauses:
        tail = [k for _, k, sf in scan(sentence[cut.end():]) if not is_num(k) and sf not in GLUE]
        if tail and 2 * sum(k in consensus_keys for k in tail) < len(tail):
            return "extra clause"

    # Numbers: only those the counted line states (spelled-out numbers are read as digits).
    if counted is not None:
        nums, ranges = counted_numbers(counted)
        stated = [k for _, k, _ in scan(sentence) if is_num(k)]
        stated += [n.replace(",", "") for n in
                   re.findall(r"(?<![A-Za-z\-])\d[\d,]*(?:\.\d+)?%?(?![A-Za-z])", sentence)]
        for n in stated:
            try:
                v = float(n.rstrip("%"))
            except ValueError:
                v = None
            if n not in nums and not any(v is not None and lo <= v <= hi for lo, hi in ranges):
                return "number not in the counted line: " + n

    # Distinct wordings only: a word must be backed by two differently worded headlines,
    # so one outlier or one mis-grouped headline cannot supply it.
    distinct, seen = [], set()
    for t in titles:
        keys = tuple(k for _, k, _ in scan(t))
        if keys and keys not in seen:
            seen.add(keys)
            distinct.append((t, keys))
    need = min(min_support or 2, len(distinct))
    support = Counter(k for _, keys in distinct for k in {stem(x) for x in keys})
    raw_support = Counter(w for t, _ in distinct for w in set(raw_words(t)))

    sent = [(i, k, sf) for i, k, sf in scan(sentence) if sf not in GLUE]
    keys = [k for _, k, _ in sent]
    if len(set(keys)) < 3:
        return "too little content"
    if consensus_keys and len(set(keys) & set(consensus_keys)) < max(2, math.ceil(0.5 * len(set(consensus_keys)))):
        return "misses the shared words"            # it must carry what the story is about
    extra = [k for k in keys if support[stem(k)] < need]
    if extra:
        return "not in headlines: " + " ".join(extra[:4])
    for w in set(raw) & CHECKED:
        if raw_support[w] < need and not (w == "not" and any(x.endswith("n't") for t, _ in distinct for x in raw_words(t))):
            return "small word not in headlines: " + w
    for n in re.findall(r"(?<![A-Za-z\-])\d[\d,]*(?:\.\d+)?%?(?![A-Za-z])", sentence):   # standalone numbers, years included
        n = n.replace(",", "")
        if sum(1 for t, _ in distinct if n in [x.replace(",", "") for x in re.findall(r"\d[\d,]*(?:\.\d+)?%?", t)]
               or n in [k for _, k, _ in scan(t)]) < need:
            return "number not in headlines: " + n

    # A number must stay with its own word, and be one the headlines commonly give for it.
    pairs = Counter(p for t, _ in distinct for p in set(number_units(t)))
    per_unit = Counter()
    for (n, unit), c in pairs.items():
        per_unit[unit] += c
    for n, unit in number_units(sentence):
        if per_unit[unit] and pairs[n, unit] < max(1, 0.2 * per_unit[unit]):
            return "number moved: %s %s" % (n, unit)
        if not per_unit[unit] and any(u for (m, u) in pairs if m == n):
            return "number moved: %s %s" % (n, unit)

    # Who did what to whom: two words may not appear in an order no headline uses.
    order = Counter()
    for _, tk in distinct:
        at = {}
        for i, k in enumerate(tk):
            at.setdefault(k, i)
        for a in at:
            for b in at:
                if at[a] < at[b]:
                    order[a, b] += 1
    first = {}
    for i, k in enumerate(keys):
        first.setdefault(k, i)
    names = proper_keys([t for t, _ in distinct] + [sentence])
    for a in first:
        for b in first:
            if first[a] < first[b] and a in names and b in names:
                if order[a, b] == 0 and order[b, a] > 0:
                    return "order not in headlines: %s %s" % (a, b)

    rawset = set(raw)
    title_raw = set(w for t, _ in distinct for w in raw_words(t))

    # A named person tied to wrongdoing: the line must say who says so, or keep a qualifier.
    if persons and set(keys) & set(persons) and rawset & WRONGDOING and not rawset & ATTRIBUTED:
        return "unattributed allegation about a person"
    # Job status ("former", "ex") must be what most headlines say, not one outlet's view.
    for w in rawset & {"former", "ex"}:
        if raw_support[w] < max(2, 0.4 * len(distinct)):
            return "status word not common: " + w
    if rawset & DIE and not title_raw & (DIE | {"dead"}):
        return "kill/die changed"
    if rawset & KILL and not title_raw & KILL:
        return "kill/die changed"

    negated = sum(title_flags(t)[1] for t, _ in distinct) / max(1, len(distinct))
    says_not = bool(rawset & (NEGATION | {"no"}))
    if must_negate and not says_not:
        return "dropped a negation"
    if says_not and not must_negate and negated < SHARE:
        return "added a negation"
    # A word the headlines qualify ("alleged affair", "suspected spy") keeps its qualifier.
    qualified = Counter()
    for t, _ in distinct:
        rw = raw_words(t)
        for a, b in zip(rw, rw[1:]):
            if a in QUALIFIER and b not in STOP:
                qualified[b] += 1
    hedging = QUALIFIER | {"allegation", "allegations", "accusation", "accusations", "claims", "reports", "reported"}
    for i, w in enumerate(raw):
        if qualified[w] >= need and not set(raw[max(0, i - 3):i]) & hedging:
            return "dropped a qualifier: " + w

    if claim:
        # A qualifier kept in place ("suspected spy", "alleged affair") marks the claim where it is.
        if any(w in QUALIFIER and i + 1 < len(raw) for i, w in enumerate(raw)):
            return ""
        # Otherwise the source must be named up front (or at the very end) the way headlines name it.
        at = [i for i, w in enumerate(raw) if w in HEDGE or w == "according"]
        if not at:
            return "dropped the attribution"
        if min(at) > 2 and max(at) < len(raw) - 2:
            return "attribution not up front"
        pairs2 = set()
        for t, _ in distinct:
            rw = raw_words(t)
            pairs2.update(zip(rw, rw[1:]))
        pair_need = min(2, len(distinct))               # the same source wording in two headlines
        seen2 = Counter(pr for t, _ in distinct for pr in set(zip(raw_words(t), raw_words(t)[1:])))
        if not any((i > 0 and seen2[raw[i - 1], raw[i]] >= pair_need) or
                   (i + 1 < len(raw) and seen2[raw[i], raw[i + 1]] >= pair_need) for i in at):
            return "attribution not as in headlines"
    return ""


NUM_DISPLAY = {w: d for w, d in NUMWORDS.items() if w != "one"}      # "one" is too often a pronoun


TOLL_RE = re.compile(r"\b(\d[\d,]*)(?:\s*[-–]\s*\d[\d,]*)?\s+(?:[A-Za-z'-]+\s+){0,3}?"
                     r"(dead|killed|deaths|die|died|injured|wounded|hurt|casualties)\b"
                     r"|\b(kills?|killing|injures?|wounds?)\s+(?:at least\s+)?(\d[\d,]*)", re.I)


def toll(titles):
    """(killed, injured) as most headlines that give a number state it: the median of each
    headline's figure, the lower end of a range. (0, 0) when no headline gives one."""
    dead, hurt = [], []
    for t in titles:
        d = h = 0
        for m in TOLL_RE.finditer(digits(t)):
            n = int((m.group(1) or m.group(4)).replace(",", ""))   # group 1 is the lower end of a range
            word = (m.group(2) or m.group(3)).lower()
            if word.startswith(("injur", "wound", "hurt")):
                h = max(h, n)
            else:
                d = max(d, n)
        lows = [int(x.replace(",", "")) for x in re.findall(r"\b(\d[\d,]*)\s*[-–]\s*\d", digits(t))]
        if d and lows:
            d = min(d, min(lows))                      # "43–74 dead": the lower end
        if d:
            dead.append(d)
        if h:
            hurt.append(h)
    med = lambda v: sorted(v)[len(v) // 2] if v else 0
    return med(dead), med(hurt)


def digits(text):
    """Spell numbers as digits for display: "two children and six adults" -> "2 children and 6 adults"."""
    text = re.sub(r"\bU\.S\.(?=\s|$)", "US", text)
    return re.sub(r"\b(%s)\b" % "|".join(NUM_DISPLAY), lambda m: NUM_DISPLAY[m.group(1).lower()], text, flags=re.I)


def common_headline(titles, consensus_keys, claim=False, renowned=None, counted=None, must_negate=False,
                    persons=()):
    """Fallback when no model sentence passes: a real headline that is short and plain and passes
    the same word, number and negation checks as a model sentence. A renowned outlet's headline
    comes first (renowned maps title -> rank); otherwise the one printed by the most outlets."""
    renowned = renowned or {}
    ranked = []
    # Words other headlines print in lower case; used to put a Title Case headline in sentence case.
    low, cap = Counter(), Counter()
    for t in titles:
        ws = t.split()
        if len(ws) >= 4 and not any(len(w) > 3 and w.islower() for w in ws):
            continue                                  # a Title Case headline says nothing about case
        for w in re.findall(r"[A-Za-z][a-z'-]+", " ".join(ws[1:])):
            (cap if w[0].isupper() else low)[w.lower()] += 1
    # A word is lower case when other headlines print it so more often than capitalised mid-sentence
    # ("resigns"); names stay capitalised ("Moscow").
    lower_seen = {w for w in low if low[w] >= cap[w]}
    small = {"a", "an", "the", "of", "in", "on", "at", "to", "for", "by", "with", "from", "over", "into"}
    n_wordings = len({tuple(k for _, k, _ in scan(t)) for t in titles})
    for title, n in Counter(titles).items():
        if n < 2 and title not in renowned and n_wordings < 6:
            continue                                  # in a big story every word is checked against many
        words0 = title.split()
        # Sentence case: a capitalised word that other headlines print in lower case is lowered
        # (Title Case, or a stray capital as in "Russia Claims drone Attack"); names stay.
        title_case = len(words0) >= 4 and not any(len(w) > 3 and w.islower() for w in words0)
        title_sc = " ".join(w if i == 0 or not w[:1].isupper() or w[1:2].isupper()
                            or w.lower().strip(".,'\"") not in (lower_seen | small if title_case else lower_seen)
                            else w.lower() for i, w in enumerate(words0))
        # The headline itself, and its opening up to the first add-on ("... as 3 million expected").
        cut = re.search(CLAUSE, title_sc)
        if cut and set(raw_words(title_sc[cut.end():])) & {"says", "said", "say", "saying", "according",
                                                           "claims", "claim", "reportedly", "report", "reports"}:
            cut = None                                # never cut off who says the main clause
        # (an allegation in the add-on itself, "... amid alleged affair", may be cut off whole)
        for text in {title_sc, title_sc[:cut.start()].strip() if cut else title_sc}:
            words = text.split()
            alpha = [w for w in words if w[:1].isalpha()]
            if not 4 <= len(words) <= AI_WORDS + 2 or re.search(r"[?!:;|]", text):
                continue
            if claim and not set(raw_words(text)) & (HEDGE | {"according", "reports", "report"}) \
                    and not (text != title_sc and set(raw_words(title_sc[len(text):])) & HEDGE):
                continue                              # a claim is shown with its attribution, or cut off whole
            if len(alpha) >= 4 and not any(len(w) > 3 and w.islower() for w in alpha):
                continue                              # Title Case Reads As Shouting (no plain word left)
            named = {k for _, k, _ in scan(text)} & set(consensus_keys)
            if len(named) < 2 or (consensus_keys and 3 * len(named) < 2 * len(set(consensus_keys))):
                continue                              # it must say what most headlines say
            # Carrying at least half of the story's shared words is enough; then shorter is better,
            # which trims agency add-ons ("..., related events in Shenzhen").
            enough = len(named) >= max(2, math.ceil(0.5 * len(set(consensus_keys))))
            fits = len(text) <= ONE_LINE                 # fits on one line of the page
            rw = set(raw_words(text))
            accuses = bool(set(persons) & rw and rw & WRONGDOING)   # a named person tied to wrongdoing
            amid = bool(re.search(r"\bamid\b", text, re.I))   # background added to the event
            ranked.append(((not accuses, not amid, enough, fits, -renowned.get(title, 999), title_sc == title, n, -len(words)), text, title))
    # In a story with many wordings every word needs a second headline behind it (this drops
    # colour such as "his second home"); a story with few wordings has too little to compare.
    # Every word of a real headline must be common in the story: in two differently worded headlines,
    # and in at least 15% of them in a big story, so one outlet's colour ("scandal", "worldwide") is dropped.
    support = 1 if n_wordings < 6 else min(6, max(2, math.ceil(0.15 * n_wordings)))
    printed = Counter(titles)
    for _, text, source in sorted(ranked, reverse=True):
        plain = text.rstrip(".")
        # A headline that a third of the outlets print word for word IS what most outlets say.
        need = 1 if printed[source] >= max(3, len(titles) / 3) else support
        if not check_sentence(plain, titles, must_negate, consensus_keys, False, counted,
                              max_words=AI_WORDS + 2, clauses=False, min_support=need, persons=persons):
            return plain
    return ""


def supported_words(titles, limit=24):
    """Content words that at least two differently worded headlines share, most shared first.
    Given to the model as its vocabulary when its own wording keeps failing the checks."""
    seen, count, surface = set(), Counter(), {}
    for t in titles:
        sc = scan(t)
        keys = tuple(k for _, k, _ in sc)
        if not keys or keys in seen:
            continue
        seen.add(keys)
        for _, k, sf in sc:
            surface.setdefault(stem(k), sf)
        count.update({stem(k) for k in keys})
    return [surface[k] for k, c in count.most_common(limit) if c >= 2 and not is_num(k)]


def add_sentences(state, lines, picks, started):
    """Attach a checked model sentence to each line. Cached per story until its counted line changes."""
    model = pick_model()
    EXAMPLES[:] = state.setdefault("ex", [])
    cache = state.setdefault("ai", {})
    live = {l["id"] for l in lines}
    for sid in [k for k in cache if k not in live and k not in state["stories"]]:
        del cache[sid]
    used = 0
    for l in lines:
        titles, shown, name_ok, ckeys, renowned, persons = picks[l["id"]]
        claim, disputed = "claim" in l["tags"], "disputed" in l["tags"]
        sig = "%d|%s|%s|%s|%s|%d" % (AI_RULES, model, l["key"], l["text"], ",".join(l["tags"]),
                                  zlib.crc32("\n".join(sorted(shown)).encode()))
        negate0 = bool({"not", "never", "no"} & set((l["key"] + " " + l["text"]).split()))
        # Pick, don't write: a real headline that passes every check is used as printed, and the
        # model is asked only when none does (a small model invents words; a headline cannot).
        picked = common_headline(titles, ckeys, claim, renowned, l["text"], negate0, persons)
        if picked and not name_ok and set(raw_words(picked)) & set(persons):
            picked = ""                               # a small story names no person
        if picked and disputed and not set(raw_words(picked)) & DENIAL:
            picked = ""                               # a disputed story is shown with its denial
        if True:
            if picked:
                l["sentence"], l["by"] = picked, "headline"
                remember_example(shown, picked, "headline")
                cache.pop(l["id"], None)
                if set(raw_words(picked)) & HEDGE and "claim" not in l["tags"]:
                    l["tags"].insert(0, "claim")
                l["sentence"] = digits(picked)
                # No "Reports:" here: a claim's headline keeps its attribution, or was cut before the claim.
                l["show_tags"] = [t for t in l["tags"] if t != "claim"]
                continue
        hit = cache.get(l["id"])
        if hit and hit["sig"] != sig and hit["s"] and name_ok and not disputed and \
                not check_sentence(hit["s"], titles, negate0, ckeys, claim, l["text"], persons=persons):
            hit["sig"] = sig                           # the accepted sentence still holds: keep it
        if hit and hit["sig"] == sig:
            l["sentence"] = hit["s"]
        elif (model and name_ok and not disputed and len(shown) >= 2
              and time.time() - started < AI_BUDGET):
            must_negate = bool({"not", "never", "no"} & set((l["key"] + " " + l["text"]).split()))
            hints = ["", "\n- Copy wording from the headlines; do not use any word that is not in them."
                         "\n- Shorter: at most 10 words, one clause, no semicolon.",
                     "\n- At most 12 words. Apart from small connecting words, use only these words: "
                     + ", ".join(supported_words(titles)) + ". Include: " + ", ".join(sorted(ckeys)) + ".",
                     "\n- Write it as: who + what + where + about what. At most 12 words. Use these words: "
                     + ", ".join(sorted(ckeys)) + "."]
            if claim:
                hedges = Counter(w for t in shown for w in raw_words(t) if w in HEDGE)
                word = hedges.most_common(1)[0][0] if hedges else "says"
                hints = [h + "\n- Most headlines attribute this to a source. Start with who says it, exactly as a "
                         "headline does, using the word \"%s\" (for example: Police say ...)." % word for h in hints]
            sentence, why = "", ""
            try:
                top = Counter(titles).most_common(1)[0][0] if titles else ""
                for n_try, extra in enumerate(hints[:AI_TRIES]):
                    heads = shown
                    if n_try == 1 and top:            # second try: shorten the most printed headline
                        heads = [top]
                        extra += ("\n- There is one headline. Shorten it to at most 12 words, keeping its "
                                  "own words and its attribution.")
                    if why == "misses the shared words":
                        extra += "\n- Your last answer left out what the story is about. Include these words: %s." \
                            % ", ".join(sorted(ckeys))
                    if why in ("length", "extra clause"):
                        extra += ("\n- Your last answer was too long. Use at most 12 words and a single clause: "
                                  "drop details, keep who, what, where and what it is about.")
                    if why.startswith(("not in headlines: ", "small word not in headlines: ", "number")) and ": " in why:
                        extra += "\n- Do not use: %s." % why.split(": ", 1)[1].replace(" ", ", ")
                    sentence = write_sentence(model, heads, extra)
                    why = check_sentence(sentence, titles, must_negate, ckeys, claim, l["text"], persons=persons)
                    cut = re.search(CLAUSE, sentence)
                    if why and cut:                    # the core before an add-on may pass by itself
                        head = sentence[:cut.start()].strip()
                        if not check_sentence(head, titles, must_negate, ckeys, claim, l["text"], persons=persons):
                            sentence, why = head, ""
                    if not why:
                        break
            except Exception as e:
                log("sentence writer unavailable:", repr(e))
                model = None
                l["sentence"] = ""
                continue
            if why:
                log("sentence rejected (%s): %s" % (why, sentence))
                DIAG["rejected"].append({"why": why, "sentence": sentence, "line": l["key"] + ": " + l["text"]})
                sentence = ""
            cache[l["id"]] = {"sig": sig, "s": sentence}
            if sentence and API_STATE.get("answered_by") == "api":
                remember_example(shown, sentence, "big model")
            l["sentence"] = sentence
        else:
            l["sentence"] = ""
        l["by"] = "model" if l["sentence"] else ""
        used += bool(l["sentence"])
        if not l["sentence"] and name_ok and not disputed:
            negate = bool({"not", "never", "no"} & set((l["key"] + " " + l["text"]).split()))
            l["sentence"] = common_headline(titles, ckeys, claim, renowned, l["text"], negate, persons)
            l["by"] = "headline" if l["sentence"] else ""
        if l["sentence"]:
            if set(raw_words(l["sentence"])) & HEDGE and "claim" not in l["tags"]:
                l["tags"].insert(0, "claim")           # wording that hedges is labelled as a claim
            l["sentence"] = digits(l["sentence"])
        # Attribution is handled one way: the line itself says who is speaking, or opens with
        # "Reports:". The side label is kept only for lines shown as counted words.
        hedged_in_line = set(raw_words(l["sentence"] or "")) & (SPEECH | QUALIFIER | {"allegation", "allegations"})
        if l["sentence"] and "claim" in l["tags"] and not hedged_in_line:
            l["sentence"] = "Reports: " + l["sentence"]
        l["show_tags"] = [t for t in l["tags"] if not (t == "claim" and l["sentence"])]
    state["ex"] = list(EXAMPLES)
    return {"model": model or "", "sentences": used, "examples": len(EXAMPLES)}


def render(state, now, cmap, built):
    stories = state["stories"]

    def members(s):
        m = dict(s["f"])
        m.update(s["d"])
        return m

    def countries(s):
        return len({c for c in (country_of(d, cmap) for d in members(s)) if c})

    def country_votes(s):
        """Votes per country. Each differently worded report has one vote, shared between the
        countries of the outlets that print it, so one agency text reprinted by 70 papers in one
        country is one vote, not 70. An outlet in another language has one vote."""
        groups = defaultdict(list)
        for dom in s["d"]:
            t = s["ti"].get(dom)
            groups[tuple(k for k, _ in tokenise(t[0])) if t else ("?", dom)].append(dom)
        votes = Counter()
        for doms in groups.values():
            known = [c for c in (country_of(d, cmap) for d in doms) if c]
            for c in known:
                votes[c] += 1.0 / len(known)
        for dom in s["f"]:
            c = country_of(dom, cmap)
            if c:
                votes[c] += 1.0
        return votes

    def spread_of(s):
        """Effective number of countries: 1 when nearly all reports come from one country, higher
        the more evenly they are shared (inverse of the sum of squared shares)."""
        by = country_votes(s)
        total = sum(by.values())
        return total * total / sum(n * n for n in by.values()) if total else 0.0

    def domestic(s):
        """True when the event happened in one country and most outlets reporting it are there."""
        codes = [(c, e[2:]) for e, c in s["e"].items() if e.startswith("K:")]
        if not codes:
            return False
        c, code = max(codes)
        if c < 0.5 * s["n"]:
            return False
        # Domestic if the home country dominates either the outlets or the differently worded reports.
        outlets = Counter(x for x in (country_of(d, cmap) for d in members(s)) if x)
        for by in (outlets, country_votes(s)):
            total = sum(by.values())
            if total > 0 and by.get(code, 0) / total > DOMESTIC_SHARE:
                return True
        return False

    def score(s):
        """Differently worded reports count 1 each, word-for-word reprints REPRINT_WEIGHT each,
        outlets in other languages OTHER_LANG_WEIGHT each; the sum is scaled down for stories
        carried mostly in a single country, and again for domestic news."""
        since = now - RANK_WINDOW
        w = wordings(s, since)
        english = sum(1 for v in s["d"].values() if v[1] > since)
        other = sum(1 for v in s["f"].values() if v[1] > since)
        spread = max(SPREAD_FLOOR, min(1.0, spread_of(s) / SPREAD_FULL))
        if domestic(s):
            spread *= DOMESTIC_WEIGHT
        c = countries(s)
        reprint = AGENCY_WEIGHT if c >= 3 else REPRINT_WEIGHT
        boost = STATE_BOOST if STATE_WORDS & {FOLD.get(k, k) for k in top_tokens(s)} else 1.0
        if cmap and not other:
            boost *= NO_OTHER_LANG
        boost *= 1 + LIFE_WEIGHT * min(1.0, share(s, "T:death", VIOLENT_DEATH | {"dead", "deaths"}) / 0.5)
        return ((w + reprint * max(0, english - w) + OTHER_LANG_WEIGHT * other) * spread * boost,
                c, len(members(s)))

    def share(s, tag, words):
        """Share of a story's reports with a GDELT tag, or (for older data) whose headline uses the words."""
        tagged = s["e"].get(tag, 0) / max(1, s["n"])
        titles = [t[0] for t in s["ti"].values()]
        worded = sum(1 for t in titles if set(raw_words(t)) & words) / max(1, len(titles))
        return max(tagged, worded)

    def headline_share(s, words):
        titles = [t[0] for t in s["ti"].values()]
        return sum(1 for t in titles if set(raw_words(t)) & words) / max(1, len(titles))

    def is_crisis(s):
        """War, attack or disaster, by the story's own headlines: these go to the crises section.
        Speeches about a crisis ("... calls it genocide") are not events and stay in the main list."""
        return CRISIS_SECTION and headline_share(s, CRISIS_WORDS | VIOLENT_DEATH) >= 0.4 \
            and headline_share(s, {"calls", "urges", "accuses", "condemns", "slams", "warns", "vows"}) < 0.4

    def event_country(s):
        codes = [(c, e[2:]) for e, c in s["e"].items() if e.startswith("K:")]
        if not codes:
            return None
        c, code = max(codes)
        return code if c >= 0.5 * s["n"] else None

    def worldwide_enough(s):
        """Listed only with an international footprint. Skipped when no country data is loaded."""
        if not cmap or MIN_SPREAD <= 0:
            return True
        return spread_of(s) >= MIN_SPREAD or len(s["f"]) >= MIN_OTHER_LANG

    def same_affair(small, big, big_names):
        """A smaller story belongs to a bigger one when it carries two of the bigger story's three
        main names and those names belong to the pair: either both are uncommon elsewhere, or one
        of them occurs in these two stories more than everywhere else together (a place such as
        "Logan Circle" next to a common one such as "Washington")."""
        shared = set(top_ents(small)) & big_names
        if not shared:
            return False
        if len(shared) >= 2 and (sum(1 for e in shared if rare_entity(state, small, e, big, slack=3)) >= 2
                                 or any(rare_entity(state, small, e, big) for e in shared)):
            return True
        if not any(rare_entity(state, small, e, big, slack=10) for e in shared):
            return False                          # a name found everywhere (EU, a capital) links nothing
        # A big event spreads its names over so many reports that none looks rare. Then a shared
        # main name plus two shared distinctive words ("nvidia", "huang"; "microsoft", "outage") is enough.
        # A word is distinctive here when at least a fifth of all its uses are in these two stories.
        rare_words = {k for k in set(top_tokens(small)[:8]) & set(top_tokens(big)[:8])
                      if not is_num(k) and state["df"].get(k, 0) <= 5 * (small["t"].get(k, 0) + big["t"].get(k, 0))}
        # Words that only repeat the shared names ("nvidia", "gaza") prove nothing about the event.
        name_words = {k for e in set(top_ents(small)) | big_names for p in e[2:].split() for k, _ in tokenise(p)}
        event_words = rare_words - name_words
        if len(event_words) >= 2:
            return True
        # Or two shared names plus one such word ("Microsoft" + "Exchange Online" + "outage").
        return len(shared) >= 2 and bool(event_words)

    def same_event(a, b):
        ta, tb = set(top_tokens(a)), set(top_tokens(b))
        if not ta or not tb:
            return False
        inter = len(ta & tb)
        if inter >= 3 and inter / len(ta | tb) >= 0.5:
            return True
        ea, eb = set(top_ents(a)), set(top_ents(b))
        shared, small = ea & eb, min(len(ea), len(eb))
        if not (small < 2 or inter < 2 or len(shared) < max(2, math.ceil(0.5 * small))):
            # Two names that belong to these stories, or four shared names and three shared words.
            if (sum(1 for e in shared if rare_entity(state, a, e, b)) >= 2
                    or (len(shared) >= 4 and inter >= 3)):
                return True
        return same_affair(b, a, set(top_ents(a)[:3]))      # fragments of one big event

    # Cheap pre-rank by size, then fold fragments of one event among the leaders, then exact rank.
    pre = sorted(stories, key=lambda sid: -len(stories[sid]["d"]))[:150]
    by_token = defaultdict(set)
    for sid, st in stories.items():
        if len(st["d"]) >= 2:
            for k in top_tokens(st):
                by_token[k].add(sid)
    for a in pre:
        if a not in stories:
            continue
        near = Counter()
        for k in top_tokens(stories[a]):
            near.update(by_token[k])
        for b, c in near.most_common(60):
            if c < 2:
                break
            if b != a and b in stories and len(stories[b]["d"]) <= len(stories[a]["d"]) \
                    and same_event(stories[a], stories[b]):
                DIAG["merged"] += 1
                merge_story(stories[a], stories[b])
                del stories[b]
    ranked = sorted((sid for sid in pre if sid in stories),
                    key=lambda sid: tuple(-x for x in score(stories[sid])))

    # Two sections that do not overlap: stories that began within the last 3 hours, and the
    # biggest stories of the last 24 hours that began earlier. Both are ranked the same way.
    # Stories kept off the page as domestic or not international enough; their fragments
    # (the same event reprinted elsewhere under other wording) stay off too.
    held = [(stories[sid], set(top_ents(stories[sid])[:3])) for sid in pre
            if sid in stories and len(stories[sid]["d"]) >= MIN_OUTLETS
            and (domestic(stories[sid]) or not worldwide_enough(stories[sid]))]
    lines, picks, shown_stories = [], {}, []
    room = {"new": NEW_LINES + SPARE_LINES, "day": DAY_LINES + SPARE_LINES}
    per_country, per_region = Counter(), Counter()
    def skip(s, why):
        if len(DIAG.setdefault("skipped", [])) < 40:
            DIAG["skipped"].append({"why": why, "score": round(score(s)[0], 1), "n": len(s["d"]),
                                    "where": event_country(s), "names": top_ents(s)[:3]})
    def make_line(sid, s, mem, section, where):
        key, text, tags, ckeys = consensus(s, now)
        if not key:
            return None
        if cmap and "claim" in tags and not s["f"]:
            return None                                  # a remark nobody abroad picked up is not an event
        heads, links = sources(s, ckeys, where, cmap)
        all_titles = [t[0] for t in s["ti"].values() if not t[3]]
        renowned = {}
        for dom, t in s["ti"].items():
            r = source_rank(dom, t[1])
            if r < 999 and not t[3]:
                renowned[t[0]] = min(r, renowned.get(t[0], 999))
        shown, seen_w = [], set()
        for t in sorted(all_titles, key=lambda t: (renowned.get(t, 999) == 999,
                                                   -len(ckeys & {k for k, _ in tokenise(t)}))):
            w = tuple(k for k, _ in tokenise(t))
            if w not in seen_w and len(shown) < AI_HEADLINES:
                seen_w.add(w)
                shown.append(t)
        # A small story gets a sentence only if it is not about a person (see names_ok).
        need_p = max(2, math.ceil(0.2 * s["n"]))
        persons = {k for e, c in s["e"].items() if e.startswith("P:") and c >= need_p
                   for part in e[2:].split() for k, _ in tokenise(part)}
        # A named person who resigns, dies, is arrested or ousted: shown as fact only when two papers of
        # record carry it; otherwise the line is marked a claim ("Reports: ...").
        if persons and set(raw_words(key + " " + text)) & BIG_EVENT and \
                len({d for d in s["ti"] if source_rank(d, s["ti"][d][1]) < pref_rank("reuters.com")}) < 2 \
                and "claim" not in tags:
            tags.insert(0, "claim")
        picks[sid] = (all_titles, shown, names_ok(s, now) or not has_person(s), ckeys, renowned, persons)
        firsts = [v[0] for v in mem.values()]
        line = {
            "id": sid, "section": section, "key": key, "text": text, "tags": tags, "related": 0,
            "score": round(score(s)[0], 1),
            "outlets": len(mem),
            "wordings": wordings(s, now - RANK_WINDOW),
            "countries": countries(s),
            "other_lang": len(s["f"]),
            "new_hour": sum(1 for v in firsts if v > now - 4),
            "prev_hour": sum(1 for v in firsts if now - 8 < v <= now - 4),
            "spark": [sum(1 for v in firsts if v == now - 11 + i) for i in range(12)],
            "first": iso(s["first"]),
            "headlines": heads, "links": links, "_where": where,
        }
        return line

    for sid in ranked:
        s = stories[sid]
        mem = members(s)
        if len(mem) < MIN_OUTLETS:
            continue
        section = "new" if s["first"] > now - NEW_AGE else "day"
        if score(s)[0] < (NEW_MIN_SCORE if section == "new" else DAY_MIN_SCORE):
            skip(s, "small"); continue  # too small to list
        if not worldwide_enough(s):
            skip(s, "not worldwide"); continue
        if is_crisis(s):
            skip(s, "crises section"); continue
        if s["e"].get("T:celeb", 0) >= 0.4 * max(1, s["n"]):
            skip(s, "celebrity"); continue
        if s["e"].get("T:sport", 0) >= 0.3 * max(1, s["n"]):
            skip(s, "sport"); continue  # sport, by GDELT's topic tags
        if cmap and domestic(s) and len(s["f"]) < DOMESTIC_KEEP:
            skip(s, "domestic"); continue  # domestic news, unless the world's press carries it
        where = event_country(s)
        if where and per_country[where] >= PER_COUNTRY + 1:
            skip(s, "country cap"); continue  # no single country fills the page
        region = REGION_OF.get(where or "", "other")
        if region != "other" and per_region[region] >= PER_REGION + 2:
            skip(s, "region cap"); continue  # nor a single world region
        if not room[section]:
            if not any(room.values()):
                break
            continue
        # One line per event: a story that carries two of the three main names of a line already
        # on the page is a follow-up or reaction, and is counted under that line instead.
        # Names found mostly elsewhere (heads of state, capitals) do not count.
        ents = set(top_ents(s))
        parent = next((l for l, ps, pe in shown_stories if same_affair(s, ps, pe)), None)
        if parent is not None:
            parent["related"] += 1
            skip(s, "follow-up"); continue
        if any(hs is not s and len(hs["d"]) > len(s["d"]) and same_affair(s, hs, he) for hs, he in held):
            skip(s, "fragment of held"); continue
        line = make_line(sid, s, mem, section, where)
        if line is None:
            continue
        lines.append(line)
        shown_stories.append((lines[-1], s, set(top_ents(s)[:3])))    # the event's three main names
        room[section] -= 1
        if where:
            per_country[where] += 1
            per_region[REGION_OF.get(where, "other")] += 1
    # Ongoing crises: a war or disaster is covered every day, but in many small stories that never top
    # the day's list. Their coverage is added up by country over the last days; the biggest crises not
    # already on the page get a line with their largest story of the day.
    today = time.strftime("%Y-%m-%d", time.gmtime(now * SLOT))
    tally = state.setdefault("ongoing", {})
    crisis_today = {}
    for sid, s in stories.items():
        where = event_country(s)
        if not where or not is_crisis(s) or s["e"].get("T:sport", 0) >= 0.3 * s["n"] \
                or s["e"].get("T:celeb", 0) >= 0.4 * s["n"] or len(members(s)) < MIN_OUTLETS:
            continue
        crisis_today.setdefault(CONFLICT.get(where, where), []).append((score(s)[0], sid, len(members(s))))
    keep = {time.strftime("%Y-%m-%d", time.gmtime((now - 96 * d) * SLOT)) for d in range(ONGOING_DAYS)}
    for where in list(tally):
        tally[where] = {d: v for d, v in tally[where].items() if d in keep and isinstance(v, list)}
        if not tally[where]:
            del tally[where]
    # Crises section: wars, attacks and disasters, one line per country (its biggest story today).
    # Ordered by today's story, raised by up to double for a crisis covered on many days of the week
    # and making up a large share of what is written about that country.
    n_days = len({d for days in tally.values() for d in days if days[d][0]})
    shown_ids = {l["id"] for l in lines}
    crises = []
    for w, items in crisis_today.items():
        d = Counter()
        for code, days in tally.items():
            if CONFLICT.get(code, code) == w:
                for day, v in days.items():
                    d[day] = [d[day][0] + v[0], d[day][1] + v[1]] if day in d else list(v)
        crisis, total = sum(v[0] for v in d.values()), sum(v[1] for v in d.values())
        days_on = sum(1 for v in d.values() if v[0] >= 8)
        ongoing = min(1.0, days_on / ONGOING_DAYS) * min(1.0, 3 * crisis / max(1, total))
        # Within a crisis, the event with the highest human toll; among equal tolls, the most covered.
        def rank(item):
            st = stories[item[1]]
            return toll([t[0] for t in st["ti"].values()]) + (item[0],)
        best, sid, _ = max((it for it in items if it[0] >= 4), key=rank, default=(0, None, 0))
        if sid is None or (not worldwide_enough(stories[sid]) and days_on < 3):
            continue                                  # a local accident is not a world crisis
        if w not in CONFLICTS and countries(stories[sid]) < BIG_DISASTER_COUNTRIES:
            continue                                  # outside known wars, only what the world covers
        k, h = toll([t[0] for t in stories[sid]["ti"].values()])
        # A toll most headlines attribute to someone ("military says") is a party's claim: it counts half,
        # so announcing the biggest number does not put a side on top.
        if headline_share(stories[sid], SPEECH) >= 0.5:
            k, h = k / 2, h / 2
        crises.append(((k, h, stories[sid]["first"]), sid, w, days_on))
    # Human toll first (people killed, then injured, as the headlines state it); then the latest.
    crises.sort(reverse=True)
    added = 0
    for _, sid, where, days_on in crises:
        if added >= ONGOING_LINES + SPARE_LINES:
            break
        if sid in shown_ids:
            continue
        s = stories[sid]
        line = make_line(sid, s, members(s), "ongoing", where)
        if line:
            line["covered_days"] = days_on
            line["toll"] = list(toll([t[0] for t in s["ti"].values()]))
            lines.append(line)
            added += 1
    lines.sort(key=lambda l: {"new": 0, "day": 1, "ongoing": 2}[l["section"]])   # order within a section kept
    ai = add_sentences(state, lines, picks, time.time())
    # Counted words are hard to read; a small story that got no sentence is left out.
    DIAG.setdefault("skipped", []).extend({"why": "no clear sentence", "score": l["score"], "line": l["key"] + ": " + l["text"]}
                                          for l in lines if not l["sentence"])
    lines = [l for l in lines if l["sentence"] or l["score"] >= COUNTED_MIN_SCORE]
    cap = {"new": NEW_LINES, "day": DAY_LINES, "ongoing": ONGOING_LINES}
    kept, per_country, per_region = [], Counter(), Counter()
    for l in lines:                         # spares fill only gaps; caps count lines actually shown
        where = l.pop("_where", None)
        region = REGION_OF.get(where or "", "other")
        if not cap[l["section"]] or (where and per_country[where] >= PER_COUNTRY) \
                or (region != "other" and per_region[region] >= PER_REGION):
            continue
        cap[l["section"]] -= 1
        kept.append(l)
        if where:
            per_country[where] += 1
            per_region[region] += 1
    lines = kept
    # Within "most covered", the order the reader can check: most countries first (which stories make
    # the page still uses the full score).
    lines = [l for l in lines if l["section"] == "new"] + \
        sorted([l for l in lines if l["section"] == "day"], key=lambda l: -l["countries"]) + \
        [l for l in lines if l["section"] == "ongoing"]
    return {
        "v": 4,
        "ai": ai,
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(built)),
        "data_until": iso(now),
        "day": time.strftime("%Y-%m-%d", time.gmtime(now * SLOT)),
        "history_hours": min(24, round((now - min([int(k) for k in state["arts"]] or [now]) + 1) / 4)),
        "ongoing_days": n_days,
        "screened": {"outlets": len(state["dom"]), "articles": sum(state["arts"].values())},
        "note": NOTE,
        "lines": lines,
    }


# ---------- run ----------

def load_state():
    """Previous state, or None on a genuine first run. A state file that exists but cannot be
    read stops the run: publishing an empty site over a working one is worse than a late update."""
    p = os.path.join(STATE_DIR, "state.json.gz")
    if not os.path.exists(p):
        return None
    if os.environ.get("RESET") == "1":
        log("RESET=1: ignoring previous state")
        return None
    try:
        with gzip.open(p, "rt", encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError, EOFError) as e:
        if os.environ.get("SELF_HEAL") == "1":       # local runner: set the damaged file aside and start over
            log("previous state is unreadable (%r): set aside, starting over" % e)
            try:
                os.replace(p, p + ".bad")
            except OSError:
                pass
            return None
        raise SystemExit("previous state is unreadable (%r). Re-run with RESET=1 to start over." % e)
    if st.get("v") != 6:
        log("state from an older version: starting over")
        return None
    return st


def replace(tmp, path):
    """os.replace, retried: on Windows it fails while the web server is reading the file."""
    for attempt in range(10):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 9:
                raise
            time.sleep(0.3)


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    replace(tmp, path)


def main():
    started = time.time()
    DIAG.clear()
    DIAG.update({"rejected": [], "merged": 0})
    state = load_state()
    rules = load_rules()
    latest = latest_slot("lastupdate.txt")
    if latest is None:
        raise SystemExit("cannot read GDELT lastupdate.txt")
    try:
        latest_tr = latest_slot("lastupdate-translation.txt")
    except Exception as e:
        log("translation feed pointer unavailable:", repr(e))
        latest_tr = None

    if state is None:
        log("first run: looking back", BOOTSTRAP, "slots")
        state = new_state()
        state["last"] = state["last_tr"] = latest - BOOTSTRAP
    state["last"] = max(state["last"], latest - MAX_CATCHUP)
    state["last_tr"] = max(state["last_tr"], latest - MAX_CATCHUP)
    if latest_tr is None:
        latest_tr = state["last_tr"]                 # nothing new known; try again next run

    apply_rules(state, rules)
    stats = {"rows": 0, "titled": 0}
    for slot in range(min(state["last"], state["last_tr"]) + 1, max(latest, latest_tr) + 1):
        if time.time() - started > BUDGET:
            log("time budget reached; the rest waits for the next run")
            break
        n_en = n_tr = 0
        if state["last"] < slot <= latest:
            en = read_gkg(slot, False, rules, stats)
            if slot >= state.get("backfill_end", 0):
                tally_crises(state, en, slot)
            cluster_slot(state, en, slot)
            for a in en:
                state["dom"][a["domain"]] = slot
            state["last"], n_en = slot, len(en)
        if state["last_tr"] < slot <= latest_tr:
            tr = read_gkg(slot, True, rules, stats)
            if slot >= state.get("backfill_end", 0):
                tally_crises(state, tr, slot)
            attach_translated(state, tr, slot)
            for a in tr:
                state["dom"][a["domain"]] = slot
            state["last_tr"], n_tr = slot, len(tr)
        state["arts"][str(slot)] = state["arts"].get(str(slot), 0) + n_en + n_tr
        log(stamp(slot), "english", n_en, "translated", n_tr, "stories", len(state["stories"]))

    if os.environ.get("BACKFILL", "1") == "1":
        backfill(state, latest, rules, started)

    # Canary: if GDELT changes its format, stop before publishing nonsense.
    if stats["rows"] > 500 and stats["titled"] < 0.3 * stats["rows"]:
        raise SystemExit("only %d of %d records had a page title: format change? Nothing published."
                         % (stats["titled"], stats["rows"]))

    now = state["last"]
    prune(state, now)
    cdata = load_countries()
    OUTLET_SIZE.clear()
    OUTLET_SIZE.update(cdata.get("size", {}))
    data = render(state, now, cdata["map"], time.time())

    os.makedirs(OUT, exist_ok=True)
    if os.path.isdir(SRC):
        shutil.copytree(SRC, OUT, dirs_exist_ok=True)
    if os.path.isdir(RULES):
        shutil.copytree(RULES, os.path.join(OUT, "rules"), dirs_exist_ok=True)
    arch = os.path.join(OUT, "archive")
    os.makedirs(arch, exist_ok=True)
    old = os.path.join(STATE_DIR, "archive")
    if os.path.isdir(old) and os.path.abspath(old) != os.path.abspath(arch):
        shutil.copytree(old, arch, dirs_exist_ok=True)
    write_json(os.path.join(arch, data["day"] + ".json"), data)
    days = sorted(f[:-5] for f in os.listdir(arch) if re.fullmatch(r"\d{4}-\d\d-\d\d\.json", f))
    write_json(os.path.join(arch, "index.json"), days)
    write_json(os.path.join(OUT, "data.json"), data)
    if cdata["map"]:
        with gzip.open(os.path.join(OUT, "countries.json.gz"), "wt", encoding="utf-8") as f:
            json.dump(cdata, f, separators=(",", ":"))
    with gzip.open(os.path.join(OUT, "state.json.gz.tmp"), "wt", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, separators=(",", ":"))
    replace(os.path.join(OUT, "state.json.gz.tmp"), os.path.join(OUT, "state.json.gz"))
    sizes = sorted((len(st["d"]) for st in state["stories"].values()), reverse=True)
    # The examples, as a training set for fine-tuning the small model later.
    with open(os.path.join(OUT, "examples.jsonl"), "w", encoding="utf-8") as f:
        for ex in state.get("ex", []):
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    write_json(os.path.join(OUT, "diag.json"), {
        "built": data["updated"], "seconds": round(time.time() - started, 1),
        "last": iso(state["last"]), "last_translated": iso(state["last_tr"]),
        "english_records": stats["rows"], "with_title": stats["titled"],
        "stories": len(sizes), "stories_5plus": sum(1 for x in sizes if x >= 5), "largest": sizes[:10],
        "stories_with_translated": sum(1 for st in state["stories"].values() if st["f"]),
        "merged_this_run": DIAG["merged"], "ai": data["ai"], "rejected": DIAG["rejected"][-20:], "skipped": DIAG.get("skipped", []),
        "lines": [{"section": l["section"], "score": l["score"], "outlets": l["outlets"], "wordings": l["wordings"],
                   "other_lang": l["other_lang"], "tags": l["tags"], "counted": l["key"] + ": " + l["text"],
                   "sentence": l["sentence"]} for l in data["lines"]],
    })
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    log("wrote", len(data["lines"]), "lines in %.0fs" % (time.time() - started))


if __name__ == "__main__":
    main()
