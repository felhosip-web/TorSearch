import pytest
from bs4 import BeautifulSoup
from onion_search.core.detector import (
    detect_language,
    detect_category,
    extract_fingerprint,
    extract_bitcoin_addresses,
    is_valid_base58_address,
    is_valid_bech32_address,
    validate_bitcoin_address,
    ContentDetector,
)

def test_detect_language():
    # HTML lang attribute fast-path
    assert detect_language("arbitrary text", html_lang_attr="hu") == "hu"
    assert detect_language("arbitrary text", html_lang_attr="en") == "en"
    assert detect_language("arbitrary text", html_lang_attr="de") == "de"
    
    # Hungarian diacritics fast heuristic
    hu_text = "Ez egy szép magyar mondat és az alma nagyon finom árvíztűrő tükörfúrógép"
    assert detect_language(hu_text) == "hu"
    
    # English frequent words
    en_text = "The quick brown fox jumps over the lazy dog and of the world is great to see"
    assert detect_language(en_text) == "en"
    
    # Russian Cyrillic fast heuristic
    ru_text = "Это русский текст для проверки работы детектора языка"
    assert detect_language(ru_text) == "ru"

def test_detect_category_no_false_positive_on_post():
    # Solitary 'post' should NOT falsely classify a blog or personal site as a forum
    text = "Welcome to my personal blog. In this post I will discuss my favorite books."
    cat = detect_category("My Life Blog", text)
    assert cat != "forum"
    
    # True forum with strong indicators
    forum_text = "Discussions and board index. Latest topics, threads, and user replies."
    assert detect_category("Tor Discussions", forum_text) == "forum"

def test_detect_category_with_soup_metadata_and_forms():
    html_market = """
    <html>
      <head>
        <title>Onion Market</title>
        <meta name="keywords" content="escrow, vendor, shop, products">
      </head>
      <body>
        <form><button>Add to Cart</button></form>
        <div>BTC Price: 0.05 BTC. Checkout now.</div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html_market, "html.parser")
    cat = detect_category("Onion Market", soup.get_text(), soup=soup)
    assert cat == "market"

def test_detect_category_types():
    assert detect_category("Onion Wiki", "MediaWiki documentation encyclopedia") == "wiki"
    assert detect_category("Free Library", "Genesis library download pdf ebooks isbn 978-3-16") == "library"
    assert detect_category("Daily News Wire", "Breaking news press agency journalism report") == "news"

def test_bitcoin_address_validation():
    # Valid Genesis block legacy address
    assert is_valid_base58_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") is True
    
    # Valid P2SH address
    assert is_valid_base58_address("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy") is True
    
    # Invalid characters (0, O, I, l)
    assert is_valid_base58_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7Div0O") is False
    assert is_valid_base58_address("101zP1eP5QGefi2DMPTfTL5SLmv7DivfN") is False
    
    # Bad checksum
    assert is_valid_base58_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNb") is False
    
    # Valid Bech32 address
    assert is_valid_bech32_address("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq") is True
    
    # Invalid Bech32 (wrong prefix or invalid chars)
    assert is_valid_bech32_address("bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mb1") is False

def test_extract_bitcoin_addresses_with_checksum():
    text = (
        "Valid address: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa and "
        "Fake address: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfXX and "
        "Valid bech32: bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"
    )
    extracted = extract_bitcoin_addresses(text, validate_checksum=True)
    assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa" in extracted
    assert "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq" in extracted
    assert "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfXX" not in extracted

def test_content_detector_class():
    detector = ContentDetector()
    assert detector.detect_category("Forum Index", "topics and threads") == "forum"
    assert len(detector.extract_fingerprint("Hello World")) == 16
