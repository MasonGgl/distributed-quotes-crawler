# 搭建指南（从零到跑通）

> 本指南记录了项目从零搭建的每一步，包括每步在干嘛和踩过的坑。
> 环境：Windows 10/11 · Python 3.14 · Redis 5 · MySQL 8.0

## 目录结构

```
myqoutes/                 ← 项目根（git 仓库）
├── myqoutes/             ← Scrapy 业务包
│   ├── spiders/quotes.py     # RedisSpider，监听 Redis 队列领任务
│   ├── items.py              # 数据模型
│   ├── pipelines.py          # MySQL 防重入库（from_crawler 注入配置）
│   ├── middlewares.py        # UA 随机轮换中间件
│   └── settings.py           # 配置（数据库参数走环境变量）
├── tests/                ← pytest 单元测试
├── init/                 ← 数据库初始化 SQL
├── conftest.py           ← pytest 根配置（让项目根进入 import 路径）
├── requirements.txt      ← 依赖清单
└── scrapy.cfg
```

## 第 1 步 · 克隆项目并创建虚拟环境

```powershell
git clone https://github.com/MasonGgl/distributed-quotes-crawler.git
cd distributed-quotes-crawler
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**在干嘛：** 虚拟环境把本项目的依赖和系统 Python 隔离，装多少包都不污染全局。激活成功的标志：提示符前面出现 `(.venv)`。

> 若 PowerShell 报"禁止运行脚本"，先执行 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`，或改用 `.venv\Scripts\python.exe` 全路径代替激活。

## 第 2 步 · 安装依赖

```powershell
python -m pip install -r requirements.txt
```

**在干嘛：** 按清单安装固定版本的依赖。两个版本号是刻意锁死的：

- `redis==6.4.0`：redis-py 8.x 建连时发送 RESP3 协议的 `HELLO` 命令，Redis 5 不认识直接断连，6.4.0 是实测兼容的最后版本
- `scrapy-redis==0.9.1`：分布式调度核心

## 第 3 步 · 启动 Redis 和 MySQL（二选一）

### 方式 A · Docker（推荐，跨平台）

```powershell
docker compose up -d
```

**在干嘛：** 按 `docker-compose.yml` 拉起两个容器——Redis 7（6379，开 AOF 持久化）和 MySQL 8.0（3306，root 密码 `root123`，自动建库 `crawler_lab`），并把 `init/` 挂载为 MySQL 初始化目录，**首次启动自动执行建表 SQL**。`healthcheck` 保证容器真正可用而不是仅仅启动。

### 方式 B · 本地解压版（无 Docker 时）

Redis 用 Windows 版 5.0.14.1，MySQL 用 8.0.29 免安装版，启动脚本：

```powershell
D:\crawler-lab\start_db.bat   # 按实际路径调整
```

**在干嘛：** 脚本先用 `netstat` 探测 6379/3306 端口，已启动就跳过（幂等），没启动就最小化拉起服务，最后用 `redis-cli ping` 和 `mysql -e "SELECT 1"` 做健康检查。

## 第 4 步 · 初始化数据库

Docker 方式首次启动已自动建表，可跳过。手动方式：

```powershell
mysql -uroot -proot123 -h127.0.0.1 < init\01_schema.sql
mysql -uroot -proot123 -h127.0.0.1 < init\02_quotes.sql
```

**在干嘛：** `01_schema.sql` 建库和商品/日志表；`02_quotes.sql` 建本项目用的 quotes 表——核心是 `text_hash CHAR(32)` 上的 **UNIQUE KEY**，这是数据防重的最后防线。

## 第 5 步 · 配置数据库密码环境变量

```powershell
setx MYSQL_PASSWORD "你的MySQL密码"
# 重开终端生效
```

**在干嘛：** 密码不写进代码（否则推上 GitHub 全世界可见）。`settings.py` 通过 `os.environ.get("MYSQL_PASSWORD")` 读取，Pipeline 通过 `from_crawler` 拿 settings 注入。`setx` 写注册表永久生效，但只对新开的进程有效——**必须重开终端**。

## 第 6 步 · 下发起始任务

```powershell
redis-cli LPUSH quotes:start_urls http://quotes.toscrape.com/
```

**在干嘛：** RedisSpider 不写死 start_urls，而是监听这个队列。LPUSH 一条 URL = 投一个任务进池子。想多投几次也行——后面的指纹去重会拦住重复采集（这本身就是个可验证的测试点）。

## 第 7 步 · 启动 worker（开几个都行，这就是"分布式"）

每个终端跑一个：

```powershell
python -m scrapy crawl quotes
```

**在干嘛：** 每个 worker 启动后从同一个 Redis 队列抢任务。开 2 个终端就是 2 进程分布式；部署到多台机器，队列和去重指纹依然共享（只要连的同一个 Redis）。

## 第 8 步 · 验证结果

```sql
SELECT COUNT(*) FROM crawler_lab.quotes;   -- 100
```

重复执行第 6、7 步再查，`COUNT(*)` 恒为 100 —— **重复采集不产生重复数据**，这就是三层防重（请求指纹去重 → MD5 指纹 → 唯一索引）的验收标准。

## 第 9 步 · 跑单元测试

```powershell
python -m pytest tests -v
```

**在干嘛：** 测试不碰真数据库——指纹函数是纯逻辑直接断言。`3 passed` 即通过。注意要在项目根（有 `conftest.py` 的目录）执行。

## 第 10 步（进阶）· 把爬虫本身打包成镜像

前面几步的爬虫跑在宿主机上，数据库跑在容器里。最后一步：让爬虫也成为镜像，实现"任何装了 Docker 的机器，clone 下来就能跑"。

项目根的 `Dockerfile`：

```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY . .
CMD ["python", "-m", "scrapy", "crawl", "quotes"]
```

要点：
- **依赖与源码分开 COPY**：依赖层不常变，改动代码后重建镜像时跳过装依赖（层缓存）
- **清华 pip 源**：容器不出网走代理，直连 PyPI 慢
- **CMD 用 JSON 数组格式**：Dockerfile 惯例

构建与运行：

```powershell
docker build -t myquotes .

# 加入 compose 自动创建的网络，用服务名访问 redis/mysql（容器里没有 localhost）
docker run --rm --network crawler-lab_default `
  -e MYSQL_PASSWORD=你的密码 `
  -e MYSQL_HOST=mysql `
  -e REDIS_URL=redis://redis:6379/0 `
  myquotes
```

**关键概念：容器里的 localhost 是它自己。** 要访问 compose 里的其他服务，必须加入同一张 Docker 网络，并用**服务名**当主机名——这正是 settings.py 里 `MYSQL_HOST`、`REDIS_URL` 都做成环境变量的原因：一份代码，宿主机/容器两种活法。

> 拉镜像超时/报 `failed to fetch anonymous token`：Docker 引擎不走系统代理，需在 Docker Desktop → Settings → Resources → Proxies 单独配置。

## 常见问题

| 现象 | 原因 | 解法 |
|---|---|---|
| redis-py 建连报错/断连 | redis-py 8.x 发 RESP3 `HELLO`，Redis 5 不支持 | 锁定 `redis==6.4.0` |
| `ModuleNotFoundError: myqoutes` | pytest 不在项目根执行 | cd 到 conftest.py 所在目录再跑 |
| 爬虫能跑但 MySQL 报连接拒绝 | 环境变量没生效 | `setx` 后必须重开终端；临时验证用 `$env:MYSQL_PASSWORD="..."` |
| 两个 worker 只有一个在干活 | 任务被先启动的 worker 抢完了 | 正常现象；任务池空了再 LPUSH 种子 |
| 容器里 quotes 表不存在 | initdb 目录的 SQL **只在数据卷首次初始化时执行**，后补的文件不会自动跑 | `docker cp` SQL 进容器，再 `mysql -e "source /tmp/xx.sql"` 手动执行 |
| SQL 过 PowerShell 管道执行报 `??????` 语法错 | PS 5.1 管道按 GBK 重新编码，SQL 里的中文注释乱码并破坏引号配对 | 别让字节穿 PowerShell 管道：`docker cp` + 容器内 `source` |
| 表的 COMMENT 注释显示乱码 | 建表时客户端编码不对，乱码已被写死进表定义 | `DROP TABLE` 后用正确编码（docker cp + source）重建；先确认表内无数据 |

更多真实踩坑记录见 [README](../README.md)。
