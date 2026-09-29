"""API 接口爬虫示例：不解析 HTML，直接对接数据接口。

流程演示（A1 抓包课程产出）：
1. 用 F12 Network（Fetch/XHR 过滤）或 mitmproxy 抓包，定位数据接口
   https://quotes.toscrape.com/api/quotes?page=N
2. 分析接口返回的 JSON 结构（quotes 数组 + has_next 翻页标记）
3. 用 requests 直接请求接口，按 has_next 循环翻页，提取结构化字段

对比 scrapy 版本（HTML 解析 + 分布式调度）：接口爬虫无需写选择器、
数据干净、抗页面改版；但前提是能找到接口——这正是抓包的意义。
"""

import logging
import time

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}


def crawl_api(base_url: str, page: int = 1, results: list | None = None) -> list:
    """递归翻页：每页采集后根据 has_next 决定是否请求下一页。

    注意：纯翻页场景更推荐 while 循环（Python 不做尾递归优化，
    页数过多会触发 RecursionError）。这里保留递归写法作对照。
    """
    if results is None:
        results = []

    response = requests.get(base_url, headers=HEADERS, params={"page": page}, timeout=10)
    if response.status_code != 200:
        logger.error("第 %d 页请求失败: HTTP %d", page, response.status_code)
        return results

    page_json = response.json()
    quotes = [
        {
            "text": q["text"],
            "author": q["author"]["name"],
            "tags": len(q["tags"]),
        }
        for q in page_json.get("quotes", [])
    ]
    logger.info("本页共采集 %d 条, 来自第 %d 页", len(quotes), page)
    results.append({"page": page, "quotes": quotes})
    time.sleep(0.5)  # 对接口保持礼貌

    if page_json.get("has_next"):
        return crawl_api(base_url, page + 1, results)
    return results


if __name__ == "__main__":
    all_results = crawl_api("https://quotes.toscrape.com/api/quotes")
    total = sum(len(item["quotes"]) for item in all_results)
    logger.info("采集结束: 共 %d 条, 来自 %d 页", total, len(all_results))
