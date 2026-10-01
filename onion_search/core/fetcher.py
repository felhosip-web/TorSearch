"""
Network operations, session management, and onion fetching.
"""
import random
import re
import threading
import time
from bs4 import BeautifulSoup
import requests
from onion_search.core.detector import (
    ContentDetector,
    detect_category,
    detect_language,
    extract_bitcoin_addresses,
    extract_fingerprint,
)
from onion_search.utils.helpers import GITHUB_SOURCES, HEADERS_LIST, TIMEOUT_GET

thread_local = threading.local()


def get_session(proxy_url):
    """Retrieve or create thread-local requests.Session configured with Tor proxy."""
    cur_proxy = getattr(thread_local, "proxy_url", None)
    if hasattr(thread_local, "session") and cur_proxy != proxy_url:
        try:
            thread_local.session.close()
        except Exception:
            pass
        try:
            del thread_local.session
        except Exception:
            pass
    if not hasattr(thread_local, "session"):
        s = requests.Session()
        s.proxies = {"http": proxy_url, "https": proxy_url}
        s.headers.update(random.choice(HEADERS_LIST))
        thread_local.session = s
        thread_local.proxy_url = proxy_url
    return thread_local.session


def close_all_thread_sessions():
    """Close and clean up thread-local sessions on NEWNYM or shutdown."""
    try:
        if hasattr(thread_local, "session"):
            try:
                thread_local.session.close()
            except Exception:
                pass
            try:
                del thread_local.session
            except Exception:
                pass
        if hasattr(thread_local, "proxy_url"):
            try:
                del thread_local.proxy_url
            except Exception:
                pass
    except Exception:
        pass


class SessionManager:
    """Manages thread-local requests sessions for Tor routing."""

    def get_session(self, proxy_url):
        return get_session(proxy_url)

    def close_all(self):
        close_all_thread_sessions()


class OnionFetcher:
    """Handles network fetching from public directories, seed lists, and onion services."""

    def __init__(self, session_manager=None, detector=None):
        self.session_manager = session_manager or SessionManager()
        self.detector = detector or ContentDetector()

    def fetch_github_seeds(self):
        """Fetch discovered .onion addresses from public GitHub and Ahmia lists."""
        found = set()
        reg = re.compile(r"[a-z2-7]{56}\.onion")
        for src in GITHUB_SOURCES:
            try:
                r = requests.get(
                    src, timeout=15, headers=random.choice(HEADERS_LIST)
                )
                for m in reg.findall(r.text):
                    found.add(f"http://{m}")
            except Exception:
                pass
        try:
            r = requests.get(
                "https://ahmia.fi/onions/",
                timeout=15,
                headers=random.choice(HEADERS_LIST),
            )
            for m in reg.findall(r.text):
                found.add(f"http://{m}")
        except Exception:
            pass
        return found

    def search_ahmia(self, queries, is_running_cb=None):
        """Query Ahmia search engine for keywords and extract .onion links."""
        all_onions = set()
        for q in queries:
            if is_running_cb and not is_running_cb():
                break
            try:
                r = requests.get(
                    f"https://ahmia.fi/search/?q={requests.utils.quote(q)}",
                    timeout=15,
                    headers=random.choice(HEADERS_LIST),
                )
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    h = a["href"]
                    if ".onion" in h:
                        if "redirect_url=" in h:
                            h = h.split("redirect_url=")[1]
                        h = h.split("?")[0].split("#")[0]
                        if len(h) > 20:
                            all_onions.add(h)
            except Exception:
                pass
        return all_onions

    def fetch_page(self, url, proxy_url):
        """Fetch a single onion URL through Tor SOCKS proxy and parse structure."""
        now_ts = time.time()
        sess = self.session_manager.get_session(proxy_url)
        if random.random() < 0.3:
            sess.headers.update(random.choice(HEADERS_LIST))
        try:
            r = sess.get(url, timeout=TIMEOUT_GET, allow_redirects=True)
            final_url = r.url
            if r.status_code != 200 or len(r.text) < 300:
                return {
                    "url": final_url if ".onion" in final_url else url,
                    "status": "dead",
                    "code": r.status_code,
                    "ts": now_ts,
                    "lang": "en",
                    "category": "other",
                }
            html = r.text
            url_to_save = final_url if ".onion" in final_url else url
        except Exception as e:
            return {
                "url": url,
                "status": "dead",
                "err": str(e)[:100],
                "ts": now_ts,
                "lang": "en",
                "category": "other",
            }

        soup = BeautifulSoup(html, "html.parser")
        html_lang = soup.html.get("lang", "") if soup.html else ""
        for s in soup(["script", "style", "nav", "footer"]):
            s.decompose()
        text = re.sub(r"\s+", " ", soup.get_text()).lower().strip()[:8000]

        if len(text) < 200:
            return {
                "url": url_to_save,
                "status": "empty",
                "ts": now_ts,
                "lang": "en",
                "category": "other",
            }

        fp = self.detector.extract_fingerprint(text)
        btc = self.detector.extract_bitcoin_addresses(text)
        lang = self.detector.detect_language(text, html_lang)
        title_tmp = (
            soup.title.string.strip()[:70]
            if soup.title and soup.title.string
            else "Nincs cím"
        )
        category = self.detector.detect_category(title_tmp, text)

        return {
            "url": url_to_save,
            "status": "ok",
            "title": title_tmp,
            "text": text,
            "snippet": text[:120],
            "fp": fp,
            "btc": btc,
            "ts": now_ts,
            "lang": lang,
            "category": category,
        }
