import hashlib
import logging

import pymysql

logger = logging.getLogger(__name__)

def make_fingerprint(text):
    """对文本计算 md5 指纹，用于数据库防重"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

class MySQLPipeline:
    def __init__(self, settings, crawler):
        self.settings = settings
        self.crawler = crawler
        self.saved = 0
        self.errors = 0

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings, crawler)

    def open_spider(self):
        self.conn = pymysql.connect(
            host=self.settings.get('MYSQL_HOST'),
            port=self.settings.getint('MYSQL_PORT'),
            user=self.settings.get('MYSQL_USER'),
            passwd=self.settings.get('MYSQL_PASSWORD'),
            db=self.settings.get('MYSQL_DB'),
            charset="utf8mb4",
        )
        self.cursor = self.conn.cursor()

    def process_item(self, item):
        text_hash = make_fingerprint(item['text'])
        sql = """
            INSERT INTO quotes(text_hash, text, author) 
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE author = VALUES(author)
        """
        try:
            self.cursor.execute(sql, (text_hash, item['text'], item['author']))
            self.conn.commit()
            self.saved += 1
        except Exception as e:
            logger.error("入库失败: %s", e)
            self.errors += 1
        return item

    def close_spider(self):
        logger.info("采集结束统计：成功入库 %d 条, 失败 %d 条", self.saved, self.errors)
        self.cursor.close()
        self.conn.close()