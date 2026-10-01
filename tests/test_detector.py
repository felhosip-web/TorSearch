import pytest
from onion_search.core.detector import (
    detect_language,
    detect_category,
    extract_fingerprint,
    extract_bitcoin_addresses,
    ContentDetector,
)

def test_detect_language():
    assert detect_language("hello", html_lang_attr="hu") == "hu"
    assert detect_language("hello", html_lang_attr="en") == "en"
    assert detect_language("hello", html_lang_attr="de") == "de"
    
    hu_text = "Ez egy szép magyar mondat és az alma nagyon finom"
    assert detect_language(hu_text) == "hu"
    
    en_text = "The quick brown fox jumps over the lazy dog and of the world"
    assert detect_language(en_text) == "en"
    
    ru_text = "Это русский текст для проверки работы детектора языка"
    assert detect_language(ru_text) == "ru"

def test_detect_category():
    assert detect_category("Tor Forum", "Latest board discussions and posts") == "forum"
    assert detect_category("Onion Wiki", "Documentation page") == "wiki"
    assert detect_category("Free Library", "Book reading and pdf downloads") == "library"
    assert detect_category("Daily News", "Journalism and press wire") == "news"
    assert detect_category("Crypto Market", "Shop vendors and goods") == "market"
    assert detect_category("Random Blog", "Personal life thoughts") == "other"

def test_extract_fingerprint():
    text1 = "Version 123 of Page ABC"
    text2 = "Version 999 of Page ABC"
    # Digits are stripped in fingerprinting, so text1 and text2 produce identical fingerprints
    assert extract_fingerprint(text1) == extract_fingerprint(text2)
    assert len(extract_fingerprint(text1)) == 16

def test_extract_bitcoin_addresses():
    text = "Send donation to 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa or bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq thanks"
    addresses = extract_bitcoin_addresses(text)
    assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in addresses
    assert "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq" in addresses

def test_content_detector_class():
    detector = ContentDetector()
    assert detector.detect_category("Forum", "posts") == "forum"
    assert len(detector.extract_fingerprint("Hello World")) == 16
