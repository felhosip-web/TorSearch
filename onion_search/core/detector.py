"""
Content detection: language, category, fingerprint, and crypto address extraction.
"""
import hashlib
import re


def detect_language(text, html_lang_attr=""):
    """Detect the language of text using HTML attribute, langdetect library, or word frequency heuristics."""
    if html_lang_attr:
        l = html_lang_attr.lower().strip()[:2]
        if l in ("hu", "en", "de", "fr", "es", "ru", "it", "pl", "ro", "sk", "cs"):
            return l
    try:
        from langdetect import detect as ld_detect

        lang = ld_detect(text[:2000])
        if len(lang) == 2:
            return lang.lower()
    except Exception:
        pass
    t = text.lower()
    hu_score = (
        t.count(" a ")
        + t.count(" az ")
        + t.count(" és ")
        + t.count(" hogy ")
        + len(re.findall(r"[áéíóöőúüű]", t))
    )
    en_score = t.count(" the ") + t.count(" and ") + t.count(" of ")
    de_score = t.count(" und ") + t.count(" der ") + t.count(" die ")
    fr_score = t.count(" le ") + t.count(" la ") + t.count(" et ")
    ru_score = len(re.findall(r"[а-яё]", t))
    scores = {
        "hu": hu_score * 1.5,
        "en": en_score,
        "de": de_score,
        "fr": fr_score,
        "ru": ru_score * 2,
    }
    if ru_score > 10:
        return "ru"
    best = max(scores, key=scores.get)
    if scores[best] < 3:
        return "en"
    return best


def detect_category(title, text):
    """Categorize page content based on title and snippet text keywords."""
    t = (title + " " + text[:1000]).lower()
    if any(k in t for k in ["forum", "board", "thread", "topic", "post"]):
        return "forum"
    if "wiki" in t:
        return "wiki"
    if any(k in t for k in ["library", "lib", "book"]):
        return "library"
    if any(k in t for k in ["news", "press"]):
        return "news"
    if any(k in t for k in ["market", "shop"]):
        return "market"
    return "other"


def extract_fingerprint(text):
    """Generate a 16-hex fingerprint from text after removing digits to identify content clones."""
    core = re.sub(r"\d+", "", text)
    return hashlib.sha256(core.encode()).hexdigest()[:16]


def extract_bitcoin_addresses(text):
    """Extract Bitcoin addresses (standard and bech32) from text."""
    return re.findall(r"(bc1[a-z0-9]{25,}|[13][a-km-zA-HJ-NP-Z1-9]{25,})", text)


class ContentDetector:
    """Class wrapper for content detection, supporting dependency injection."""

    def __init__(self):
        pass

    def detect_language(self, text, html_lang_attr=""):
        return detect_language(text, html_lang_attr)

    def detect_category(self, title, text):
        return detect_category(title, text)

    def extract_fingerprint(self, text):
        return extract_fingerprint(text)

    def extract_bitcoin_addresses(self, text):
        return extract_bitcoin_addresses(text)
