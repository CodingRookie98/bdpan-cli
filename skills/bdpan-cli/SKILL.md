---
name: bdpan-cli
description: Use when managing files on Baidu Netdisk (百度网盘) using bdpan-cli, running CLI commands (ls, mkdir, mv, cp, rm, rename, search, tree, upload), querying account info and quotas (whoami, quota), or organizing and scraping movie media libraries with Scheme A standards.
---

# bdpan-cli 技能手册 (Baidu Pan CLI Operations & Media Management)

`bdpan-cli` 是基于百度网盘开放平台官方 Python SDK (`vendor/baidu-pan-sdk`) 开发的工程化网盘管理与媒体库整理工具。
本技能指导智能体如何高效、安全地使用 `bdpan` CLI 进行网盘文件交互、断点续传上传、目录树检索以及媒体库影视规范化刮削。

---

## 1. 运行环境与执行规范

* **执行命令基线**：在项目根目录下通过 `uv run bdpan <subcommand>` 运行（或在激活的 `.venv` 下直接使用 `bdpan <subcommand>`）。
* **别名兼容**：`bdpan`、`bdpan-cli`、`bd-net-disc-mgr` 三者为等价 CLI 入口。
* **认证凭据**：
  * 应用密钥配置于项目根目录 `.env`（`BAIDUPAN_APP_KEY`, `BAIDUPAN_APP_SECRET`）。
  * 授权 Token 自动缓存在 `.baidupan_tokens.json`，由 `TokenManager` 自动管理并在过期时静默刷新。
* **安全底线**：
  * 对网盘文件进行批量改名、移动或删除操作前，先通过只读命令（`ls`、`tree`、`scrape preview`、`--dry-run`）核对路径与影响范围。
  * `rm` 默认具有交互确认；脚本或批处理中如需静默执行需显式传递 `-y`。

---

## 2. CLI 命令速查表 (Cheat Sheet)

| 子命令 | 用途说明 | 核心参数与示例 |
|---|---|---|
| `ls` | 查看指定目录内容 | `uv run bdpan ls /videos/movies [--limit 1000]` |
| `mkdir` | 创建新目录（幂等） | `uv run bdpan mkdir /videos/new_dir` |
| `mv` | 移动或移动改名 | `uv run bdpan mv /path/a /path/b /dest/` (多源)<br>`uv run bdpan mv /path/old /dest/new_name` (单源改名) |
| `cp` | 复制或复制改名 | `uv run bdpan cp /path/file.mkv /backup/` (每批 50 项) |
| `rename` | 原地重命名文件或目录 | `uv run bdpan rename /videos/movies new_movies` |
| `rm` | 删除文件或目录（移入回收站） | `uv run bdpan rm /videos/junk.mkv [-y]` |
| `search` | 全盘或指定目录搜索 | `uv run bdpan search "阿凡达" [--dir /videos] [--no-recursion]` |
| `tree` | 递归目录树与本地索引 | `uv run bdpan tree /videos [--depth 2] [--index index.json]` |
| `upload` | 分片上传与断点续传 | `uv run bdpan upload ./local.mkv /videos/ [--overwrite]` |
| `quota` | 查询网盘容量与到期日 | `uv run bdpan quota [--check-expire] [--check-free]` |
| `whoami` | 查询网盘用户信息与 VIP 状态 | `uv run bdpan whoami` |
| `scrape preview` | 电影目录方案 A 刮削更名预览 | `uv run bdpan scrape preview /videos/movies/unwatched` |
| `scrape apply` | 批量应用刮削重命名映射 | `uv run bdpan scrape apply preview.json --target-dir /videos/movies` |
| `scrape foldering` | 散落媒体文件自动归集规范目录 | `uv run bdpan scrape foldering /videos/unscraped [--dry-run]` |

---

## 3. 核心功能与关键语义

### 3.1 路径解析与移动/复制双语义 (`mv` / `cp`)
`_resolve_dest` 解析规则：
1. **多源输入**：目标必须为已存在目录或以 `/` 结尾，所有源文件/目录保持原名迁入。
2. **单源输入**：
   * 若目标以 `/` 结尾，或目标在网盘上已存在且为目录，源文件保持原名移入/复制入内。
   * 若目标不存在或不以 `/` 结尾，将目标解析为 `目标目录/新名称`，实现移动/复制同时更名。
3. **批量保护**：复制与移动在底层自动切分为 **50 项/批**，避免因百度 OpenAPI 超时导致事务失败。

### 3.2 目录树与本地索引 (`tree`)
* 由于百度网盘 OpenAPI 的 `xpanfilelistall` 受应用权限约束（返回 `errno=20020`），`tree` 命令采用**客户端深度优先递归 (`walk`)**。
* 支持通过 `--depth N` 限制遍历深度。
* 支持通过 `--index <output.json>` 将整棵目录树元数据（大小、fs_id、修改时间、目录拓扑）持久化为本地离线 JSON 索引。

### 3.3 大文件分片上传与断点续传 (`upload`)
* 采用 4MB 分片分段上传逻辑：
  1. `precreate`：计算全量 MD5 及分片 MD5，向网盘申请 `uploadid`。
  2. `upload_slice`：校验本地续传记录 `.bdpan_uploads.json`，仅上传云端缺失分片。
  3. `create`：合并分片创建文件。
* 覆盖选项：`--overwrite` 对应网盘 `rtype=3`（覆盖同名文件）；默认为 `rtype=1`（同名自动追加序号，如 `filename(1).mkv`）。

### 3.4 电影刮削与媒体库整理规范 (`scrape`)
本项目媒体库遵循 **方案 A 规范目录名**：
```text
{中文译名}.{英文原名}.{上映年份}.{IMDb ID}[.{特别版本标识}]
例如: 超时空接触.Contact.1997.tt0118884
      白日梦想家.The.Secret.Life.of.Walter.Mitty.2013.tt0359950.Remux-BONZO
```

* **元数据检索链路**：IMDb ID / 规范特征提取 ➔ TMDB API（zh-CN 优先，en-US 兜底）➔ 豆瓣候选建议补全中文片名。
* **工作流**：
  1. **散落文件归集**：使用 `bdpan scrape foldering /path/unscraped` 将视频、外挂字幕与压缩包自动归集入方案 A 规范新建目录中。
  2. **更名预演**：运行 `bdpan scrape preview <dir> --output preview.json` 生成预演映射表供审阅。
  3. **确认应用**：审阅后运行 `bdpan scrape apply preview.json` 执行实际重命名。

---

## 4. 常见工作流指导 (Workflows)

### 场景一：检查目录结构与空间
```bash
# 查看网盘剩余空间
uv run bdpan quota

# 列出媒体库顶级目录
uv run bdpan ls /videos/movies

# 导出电影目录离线索引以便快速检索
uv run bdpan tree /videos/movies --depth 2 --index movies_index.json
```

### 场景二：上传新下载的影视资源
```bash
# 断点续传上传本地 MKV 文件到网盘收件箱
uv run bdpan upload /path/to/Interstellar.2014.2160p.mkv /videos/movies/unscraped/

# 查看收件箱
uv run bdpan ls /videos/movies/unscraped
```

### 场景三：归集并规范化收件箱电影
```bash
# 1. 预演散落文件建目录归集方案
uv run bdpan scrape foldering /videos/movies/unscraped --dry-run

# 2. 确认无误后执行归集
uv run bdpan scrape foldering /videos/movies/unscraped

# 3. 将归集好的电影目录移入待看/已看目录
uv run bdpan mv /videos/movies/unscraped/星际穿越.Interstellar.2014.tt0816692 /videos/movies/unwatched/
```

---

## 5. 故障排查与技术限制 (Gotchas & Troubleshooting)

1. **不存在路径返回空列表**：
   * 百度 OpenAPI `xpanfilelist` 在路径不存在时不抛异常，而是返回空列表 `[]`。
   * 判断目录是否真正存在时，应检查其父目录的条目列表中是否包含该名称。
2. **批量操作批大小上限 (50)**：
   * 网盘重命名、复制、移动 API 对单次请求 items 数量有限制，超过 50 个容易引发超时或网关截断。`FileManager` 已内建批大小切分，调用 SDK 底层接口时请勿单批超过 50。
3. **软删除语义 (`rm`)**：
   * `rm` 操作实际上将网盘条目移入百度网盘「回收站」，不会立即彻底物理擦除，仍可在网页端回收站恢复。
4. **Token 缓存与刷新**：
   * 若遇到授权过期或 401 报错，检查 `.env` 配置，或删除 `.baidupan_tokens.json` 后重新触发鉴权。
