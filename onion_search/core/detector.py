# Copyright 2026 HES Projects by FePe
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Content detection: language, category, fingerprint, and crypto address extraction.
Includes LRU classification caching by fingerprint for high-throughput scraping.
Developed by HES Projects by FePe.
"""
from collections import OrderedDict
import hashlib
import re
import threading
from typing import Dict, List, Optional, Pattern, Tuple, Union
from bs4 import BeautifulSoup
from onion_search.config import MAX_MEMORY_CACHE_SIZE

BASE58_ALPHABET: str = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE58_REGEX: Pattern[str] = re.compile(r"\b[13][1-9A-HJ-NP-Za-km-z]{25,34}\b")
BECH32_REGEX: Pattern[str] = re.compile(r"\bbc1[ac-hj-np-z02-9]{38,60}\b", re.IGNORECASE)


def decode_base58(s: str) -> bytes:
    """Decode a Base58 string to bytes with leading zeros preserved."""
    n: int = 0
    for char in s:
        n = n * 58 + BASE58_ALPHABET.index(char)
    res: List[int] = []
    while n > 0:
        res.append(n & 0xFF)
        n >>= 8
    raw_bytes: bytes = bytes(reversed(res))
    num_zeros: int = len(s) - len(s.lstrip("1"))
    return b"\x00" * num_zeros + raw_bytes


def is_valid_base58_address(addr: str) -> bool:
    """Validate a legacy/P2SH Bitcoin address using Base58Check checksum."""
    if not (26 <= len(addr) <= 35) or addr[0] not in ("1", "3"):
        return False
    try:
        raw: bytes = decode_base58(addr)
        if len(raw) != 25:
            return False
        payload: bytes = raw[:-4]
        checksum: bytes = raw[-4:]
        h1: bytes = hashlib.sha256(payload).digest()
        h2: bytes = hashlib.sha256(h1).digest()
        return h2[:4] == checksum
    except Exception:
        return False


def is_valid_bech32_address(addr: str) -> bool:
    """Validate Bech32 Bitcoin address format and character set."""
    addr_lower: str = addr.lower()
    if not addr_lower.startswith("bc1"):
        return False
    if not (42 <= len(addr_lower) <= 62):
        return False
    allowed: set = set("qpzry9x8gf2tvdw0s3jn54khce6mua7l")
    payload: str = addr_lower[3:]
    return all(c in allowed for c in payload)


def validate_bitcoin_address(addr: str) -> bool:
    """Check if address is a valid Bitcoin address (Base58Check or Bech32)."""
    if addr.startswith("1") or addr.startswith("3"):
        return is_valid_base58_address(addr)
    if addr.lower().startswith("bc1"):
        return is_valid_bech32_address(addr)
    return False


def extract_bitcoin_addresses(text: str, validate_checksum: bool = True) -> List[str]:
    """
    Extract Bitcoin addresses from text.
    Filters out invalid Base58 characters (0, O, I, l) and optionally verifies checksums.
    """
    candidates: set = set()
    for m in BASE58_REGEX.findall(text):
        candidates.add(m)
    for m in BECH32_REGEX.findall(text):
        candidates.add(m.lower())

    if not validate_checksum:
        return list(candidates)

    valid_addrs: List[str] = []
    for addr in candidates:
        if validate_bitcoin_address(addr):
            valid_addrs.append(addr)
    return valid_addrs


def detect_language(text: str, html_lang_attr: str = "") -> str:
    """
    Fast and accurate language detection.
    1. HTML lang attribute fast-path.
    2. Heuristic frequency score.
    3. Langdetect only called when ambiguous.
    """
    if html_lang_attr:
        l: str = html_lang_attr.lower().strip()[:2]
        if l in ("hu", "en", "de", "fr", "es", "ru", "it", "pl", "ro", "sk", "cs"):
            return l

    t: str = text.lower()
    hu_diacritics: int = len(re.findall(r"[áéíóöőúüű]", t))
    ru_letters: int = len(re.findall(r"[а-яё]", t))

    # Fast-path for Russian
    if ru_letters > 10:
        return "ru"

    # Fast-path for Hungarian
    hu_words: int = t.count(" a ") + t.count(" az ") + t.count(" és ") + t.count(" hogy ")
    hu_score: float = (hu_words + hu_diacritics) * 1.5
    if hu_diacritics >= 3 or hu_score >= 8:
        return "hu"

    en_score: int = (
        t.count(" the ")
        + t.count(" and ")
        + t.count(" of ")
        + t.count(" to ")
        + t.count(" is ")
    )
    de_score: int = (
        t.count(" und ")
        + t.count(" der ")
        + t.count(" die ")
        + t.count(" das ")
        + t.count(" ist ")
    )
    fr_score: int = (
        t.count(" le ")
        + t.count(" la ")
        + t.count(" et ")
        + t.count(" des ")
        + t.count(" du ")
    )

    scores: Dict[str, float] = {
        "hu": hu_score,
        "en": float(en_score),
        "de": float(de_score),
        "fr": float(fr_score),
        "ru": float(ru_letters * 2),
    }

    best: str = max(scores, key=lambda k: scores[k])
    sorted_scores: List[float] = sorted(scores.values(), reverse=True)

    # If top heuristic has high confidence over second place, return immediately
    if sorted_scores[0] >= 5 and (sorted_scores[0] - sorted_scores[1] >= 3):
        return best

    # Fallback to langdetect only if ambiguous
    try:
        from langdetect import detect as ld_detect

        lang: str = ld_detect(text[:2000])
        if len(lang) == 2:
            return lang.lower()
    except Exception:
        pass

    if scores[best] < 3:
        return "en"
    return best


def detect_category(title: str, text: str, soup: Optional[BeautifulSoup] = None) -> str:
    """
    Weighted category classification based on title, content, meta tags, and HTML structure.
    Avoids false positives (e.g. solitary 'post' word no longer flags forum).
    """
    meta_text: str = ""
    has_post_form: bool = False
    has_cart: bool = False

    if soup is not None:
        # Check meta keywords & description
        for meta in soup.find_all("meta"):
            name: str = meta.get("name", "").lower()
            prop: str = meta.get("property", "").lower()
            if name in ("keywords", "description") or prop in (
                "og:description",
                "og:title",
            ):
                meta_text += " " + meta.get("content", "")

        # Check structural elements
        for form in soup.find_all("form"):
            form_text: str = str(form).lower()
            if "comment" in form_text or "reply" in form_text or "message" in form_text:
                has_post_form = True
            if "cart" in form_text or "checkout" in form_text or "buy" in form_text:
                has_cart = True

    combined: str = (title + " " + meta_text + " " + text[:2500]).lower()

    weights: Dict[str, int] = {
        "forum": 0,
        "wiki": 0,
        "library": 0,
        "news": 0,
        "market": 0,
    }

    # Forum indicators (weighted phrases)
    forum_strong: List[str] = [
        "forum",
        "board index",
        "phpbb",
        "discussions",
        "subforum",
        "threads",
        "bulletin board",
    ]
    forum_medium: List[str] = ["thread", "topic", "reply to thread", "posts:", "registered user"]
    for w in forum_strong:
        if w in combined:
            weights["forum"] += 4
    for w in forum_medium:
        if w in combined:
            weights["forum"] += 2
    if has_post_form:
        weights["forum"] += 3

    # Wiki indicators
    wiki_strong: List[str] = ["wiki", "mediawiki", "wikitext", "special:search", "main page - wiki"]
    wiki_medium: List[str] = ["encyclopedia", "edit this page", "revision history", "article talk"]
    for w in wiki_strong:
        if w in combined:
            weights["wiki"] += 4
    for w in wiki_medium:
        if w in combined:
            weights["wiki"] += 2

    # Library indicators
    lib_strong: List[str] = ["library", "genesis", "ebooks", "z-library", "books catalog"]
    lib_medium: List[str] = ["book", "author", "isbn", "publisher", "download pdf", "monograph"]
    for w in lib_strong:
        if w in combined:
            weights["library"] += 4
    for w in lib_medium:
        if w in combined:
            weights["library"] += 2

    # News indicators
    news_strong: List[str] = ["press release", "journalism", "daily news", "news agency", "breaking news"]
    news_medium: List[str] = ["press", "editorial", "headline", "reporter", "correspondent"]
    for w in news_strong:
        if w in combined:
            weights["news"] += 4
    for w in news_medium:
        if w in combined:
            weights["news"] += 2

    # Market indicators
    market_strong: List[str] = ["marketplace", "vendor", "escrow", "shopping cart", "add to cart"]
    market_medium: List[str] = ["market", "shop", "price", "btc price", "checkout", "shipping", "catalog"]
    for w in market_strong:
        if w in combined:
            weights["market"] += 4
    for w in market_medium:
        if w in combined:
            weights["market"] += 2
    if has_cart:
        weights["market"] += 3

    # Identify best category
    best_cat: str = max(weights, key=lambda k: weights[k])
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


def extract_fingerprint(text: str) -> str:
    """Generate a 16-hex fingerprint from text after removing digits to identify content clones."""
    core: str = re.sub(r"\d+", "", text)
    return hashlib.sha256(core.encode()).hexdigest()[:16]


class ContentDetector:
    """Class wrapper for content detection with in-memory LRU classification caching."""

    def __init__(self, max_cache_size: int = MAX_MEMORY_CACHE_SIZE) -> None:
        self.max_cache_size: int = max_cache_size
        self.fp_cache: OrderedDict[str, Tuple[str, str]] = OrderedDict()
        self.lock: threading.Lock = threading.Lock()

    def get_cached_classification(self, fp: str) -> Optional[Tuple[str, str]]:
        """Retrieve cached (lang, category) tuple by content fingerprint."""
        if not fp:
            return None
        with self.lock:
            if fp in self.fp_cache:
                self.fp_cache.move_to_end(fp)
                return self.fp_cache[fp]
        return None

    def cache_classification(self, fp: str, lang: str, category: str) -> None:
        """Store (lang, category) in LRU fingerprint cache."""
        if not fp:
            return
        with self.lock:
            self.fp_cache[fp] = (lang, category)
            if len(self.fp_cache) > self.max_cache_size:
                self.fp_cache.popitem(last=False)

    def classify_with_cache(
        self,
        fp: str,
        title: str,
        text: str,
        html_lang: str = "",
        soup: Optional[BeautifulSoup] = None,
    ) -> Tuple[str, str]:
        """Classify content, using fingerprint cache to bypass repeat computation."""
        cached = self.get_cached_classification(fp)
        if cached:
            return cached[0], cached[1]

        lang: str = self.detect_language(text, html_lang)
        category: str = self.detect_category(title, text, soup=soup)
        self.cache_classification(fp, lang, category)
        return lang, category

    def detect_language(self, text: str, html_lang_attr: str = "") -> str:
        return detect_language(text, html_lang_attr)

    def detect_category(self, title: str, text: str, soup: Optional[BeautifulSoup] = None) -> str:
        return detect_category(title, text, soup=soup)

    def extract_fingerprint(self, text: str) -> str:
        return extract_fingerprint(text)

    def extract_bitcoin_addresses(self, text: str, validate_checksum: bool = True) -> List[str]:
        return extract_bitcoin_addresses(text, validate_checksum=validate_checksum)
