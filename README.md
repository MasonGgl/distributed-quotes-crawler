# myquotes · 分布式爬虫学习项目

> 一个用于理解**分布式采集原理**的完整 Scrapy 项目：Redis 共享队列 + 共享去重 + MySQL 防重入库 + UA 轮换反爬。
> 作者背景：2 年电商数据采集经验（平台托管版），本项目是从"会用平台"到"懂原理"的手工实现。

## 架构

```
                    ┌─────────────────────────────┐
                    │      Redis (127.0.0.1)      │
                    │  quotes:start_urls  起始任务 │
                    │  quotes:requests    请求队列 │
                    │  quotes:dupefilter  去重指纹 │
                    └──────────┬──────────────────┘
                     抢任务 ↑    ↓ 共享指纹
              ┌────────────┴─┐   ┌─┴────────────┐
              │  Worker 进程 1 │   │  Worker 进程 2 │   ← 可横向扩展到 N 台机器
              │  (scrapy crawl)│   │  (scrapy crawl)│
              └──────┬───────┘   └─┬────────────┘
                     │ RandomUAMiddleware（每请求轮换 UA）
                     ▼
              quotes.toscrape.com
                     │
                     ▼ Item Pipeline
              ┌─────────────────────────────┐
              │      MySQL (crawler_lab)     │
              │  quotes 表：text_hash 唯一索引 │
              │  ON DUPLICATE KEY 防重入库    │
              └─────────────────────────────┘
```

## 核心设计

### 1. 分布式调度（scrapy-redis）
- Spider 继承 `RedisSpider`，`start_urls` 不写在代码里，改为监听 Redis 队列 `quotes:start_urls`；
- 多个 worker 进程（可分布在不同机器）抢同一个队列，谁领到谁干；
- 领走的任务没有 ack 机制——worker 崩溃任务即丢失，生产环境需应用层重试兜底（对应我此前在采集平台实现的"失败任务扫描 + 自动重试"逻辑）。

### 2. 分布式去重
- `RFPDupeFilter` 把每个请求 URL 的 SHA1 指纹存入 Redis Set `quotes:dupefilter`；
- 所有 worker 共享同一份指纹表，跨机器不重复采集。

### 3. 数据防重入库（Item Pipeline）
- 名言没有唯一 URL，取**正文 MD5** 作为指纹（`text_hash CHAR(32)`）；
- 表上建 `UNIQUE KEY uk_text_hash`，SQL 用 `INSERT ... ON DUPLICATE KEY UPDATE`；
- **验收标准：重复采集 N 次，`COUNT(*)` 恒为 100** —— 实测通过。

### 4. 反爬中间件（Downloader Middleware）
- `RandomUAMiddleware`：每个请求随机轮换 User-Agent，摊薄单 UA 请求频率；
- `RETRY_TIMES=5`，429/5xx 自动重试；
- `AUTOTHROTTLE_ENABLED`：根据网站响应自适应降速。

### 5. 配置分离与依赖注入
- 数据库密码走**环境变量**（`MYSQL_PASSWORD`），代码仓库零明文密钥；
- Pipeline 通过 `from_crawler` 拿 crawler.settings 注入配置，并已适配新版 Scrapy 的钩子签名（无 spider 参数）；
- 指纹计算抽成独立函数 `make_fingerprint`，纯逻辑与 IO 解耦，可独立测试。

### 6. 单元测试
- pytest 覆盖指纹生成逻辑（正确性 / 稳定性 / 区分度三组断言）；
- `python -m pytest tests -v` 一键验证，不依赖真实数据库。

## 运行

完整分步搭建指南（虚拟环境 → 数据库 → 环境变量 → 分布式运行 → 测试）见 **[docs/SETUP.md](docs/SETUP.md)**，每一步都标注了"在干嘛"。

快速开始：

```bash
pip install -r requirements.txt

# 启动 Redis / MySQL（docker compose up -d 或本地服务）
mysql -uroot -p < init/01_schema.sql && mysql -uroot -p < init/02_quotes.sql
setx MYSQL_PASSWORD "你的MySQL密码"    # 重开终端生效

# 下发任务 + 开 N 个终端跑 worker
redis-cli LPUSH quotes:start_urls http://quotes.toscrape.com/
python -m scrapy crawl quotes

# 验证：重复跑 COUNT 恒为 100
mysql -e "SELECT COUNT(*) FROM crawler_lab.quotes;"

# 单元测试
python -m pytest tests -v
```

## 踩坑记录（真实调试过程）

| 坑 | 原因 | 解法 |
|---|---|---|
| `QuoteItem.__init__() got an unexpected keyword argument` | `@dataclass` 与 `scrapy.Item` 混用，dataclass 的 `__init__` 不认 `scrapy.Field()` | 二选一，本项目用 `scrapy.Item` |
| redis-cli `LPUSH` 报 `Invalid argument(s)` | 带 `{}`/引号的参数被 shell 拆分 | 裸传 URL |
| `setdefault` 后 UA 仍是 Scrapy 默认 | 默认 UA 已存在，`setdefault` 不覆盖 | 改直接赋值 `headers["User-Agent"] = ua` |
| robots 中间件 `assert useragent is not None` | `USER_AGENT=None` 时 robots 检查（排序 100，先于自定义中间件）无兜底 | 删除该设置，保持默认 |

## 技术栈

`Python 3.14` · `Scrapy 2.19` · `scrapy-redis 0.9` · `Redis 5/7` · `MySQL 8.0` · `pytest` · `Docker Compose`
