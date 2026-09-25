from scrapy_redis.spiders import RedisSpider
from myqoutes.items import QuoteItem

class QuotesSpider(RedisSpider):
    name = "quotes"
    redis_key = "quotes:start_urls"

    def parse(self, response):
        # self.logger.info(f"本次请求 UA 尾部: {response.request.headers.get('User-Agent')!r} ... 截取判断")
        for quote in response.css("div.quote"):
            yield QuoteItem(
                text=quote.css("span.text::text").get(),
                author=quote.css("small.author::text").get(),
                tags=quote.css("div.tags a::text").getall()
            )
        next_page = response.css("li.next a::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

