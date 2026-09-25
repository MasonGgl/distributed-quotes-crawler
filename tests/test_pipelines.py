import hashlib
from myqoutes.pipelines import make_fingerprint

def test_fingerprint_is_mad5():
    assert make_fingerprint("hello") == hashlib.md5("hello".encode('utf-8')).hexdigest()

def test_same_test_same_fingerprint():
    assert make_fingerprint("abc") == make_fingerprint("abc")

def test_different_test_different_fingerprint():
    assert make_fingerprint("hello") != make_fingerprint("abc")