---
name: bdpan-cli
description: Use when managing files on Baidu Netdisk (百度网盘) using bdpan-cli, running CLI commands (ls, mkdir, mv, cp, rm, rename, search, tree, upload, download, dlink, ops, undo, auth, info, stats, mcp), querying account info and quotas (whoami, quota), executing reverse undo rollbacks, probing video metadata, or organizing and scraping movie media libraries with Scheme A standards.
---

# bdpan-cli 技能手册 (Baidu Pan CLI Operations & Media Management)

`bdpan-cli` 是基于百度网盘开放平台官方 OpenAPI 构建的生产级工程化网盘管理工具、影视媒体库整理系统及原生 MCP (Model Context Protocol) 服务的实现。
本技能指导智能体如何高效、安全地使用 `bdpan` CLI 进行网盘文件交互、断点续传上传/下载、秒传穿透、操作流水审计与逆向回滚、媒体深度元数据探测，以及对接 AI 智能体编排。

---

## 1. 运行环境、安装指示与执行规范

### 1.1 安装指示与审批红线 (MANDATORY APPROVAL GATE)
* **先探测后使用**：在使用前检测环境是否存在 `bdpan` 命令（或当前处于项目根目录使用 `uv run bdpan`）。
* ⛔ **严禁擅自安装**：若宿主系统中未找到 `bdpan` CLI（例如终端返回 `command not found: bdpan` 且当前目录非项目根目录），**绝对严禁智能体擅自、静默在后台执行 `uv tool install`、`pip install` 或下载二进制**！
* 🛑 **必须获得用户显式审批**：智能体必须立即暂停操作，如实向用户陈述“当前系统未安装 bdpan CLI 工具”，向用户提供安装选项（如 `uv tool install bdpan-cli`、`pip install bdpan-cli` 或使用 `uvx` 即用即走），并在**明确取得用户确认/审批授权后**方可执行安装或引导用户安装。
* **支持的安装方式**：
  - 推荐全局隔离安装：`uv tool install bdpan-cli`（更新使用 `uv tool upgrade bdpan-cli`）
  - 免安装即用即走：`uvx bdpan-cli <subcommand>`
  - 传统 pip 安装：`pip install bdpan-cli`
  - 源码开发模式：在项目根目录下执行 `uv sync`，随后通过 `uv run bdpan <subcommand>` 运行
  - 独立免环境二进制：从 [GitHub Releases](https://github.com/CodingRookie98/bdpan-cli/releases) 下载对应系统的单文件执行包

### 1.2 执行基线与安全规范
* **执行命令基线**：在项目根目录下通过 `uv run bdpan <subcommand>` 运行（或在全局安装环境下直接使用 `bdpan <subcommand>`）。
* **全局通用选项**：
  * `--account <alias>`：单次命令指定操作账号别名（支持多租户账号隔离并发操作）。
  * `--json`：所有核心查询命令均支持标准化 JSON 信封输出（`{"success": true, "code": 0, "data": ..., "error": null}`），便于脚本或流水线消费。
  * `--debug` / `-v`：开启详细调试日志（输出 HTTP 请求/响应细节与代码行号，控制台输出至 `stderr`，不污染 `stdout`）。
  * `--quiet` / `-q`：静音非错误输出（仅输出 `ERROR` 级别）。
* **认证凭据与日志持久化**：
  * 应用密钥配置于项目根目录 `.env` 或全局 `~/.config/bdpan/.env`（`BAIDU_APP_KEY`, `BAIDU_SECRET_KEY`）。
  * 授权 Token 遵循 XDG 规范自动保存在用户目录 `~/.config/bdpan/tokens.json`（权限 `0o600`，由 `TokenManager` 自动管理并在剩余不足 1 天时静默刷新；无缝自动兼容迁移旧版项目级 `.baidupan_tokens.json`）。
  * 运行日志持久化双写至 `~/.config/bdpan/logs/bdpan.log`（保留 5 个 10MB 轮转文件，完整保留 DEBUG 追踪细节）。
* **安全底线与审计防线**：
  * **只读先行与预演原则**：对网盘进行批量改名、移动或删除操作前，先通过只读命令（`ls`、`tree`、`scrape preview`、`--dry-run`）核对路径与影响范围。
  * **操作流水与逆向撤销**：所有关键重命名、移动、归集操作均自动原子落盘审计日志至 `.bdpan_ops/<op_id>.json`，支持通过 `bdpan undo <op_id>` 一键逆向回滚还原。
  * **删除确认守卫**：`rm` 默认具有交互确认；批处理中如需跳过确认需显式传递 `-y`；删除操作由网盘服务端移入回收站。

### 1.3 缺陷、Bug 与功能需求反馈规程 (Bug & Issue Escalation)
* **严格隔离，禁止擅自改码**：在 CLI 使用过程中如果发现缺陷、Bug、未捕获异常或功能缺失，严格遵守项目 `AGENTS.md` 军规，严禁私自修改 `src/bdpan_cli/` 源码进行“顺手修 Bug”或滥用 ad-hoc 脱轨脚本；
* 🛑 **汇报并给出选项**：立即暂停盲目试错，如实向用户客观陈述错误现场并提供 2~3 个具体变通或立项方案；
* 💡 **远端 Issue 提交流程提醒 (MANDATORY)**：向用户汇报缺陷或需求时，**必须主动提醒用户可以前往 GitHub 远端开源仓库提交 Issue** 进行追踪、建议与讨论：
  * **GitHub Issues 提交入口**：[https://github.com/CodingRookie98/bdpan-cli/issues](https://github.com/CodingRookie98/bdpan-cli/issues)
  * **建议汇报内容**：执行命令、完整 Traceback/报错信息、预期表现 vs 实际现象，以及操作系统/Python 环境版本。

---

## 2. CLI 命令速查表 (Cheat Sheet)

| 子命令 | 用途说明 | 核心参数与示例 |
|---|---|---|
| `ls` | 查看指定目录内容与条目详情 | `uv run bdpan ls /videos/movies [--limit 1000] [--json]` |
| `mkdir` | 创建新目录（幂等） | `uv run bdpan mkdir /videos/new_dir` |
| `mv` | 移动或移动改名（自动落盘操作流水） | `uv run bdpan mv /path/a /path/b /dest/` (多源)<br>`uv run bdpan mv /path/old /dest/new_name` (单源改名) |
| `cp` | 复制或复制改名 | `uv run bdpan cp /path/file.mkv /backup/` (每批 50 项保护) |
| `rename` | 原地重命名文件或目录（自动落盘操作流水） | `uv run bdpan rename /videos/movies new_movies` |
| `rm` | 删除文件或目录（移入网盘回收站） | `uv run bdpan rm /videos/junk.mkv [-y]` |
| `search` | 全盘或指定目录递归搜索 | `uv run bdpan search "阿凡达" [--dir /videos] [--no-recursion] [--json]` |
| `tree` | 递归目录树层级拓扑与本地索引 | `uv run bdpan tree /videos [--depth 2] [--index index.json]` |
| `upload` | 分片上传、断点续传与极速秒传 | `uv run bdpan upload ./local.mkv /videos/ [--overwrite]` |
| `download` | 大文件分块断点续传下载 | `uv run bdpan download /videos/movie.mkv [-d ./downloads] [--overwrite]` |
| `dlink` | 查询下载直链或导出多线程下载命令 | `uv run bdpan dlink /videos/movie.mkv [--aria2 \| --curl]` |
| `ops` | 查看操作审计流水日志 | `uv run bdpan ops list [--limit 20]`<br>`uv run bdpan ops show <op_id>` |
| `undo` | 逆向撤销历史批量操作回滚复原 | `uv run bdpan undo <op_id> [--dry-run] [-y]` |
| `auth` | 网盘账号凭证管理与多账号切换 | `uv run bdpan auth config --app-key <key> --secret-key <secret>`<br>`uv run bdpan auth config --show`<br>`uv run bdpan auth list`<br>`uv run bdpan auth switch <alias>`<br>`uv run bdpan auth login [--account <alias>]` |
| `info` | 探测视频媒体深度元数据（分辨率/编码/时长） | `uv run bdpan info /videos/movie.mkv [--json]` |
| `stats` | 递归聚合统计目录总容量与媒体格式分布 | `uv run bdpan stats /videos/movies [--depth N] [--json]` |
| `mcp` | 启动原生 Model Context Protocol Server (stdio) | `uv run bdpan mcp` |
| `dedup` | 冲突副本 `(1)/(2)` 治理与隔离清理 | `uv run bdpan dedup /videos [--staging-dir /videos/pending_delete] [--dry-run]` |
| `scrape foldering` | 散落媒体文件自动归集方案规范目录（支持自定义模板） | `uv run bdpan scrape foldering /videos/unscraped [--format "{title} ({year})"] [--dry-run]` |
| `scrape preview` | 电影目录方案更名预览（支持自定义模板） | `uv run bdpan scrape preview /videos/movies/unwatched [--format "{title}.{year}.{id}"]` |
| `scrape apply` | 批量应用刮削重命名映射 | `uv run bdpan scrape apply preview.json --target-dir /videos/movies` |
| `quota` | 查询网盘总容量、已用空间与到期时间 | `uv run bdpan quota [--check-expire] [--check-free] [--json]` |
| `whoami` | 查询当前网盘用户名与 VIP 等级 | `uv run bdpan whoami [--json]` |

* **全局通用选项**：
  * `-V`, `--version`：查看 CLI 工具当前版本号（如 `bdpan 0.3.0`）。
  * `--account <alias>`：指定当前命令所操作的网盘账号租户。
  * `--json`：以标准化 JSON 信封格式输出结果（结构化自动化消费）。
  * `-v`, `--verbose`, `--debug`：开启详细诊断调试日志（输出至 stderr，自动双写至 `~/.config/bdpan/logs/`）。
  * `-q`, `--quiet`：静音模式，仅保留 ERROR 级别输出。

---

## 3. 核心子系统与关键语义

### 3.1 路径解析与移动/复制双语义 (`mv` / `cp`)
`_resolve_dest` 解析规则：
1. **多源输入**：目标必须为已存在目录或以 `/` 结尾，所有源文件/目录保持原名迁入。
2. **单源输入**：
   * 若目标以 `/` 结尾，或目标在网盘上已存在且为目录，源文件保持原名移入/复制入内。
   * 若目标不存在或不以 `/` 结尾，将目标解析为 `目标目录/新名称`，实现移动/复制同时更名。
3. **批量保护**：复制与移动在底层自动切分为 **50 项/批**，避免因百度 OpenAPI 超时导致事务失败。

### 3.2 传输子系统：秒传、动态机房与断点下载
* **极速秒传与动态机房 (`upload`)**：
  * 在 `precreate` 阶段计算文件首片 256KB MD5 与全量 MD5 碰撞，若云端已存在相同特征（`return_type == 2`）直接极速秒传，消耗 0 流量。
  * 分片上传前自动调用 `locate_upload_host` 动态获取距离当前客户端网络物理延迟最低的最优服务器 host。
  * 断点续传通过 `.bdpan_uploads.json` 记忆 uploadid，支持中途意外断网或中断恢复。
* **分块断点下载与高速直链 (`download` / `dlink`)**：
  * 调用 OpenAPI 获取真实直链（`dlink`），强制注入 `User-Agent: pan.baidu.com` 请求头防 403 限速。
  * 下载器通过 `.tmp` 临时文件与 HTTP Range 协议分块传输，支持意外中断恢复；`dlink` 命令可一键输出适用于 `aria2c`（16线程）或 `curl` 的下载脚本。

### 3.3 安全运维：操作流水与逆向撤销 (`ops` & `undo`)
* 任何通过 `mv`、`rename` 执行的文件移动或更名均落盘至 `.bdpan_ops/<op_id>.json`（包含时间、账号、执行命令及源目的映射元组清单）。
* `bdpan undo <op_id>` 能够严格逆向计算出反向移动动作，支持 `--dry-run` 查看回滚方案；执行完成后标记状态为已撤销，防止重复回滚错乱。

### 3.4 媒体可观测性与目录统计 (`info` & `stats`)
* `bdpan info <file>`：提取视频真实宽高，自动归一化为行业标准标称（如 `3840x2160 (4K UHD)`、`1080P FHD`），输出精准时长（`HH:MM:SS`）、视频编码格式（HEVC/H.264/AV1）及音频轨道数量。
* `bdpan stats <dir>`：递归统计目录下总大小、总文件数、子目录数，并输出视频、字幕、海报图片等不同分类和常见扩展名的容量与占比。

### 3.5 AI 原生集成：Model Context Protocol (`mcp`)
* 纯净原生实现的标准 MCP Server，基于 `stdio` 运行 JSON-RPC 2.0 协议。
* 自省暴露 14 个网盘管理与观测工具，支持 Claude Code、Cursor、Antigravity 等主流 AI 编程助手直接编排调用。

### 3.6 电影刮削与媒体库整理规范 (`scrape`)
本项目媒体库默认遵循 **方案 A 规范目录名**：
```text
{中文译名}.{英文原名}.{上映年份}.{IMDb ID}[.{特别版本标识}]
例如: 超时空接触.Contact.1997.tt0118884
      白日梦想家.The.Secret.Life.of.Walter.Mitty.2013.tt0359950.Remux-BONZO
```
* **自定义命名模板 (`--format`)**：
  `preview` 与 `foldering` 命令支持传入 `--format` 自定义目录名占位符组合，未指定时默认保持方案 A 规范：
  - 可用字段：`{title}`（中文片名）、`{original_title}`（英文原名）、`{year}`（年份）、`{id}` / `{imdb_id}`（IMDb编号）、`{tmdb_id}`（TMDB编号）、`{edition}`（版本标识）。
  - 示例模板：
    - Plex 官方规范：`--format "{title} ({year}) {{imdb-{imdb_id}}}"` ➔ `黑客帝国 (1999) {imdb-tt0133093}`
    - 紧凑点号格式：`--format "{title}.{year}.{id}"` ➔ `黑客帝国.1999.tt0133093`
    - 常见中文年份：`--format "{title} ({year})"` ➔ `黑客帝国 (1999)`
* **元数据检索链路**：IMDb ID / 规范特征提取 ➔ TMDB API（zh-CN 优先，en-US 兜底）➔ 豆瓣候选建议补全中文片名。
* **工作流**：
  1. **散落文件归集**：使用 `bdpan scrape foldering /path/unscraped [--format "..."]` 将视频、外挂字幕与压缩包自动归集入规范新建目录中。
  2. **更名预演**：运行 `bdpan scrape preview <dir> --output preview.json [--format "..."]` 生成预演映射表供审阅。
  3. **确认应用**：审阅后运行 `bdpan scrape apply preview.json` 执行实际重命名。

---

## 4. 常见工作流指导 (Workflows)

### 场景一：检查网盘状态与配额
```bash
# 查询空间容量（支持 --json）
uv run bdpan quota

# 探测当前登录用户信息
uv run bdpan whoami

# 递归统计影视媒体库容量分布
uv run bdpan stats /videos/movies --depth 2
```

### 场景二：资源下载与高速直链提取
```bash
# 断点续传下载网盘大文件到本地 downloads 目录
uv run bdpan download /videos/movies/Inception.2010/Inception.mkv -d ./downloads/

# 提取高速直链并输出适用于 aria2c 的 16 线程下载命令
uv run bdpan dlink /videos/movies/Inception.2010/Inception.mkv --aria2
```

### 场景三：视频深度元数据探测
```bash
# 探测网盘内某部电影的画质编码与音轨详情
uv run bdpan info /videos/movies/Inception.2010/Inception.mkv
```

### 场景四：误操作审计与一键逆向撤销
```bash
# 1. 查看最近执行的操作审计流水
uv run bdpan ops list --limit 5

# 2. 预演撤销某次批量误移动/误重命名
uv run bdpan undo op_20261028_123456 --dry-run

# 3. 确认无误，执行一键还原
uv run bdpan undo op_20261028_123456 -y
```

### 场景五：开发者凭证配置、一键登录与多账号管理
```bash
# 1. 首次配置开发者凭据（写入全局 ~/.config/bdpan/.env，仅需配置一次）
uv run bdpan auth config --app-key YOUR_KEY --secret-key YOUR_SECRET

# 2. 授权登录当前账号（自动唤起默认浏览器并输出大字授权码）
uv run bdpan auth login

# 3. 查看本地保存的所有账号
uv run bdpan auth list

# 4. 切换当前默认活跃账号
uv run bdpan auth switch work

# 5. 单次命令临时使用备份账号执行，不影响当前默认账号
uv run bdpan --account backup ls /videos
```

### 场景六：AI 助手连接网盘 MCP
在 Claude Code、Cursor 或 Antigravity 中配置命令：
```bash
uv run --directory /path/to/bdpan-cli bdpan mcp
```
AI 助手将自动获取包含 `bdpan_ls`、`bdpan_info`、`bdpan_stats`、`bdpan_mv` 等 14 个工具，可直接对话指挥 AI 整理和运维网盘。

### 场景七：Python SDK 编程与代码内调用
当需要在自有 Python 脚本、Web 服务或数据管道中调用百度网盘时，无需通过 CLI 子进程，直接导入高层客户端：
```python
from bdpan_cli import BaiduPan

# 零配置自动初始化
pan = BaiduPan()

# 增删改查与分片断点续传
files = pan.list_dir("/影视/电影")
pan.upload("movie.mkv", remote_dir="/影视/电影")
pan.download("/影视/电影/Inception.mkv", dest_dir="./downloads")

# 媒体元数据与配额
info = pan.get_media_info("/影视/电影/Inception.mkv")
user = pan.whoami()
quota = pan.get_quota()
```
