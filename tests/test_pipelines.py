import hashlib
from myqoutes.pipelines import make_fingerprint
from scrapy.settings import Settings
from myqoutes.pipelines import MySQLPipeline
from myqoutes.items import QuoteItem

def test_fingerprint_is_mad5():
    assert make_fingerprint("hello") == hashlib.md5("hello".encode('utf-8')).hexdigest()

def test_same_test_same_fingerprint():
    assert make_fingerprint("abc") == make_fingerprint("abc")

def test_different_test_different_fingerprint():
    assert make_fingerprint("hello") != make_fingerprint("abc")


# ========== 测试替身：假装是数据库，实际只是个"记录员" ==========
class FakeCursor:
    """记录每次 execute 收到的参数，供测试断言"""
    def __init__(self):
        self.executed = []

    def execute(self, sql, args):
        self.executed.append((sql, args))

    def commit(self):
        pass

    def close(self):
        pass

class FakeConn:
    def __init__(self):
        self.comitted = False

    def commit(self):
        self.comitted = True

    def close(self):
        pass

class BrokenCursor(FakeCursor):
    """模拟数据库挂了：一执行就炸"""
    def execute(self, sql, args):
        raise Exception("db down")


def make_pipeline():
    p = MySQLPipeline(Settings(), None)
    p.cursor = FakeCursor()
    p.conn = FakeCursor()
    return p

def make_item():
    return QuoteItem(text="hello world", author="tester")

def test_process_item_executes_sql():
    p = make_pipeline()
    p.process_item(make_item())
    assert len(p.cursor.executed) == 1
    fingerprint = p.cursor.executed[0][1][0]
    assert fingerprint == make_fingerprint("hello world")

def test_process_item_counts_saved():
    p = make_pipeline()
    p.process_item(make_item())
    assert p.saved == 1
    assert p.errors == 0

def test_process_item_swallows_db_error():
    p = make_pipeline()
    p.cursor = BrokenCursor()
    returned = p.process_item(make_item())
    assert p.errors == 1
    assert returned is not None