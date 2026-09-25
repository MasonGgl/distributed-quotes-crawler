import hashlib

import pymysql

class MySQLPipeline:
    def __init__(self, settings):
        self.settings = settings

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings)

    def open_spider(self, spider):
        self.conn = pymysql.connect(
            host=self.settings.get('MYSQL_HOST'),
            port=self.settings.getint('MYSQL_PORT'),
            user=self.settings.get('MYSQL_USER'),
            passwd=self.settings.get('MYSQL_PASSWORD'),
            db=self.settings.get('MYSQL_DB'),
            charset="utf8mb4",
        )
        self.cursor = self.conn.cursor()

    def process_item(self, item, spider):
        text_hash = hashlib.md5(item['text'].encode('utf-8')).hexdigest()
        sql = """
            INSERT INTO quotes(text_hash, text, author) 
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE author = VALUES(author)
        """
        try:
            self.cursor.execute(sql, (text_hash, item['text'], item['author']))
            self.conn.commit()
        except Exception as e:
            print(f"[pipeline] 入库失败：{e}")
        return item

    def close_spider(self, spider):
        self.cursor.close()
        self.conn.close()