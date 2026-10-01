"""
Content detection: language, category, fingerprint, and crypto address extraction.
Includes LRU classification caching by fingerprint for high-throughput scraping.
"""
from collections import OrderedDict
import hashlib
import re
import threading
from bs4 import BeautifulSoup

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE58_REGEX = re.compile(r"\b[13][1-9A-HJ-NP-Za-km-z]{25,34}\b")
BECH32_REGEX = re.compile(r"\bbc1[ac-hj-np-z02-9]{38,60}\b", re.IGNORECASE)


def decode_base58(s):
    """Decode a Base58 string to bytes with leading zeros preserved."""
    n = 0
    for char in s:
        n = n * 58 + BASE58_ALPHABET.index(char)
    res = []
    while n > 0:
        res.append(n & 0xFF)
        n >>= 8
    res = bytes(reversed(res))
    num_zeros = len(s) - len(s.lstrip("1"))
    return b"\x00" * num_zeros + res


def is_valid_base58_address(addr):
    """Validate a legacy/P2SH Bitcoin address using Base58Check checksum."""
    if not (26 <= len(addr) <= 35) or addr[0] not in ("1", "3"):
        return False
    try:
        raw = decode_base58(addr)
        if len(raw) != 25:
            return False
        payload = raw[:-4]
        checksum = raw[-4:]
        h1 = hashlib.sha256(payload).digest()
        h2 = hashlib.sha256(h1).digest()
        return h2[:4] == checksum
    except Exception:
        return False


def is_valid_bech32_address(addr):
    """Validate Bech32 Bitcoin address format and character set."""
    addr_lower = addr.lower()
    if not addr_lower.startswith("bc1"):
        return False
    if not (42 <= len(addr_lower) <= 62):
        return False
    allowed = set("qpzry9x8gf2tvdw0s3jn54khce6mua7l")
    payload = addr_lower[3:]
    return all(c in allowed for c in payload)


def validate_bitcoin_address(addr):
    """Check if address is a valid Bitcoin address (Base58Check or Bech32)."""
    if addr.startswith("1") or addr.startswith("3"):
        return is_valid_base58_address(addr)
    if addr.lower().startswith("bc1"):
        return is_valid_bech32_address(addr)
    return False


def extract_bitcoin_addresses(text, validate_checksum=True):
    """
    Extract Bitcoin addresses from text.
    Filters out invalid Base58 characters (0, O, I, l) and optionally verifies checksums.
    """
    candidates = set()
    for m in BASE58_REGEX.findall(text):
        candidates.add(m)
    for m in BECH32_REGEX.findall(text):
        candidates.add(m.lower())

    if not validate_checksum:
        return list(candidates)

    valid_addrs = []
    for addr in candidates:
        if validate_bitcoin_address(addr):
            valid_addrs.append(addr)
    return valid_addrs


def detect_language(text, html_lang_attr=""):
    """
    Fast and accurate language detection.
    1. HTML lang attribute fast-path.
    2. Heuristic frequency score.
    3. Langdetect only called when ambiguous.
    """
    if html_lang_attr:
        l = html_lang_attr.lower().strip()[:2]
        if l in ("hu", "en", "de", "fr", "es", "ru", "it", "pl", "ro", "sk", "cs"):
            return l

    t = text.lower()
    hu_diacritics = len(re.findall(r"[áéíóöőúüű]", t))
    ru_letters = len(re.findall(r"[а-яё]", t))

    # Fast-path for Russian
    if ru_letters > 10:
        return "ru"

    # Fast-path for Hungarian
    hu_words = t.count(" a ") + t.count(" az ") + t.count(" és ") + t.count(" hogy ")
    hu_score = (hu_words + hu_diacritics) * 1.5
    if hu_diacritics >= 3 or hu_score >= 8:
        return "hu"

    en_score = (
        t.count(" the ")
        + t.count(" and ")
        + t.count(" of ")
        + t.count(" to ")
        + t.count(" is ")
    )
    de_score = (
        t.count(" und ")
        + t.count(" der ")
        + t.count(" die ")
        + t.count(" das ")
        + t.count(" ist ")
    )
    fr_score = (
        t.count(" le ")
        + t.count(" la ")
        + t.count(" et ")
        + t.count(" des ")
        + t.count(" du ")
    )

    scores = {
        "hu": hu_score,
        "en": en_score,
        "de": de_score,
        "fr": fr_score,
        "ru": ru_letters * 2,
    }

    best = max(scores, key=scores.get)
    sorted_scores = sorted(scores.values(), reverse=True)

    # If top heuristic has high confidence over second place, return immediately
    if sorted_scores[0] >= 5 and (sorted_scores[0] - sorted_scores[1] >= 3):
        return best

    # Fallback to langdetect only if ambiguous
    try:
        from langdetect import detect as ld_detect

        lang = ld_detect(text[:2000])
        if len(lang) == 2:
            return lang.lower()
    except Exception:
        pass

    if scores[best] < 3:
        return "en"
    return best


def detect_category(title, text, soup=None):
    """
    Weighted category classification based on title, content, meta tags, and HTML structure.
    Avoids false positives (e.g. solitary 'post' word no longer flags forum).
    """
    meta_text = ""
    has_post_form = False
    has_cart = False

    if soup is not None:
        # Check meta keywords & description
        for meta in soup.find_all("meta"):
            name = meta.get("name", "").lower()
            prop = meta.get("property", "").lower()
            if name in ("keywords", "description") or prop in (
                "og:description",
                "og:title",
            ):
                meta_text += " " + meta.get("content", "")

        # Check structural elements
        for form in soup.find_all("form"):
            form_text = str(form).lower()
            if "comment" in form_text or "reply" in form_text or "message" in form_text:
                has_post_form = True
            if "cart" in form_text or "checkout" in form_text or "buy" in form_text:
                has_cart = True

    combined = (title + " " + meta_text + " " + text[:2500]).lower()

    weights = {
        "forum": 0,
        "wiki": 0,
        "library": 0,
        "news": 0,
        "market": 0,
    }

    # Forum indicators (weighted phrases)
    forum_strong = [
        "forum",
        "board index",
        "phpbb",
        "discussions",
        "subforum",
        "threads",
        "bulletin board",
    ]
    forum_medium = ["thread", "topic", "reply to thread", "posts:", "registered user"]
    for w in forum_strong:
        if w in combined:
            weights["forum"] += 4
    for w in forum_medium:
        if w in combined:
            weights["forum"] += 2
    if has_post_form:
        weights["forum"] += 3

    # Wiki indicators
    wiki_strong = ["wiki", "mediawiki", "wikitext", "special:search", "main page - wiki"]
    wiki_medium = ["encyclopedia", "edit this page", "revision history", "article talk"]
    for w in wiki_strong:
        if w in combined:
            weights["wiki"] += 4
    for w in wiki_medium:
        if w in combined:
            weights["wiki"] += 2

    # Library indicators
    lib_strong = ["library", "genesis", "ebooks", "z-library", "books catalog"]
    lib_medium = ["book", "author", "isbn", "publisher", "download pdf", "monograph"]
    for w in lib_strong:
        if w in combined:
            weights["library"] += 4
    for w in lib_medium:
        if w in combined:
            weights["library"] += 2

    # News indicators
    news_strong = ["press release", "journalism", "daily news", "news agency", "breaking news"]
    news_medium = ["press", "editorial", "headline", "reporter", "correspondent"]
    for w in news_strong:
        if w in combined:
            weights["news"] += 4
    for w in news_medium:
        if w in combined:
            weights["news"] += 2

    # Market indicators
    market_strong = ["marketplace", "vendor", "escrow", "shopping cart", "add to cart"]
    market_medium = ["market", "shop", "price", "btc price", "checkout", "shipping", "catalog"]
    for w in market_strong:
        if w in combined:
            weights["market"] += 4
    for w in market_medium:
        if w in combined:
            weights["market"] += 2
    if has_cart:
        weights["market"] += 3

    # Identify best category
    best_cat = max(weights, key=weights.get)
    if weights[best_cat] >= 3:
        return best_cat

    # Fallback minimal heuristics
    if "wiki" in combined:
        return "wiki"
    if "forum" in combined:
        return "forum"
    if "library" in combined:
        return "library"
    if "market" in combined or "shop" in combined:
        return "market"
    if "news" in combined:
        return "news"

    return "other"


def extract_fingerprint(text):
    """Generate a 16-hex fingerprint from text after removing digits to identify content clones."""
    core = re.sub(r"\d+", "", text)
    return hashlib.sha256(core.encode()).hexdigest()[:16]


class ContentDetector:
    """Class wrapper for content detection with in-memory LRU classification caching."""

    def __init__(self, max_cache_size=50000):
        self.max_cache_size = max_cache_size
        self.fp_cache = OrderedDict()
        self.lock = threading.Lock()

    def get_cached_classification(self, fp):
        """Retrieve cached (lang, category) tuple by content fingerprint."""
        if not fp:
            return None
        with self.lock:
            if fp in self.fp_cache:
                self.fp_cache.move_to_end(fp)
                return self.fp_cache[fp]
        return None

    def cache_classification(self, fp, lang, category):
        """Store (lang, category) in LRU fingerprint cache."""
        if not fp:
            return
        with self.lock:
            self.fp_cache[fp] = (lang, category)
            if len(self.fp_cache) > self.max_cache_size:
                self.fp_cache.popitem(last=False)

    def classify_with_cache(self, fp, title, text, html_lang="", soup=None):
        """Classify content, using fingerprint cache to bypass repeat computation."""
        cached = self.get_cached_classification(fp)
        if cached:
            return cached[0], cached[1]

        lang = self.detect_language(text, html_lang)
        category = self.detect_category(title, text, soup=soup)
        self.cache_classification(fp, lang, category)
        return lang, category

    def detect_language(self, text, html_lang_attr=""):
        return detect_language(text, html_lang_attr)

    def detect_category(self, title, text, soup=None):
        return detect_category(title, text, soup=soup)

    def extract_fingerprint(self, text):
        return extract_fingerprint(text)

    def extract_bitcoin_addresses(self, text, validate_checksum=True):
        return extract_bitcoin_addresses(text, validate_checksum=validate_checksum)
