# bdpan-cli 用户使用指南 (User Guide)

> 面向终端用户的全功能使用手册：从环境准备、密钥申请、授权登录，到文件操作、高速传输、影视刮削、安全撤销与 AI Agent 集成。

---

## 1. 快速上手与环境准备

### 1.1 系统与环境要求
- **操作系统**：Linux (Ubuntu/Debian/CentOS/Arch)、macOS (Apple Silicon & Intel) 或 Windows (x64)。
- **Python 环境**：Python >= 3.12（推荐搭配现代包管理器 [`uv`](https://github.com/astral-sh/uv)）。
- **免环境方式**：支持直接下载独立单文件可执行二进制包（无需安装任何 Python 运行时）。

### 1.2 安装方式

#### 方式一：uv tool 安装（强烈推荐，全局独立沙箱）
```bash
uv tool install bdpan-cli
```
安装后即可在终端直接执行 `bdpan` 命令。更新至最新版本：
```bash
uv tool upgrade bdpan-cli
```

#### 方式二：即用即走（无需预先安装）
```bash
uvx bdpan-cli --help
```

#### 方式三：传统 pip 安装
```bash
pip install bdpan-cli
```

#### 方式四：下载跨平台单文件二进制
访问 [GitHub Releases](https://github.com/CodingRookie98/bdpan-cli/releases)，根据您的操作系统下载对应的单文件执行包并赋予执行权限：
- Linux x86_64: `bdpan-linux-amd64`
- Linux ARM64: `bdpan-linux-arm64`
- macOS Apple Silicon: `bdpan-macos-arm64`
- macOS Intel: `bdpan-macos-x86_64`
- Windows: `bdpan-windows-amd64.exe`

#### 验证安装
安装完成后，可通过以下命令验证 CLI 工具是否就绪：
```bash
bdpan --version
# 输出: bdpan 0.1.0
```

---

## 2. 百度开放平台配置与账号授权

`bdpan-cli` 基于百度网盘官方开放平台 OpenAPI 构建，在使用前需要接入开发者凭证。

### 2.1 申请开发者凭据
1. 访问 [百度网盘开放平台控制台](https://pan.baidu.com/union/console/applist)；
2. 登录您的百度账号，创建应用并获取：
   - **AppKey**（对应客户端环境变量 `BAIDU_PAN_APP_KEY`）
   - **SecretKey**（对应客户端环境变量 `BAIDU_PAN_SECRET_KEY`）
   - **SignKey**（可选，开通签名时填写 `BAIDU_PAN_SIGN_KEY`）

### 2.2 本地凭证配置 (`.env`)
在项目或工作目录下复制 `.env.example` 为 `.env`：
```bash
cp .env.example .env
```
编辑 `.env` 填入您的密钥：
```ini
BAIDU_PAN_APP_KEY=your_actual_app_key
BAIDU_PAN_SECRET_KEY=your_actual_secret_key
BAIDU_PAN_SIGN_KEY=
```

### 2.3 账号首次登录授权
在配置好 `.env` 后，运行任一查询命令（如 `bdpan whoami` 或 `bdpan auth login`）：
- **桌面有头环境**：CLI 会自动在默认浏览器中打开百度授权页面，登录并确认授权后自动将 Token 凭据安全存储于遵循 XDG 规范的用户目录 `~/.config/bdpan/tokens.json`（权限 `0o600`，由 `TokenManager` 自动管理并在剩余不足 1 天时静默刷新）。
- **无头服务器/SSH 环境**：终端会输出完整的授权登录 URL。请在任意外部浏览器中打开该链接，登录授权完成后将浏览器地址栏跳转后的完整 URL 或 `code` 复制并粘贴回终端，即可完成绑定。
- **向下无缝兼容**：系统初次启动时，若检测到旧版项目根目录下的 `.baidupan_tokens.json`，会自动将其无缝迁移至 `~/.config/bdpan/tokens.json`。

---

## 3. 基础文件与目录管理

`bdpan-cli` 提供了一套贴近 POSIX 习惯的文件与目录操作指令，所有路径均以网盘根路径 `/` 起始。

### 3.1 浏览与查看 (`ls`, `tree`, `search`)
```bash
# 列出根目录内容
bdpan ls /

# 列出指定影视目录（单页最多返回 200 项）
bdpan ls /videos/movies --limit 200

# 递归查看目录树结构（限定遍历深度为 2 层）
bdpan tree /videos/movies --depth 2

# 递归扫描全树并保存为本地机器可读的 JSON 索引
bdpan tree /videos/movies --index /tmp/movies_index.json

# 按关键字搜索文件（限定在 /videos 目录下）
bdpan search "Matrix" --dir /videos
```

### 3.2 创建与组织 (`mkdir`, `mv`, `cp`, `rename`)
```bash
# 创建单个或多级新目录
bdpan mkdir /videos/movies/科幻

# 单文件/目录原地重命名
bdpan rename /videos/old_name.mkv new_name.mkv

# 单文件移动并重命名（当目标路径不存在时视为新路径名）
bdpan mv /videos/source.mkv /videos/movies/target.mkv

# 多文件批量归入已存在的目标目录
bdpan mv /videos/f1.mkv /videos/f2.mkv /videos/movies/科幻/

# 复制文件到新目录
bdpan cp /videos/source.mkv /backup/movies/
```

### 3.3 安全删除 (`rm`)
```bash
# 交互式删除（CLI 会逐项展示待删路径并提示确认）
bdpan rm /videos/temp.mp4

# 免交互确认强制删除（-y 跳过确认）
bdpan rm /videos/temp1.mp4 /videos/temp2.mp4 -y
```
> **安全机制**：网盘删除操作在云端由服务端移入“网盘回收站”，不会立即物理抹除数据，保障误删可恢复。

---

## 4. 高性能文件传输与直链提取

### 4.1 大文件切片上传与秒传 (`upload`)
`bdpan-cli` 实现了标准的预上传（`precreate`）➔ 分片上传（`superfile2`）➔ 云端合并（`create`）三阶段机制：
```bash
# 上传本地大文件至网盘指定目录
bdpan upload /local/path/Movie.2024.4K.mkv /videos/movies/

# 目标位置同名覆盖上传（默认会在冲突时自动重命名）
bdpan upload /local/path/Movie.2024.4K.mkv /videos/movies/ --overwrite
```
- **0 流量极速秒传**：上传前计算特征值，若服务端已存在相同文件，直接完成秒传，瞬间创建文件；
- **动态机房接入**：上传前动态向百度请求延时最低的最优机房 host 列表；
- **断点续传**：大文件中断后再次执行相同命令，会自动复用未过期的 `uploadid` 并补齐缺失分片。

### 4.2 断点续传下载 (`download`)
```bash
# 下载指定网盘文件到本地当前目录
bdpan download /videos/movies/Inception.mkv

# 下载多个文件并保存至指定本地目录
bdpan download /videos/movies/f1.mkv /videos/movies/f2.mkv -d ./downloads/

# 本地已存在同名文件时强制覆盖重新下载
bdpan download /videos/movies/Inception.mkv -d ./downloads/ --overwrite
```
- 下载时底层自动注入 `User-Agent: pan.baidu.com` 避免官方 HTTP 403 限速；
- 支持 HTTP Range 协议分块断点续传，未完成文件存储为 `.tmp`，下载校验完毕后原子重命名。

### 4.3 高速下载直链提取 (`dlink`)
```bash
# 查询单个网盘文件的真实高速直链与有效时长
bdpan dlink /videos/movies/Inception.mkv

# 导出适用于 aria2c 的 16 线程高速下载命令
bdpan dlink /videos/movies/Inception.mkv --aria2

# 导出适用于 curl 的断点续传脚本命令
bdpan dlink /videos/movies/Inception.mkv --curl
```

---

## 5. 影视媒体库规范刮削与整理系统

本项目针对个人云端媒体库提供自动化刮削与结构规整能力，完全契合 Kodi、Emby、Jellyfin 等播放器的识别规范。

### 5.1 方案 A 目录名规范
默认媒体库命名规范：
```text
{中文译名}.{英文原名}.{上映年份}.{IMDb ID}[.{特别版本标识}]
示例：黑客帝国.The.Matrix.1999.tt0133093
      指环王1：护戒使者.The.Lord.of.the.Rings.2001.tt0120737.Extended.Remux
```

### 5.2 媒体整理三步工作流

#### 第一步：散落媒体文件建目录归集 (`scrape foldering`)
将散落在非规范目录中的视频、外挂字幕（`.srt`/`.ass`/`.sub`/`.vtt`）自动识别并归集入独立的新建规范目录：
```bash
# 预演散落文件归集（不产生实际修改）
bdpan scrape foldering /videos/movies/unscraped --dry-run

# 正式执行归集与建立规范目录
bdpan scrape foldering /videos/movies/unscraped
```

#### 第二步：刮削更名预演 (`scrape preview`)
扫描目标目录，通过 TMDB 与豆瓣 API 匹配元数据，生成更名前后对照表：
```bash
bdpan scrape preview /videos/movies/unwatched -o preview.csv
```
生成的 `preview.csv` 清晰展示：原目录名 ➔ 规范新目录名 ➔ 匹配置信度与 IMDb 编号。

#### 第三步：批量应用更名 (`scrape apply`)
审阅 `preview.csv` 后，执行批量原子重命名：
```bash
bdpan scrape apply preview.csv --target-dir /videos/movies/unwatched
```

### 5.3 自定义命名模板 (`--format`)
`preview` 与 `foldering` 支持 `--format` 参数，允许用户自由定义目录结构：
- **可用占位符**：`{title}` (中文名), `{original_title}` (外文原名), `{year}` (年份), `{id}` / `{imdb_id}` (IMDb 编号), `{tmdb_id}` (TMDB 编号), `{edition}` (版本后缀)。
- **典型用法**：
  ```bash
  # Plex 官方推荐格式: Title (Year) {imdb-ttXXXXXXX}
  bdpan scrape foldering /videos/unscraped --format "{title} ({year}) {{imdb-{imdb_id}}}" --dry-run

  # 紧凑点号格式: Title.Year.ID
  bdpan scrape preview /videos/movies --format "{title}.{year}.{id}" -o preview.csv

  # 纯中文加年份格式
  bdpan scrape foldering /videos/unscraped --format "{title} ({year})"
  ```

---

## 6. 网盘冲突副本与重复治理 (`dedup`)

由于网盘同步客户端或多设备转存，常会在文件名后产生 `(1)`、`(2)` 等冲突副本。
```bash
# 预演扫描冲突副本与空目录
bdpan dedup /videos/movies --dry-run

# 将发现的冲突副本安全移动至隔离区，后续人工审阅
bdpan dedup /videos/movies --staging-dir /videos/quarantine

# 确认无误后直接将冗余副本移入回收站
bdpan dedup /videos/movies --delete
```

---

## 7. 安全运维审计与逆向撤销体系 (`ops`, `undo`)

为了防止批量重命名或误移动导致网盘拓扑混乱，`bdpan-cli` 引入了全量结构化审计与逆向回滚引擎。

### 7.1 查看操作流水 (`ops list`, `ops show`)
所有会修改网盘目录拓扑的命令（`mv`, `rename`, `scrape apply`, `scrape foldering` 等）均会自动在本地 `.bdpan_ops/<op_id>.json` 中记录原子流水：
```bash
# 查看最近 20 条变更流水
bdpan ops list

# 查看指定流水号的详细修改映射清单
bdpan ops show 20261029_095105_mv_7ac7a2
```

### 7.2 一键逆向回滚 (`undo`)
若某次批量移动或改名不符合预期，可通过流水号瞬间原样复原：
```bash
# 预演逆向回滚（核对原路径与新路径映射）
bdpan undo 20261029_095105_mv_7ac7a2 --dry-run

# 执行逆向回滚还原
bdpan undo 20261029_095105_mv_7ac7a2 -y
```

---

## 8. 多账号管理与多租户隔离 (`auth`)

支持在单机管理多个不同的百度网盘账号，互不干扰。

```bash
# 列出本地保存的所有账号别名与 Token 有效期
bdpan auth list

# 授权并登录新账号并指定别名
bdpan auth login --account work_pan

# 切换全局默认活跃账号
bdpan auth switch work_pan

# 在不切换默认账号的前提下，单次命令指定操作某一账号（多租户并发隔离）
bdpan --account personal_pan ls /photos
```

---

## 9. 媒体深度可观测性与全局 JSON 信封

### 9.1 视频元数据探测 (`info`)
无需下载庞大的视频文件，直接通过网盘多媒体接口提取文件内嵌元数据：
```bash
bdpan info /videos/movies/The.Matrix.1999.mkv
```
输出包含：
- **精确分辨率**：如 `3840x2160 (4K UHD)`、`1920x1080 (1080P FHD)`
- **时长**：精准格式化为 `HH:MM:SS`
- **视频编码**：识别 `HEVC (H.265)`、`H.264` 等主流编码
- **音轨信息**：内嵌音频流数与编码规格

### 9.2 目录聚合统计 (`stats`)
```bash
# 递归统计整个媒体库目录的总体积、文件数与分类占比
bdpan stats /videos/movies --depth 2
```

### 9.3 统一全局 JSON 信封 (`--json`)
所有核心查询命令均支持 `--json` 全局参数，输出结构一致的 JSON 字典，便于脚本与自动化运维系统消费：
```bash
bdpan --json whoami
bdpan --json quota
bdpan --json info /videos/movies/Inception.mkv
bdpan --json stats /videos/movies
```
响应格式遵循统一信封规范：
```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

### 9.4 诊断日志与调试模式 (`--debug`, `--quiet`)
`bdpan-cli` 实现了严格的控制台与日志流分离架构，控制台日志输出至 `sys.stderr`，确保 `sys.stdout` 的管道重定向与 `--json` 解析不受任何干扰。
```bash
# 开启详细诊断模式（输出底层 HTTP 请求头、响应体、模块名与行号）
bdpan --debug ls /videos/movies

# 静音模式（仅打印 ERROR 及以上级别异常，适合无交互定时任务）
bdpan -q quota

# 本地滚动日志文件
# 所有 DEBUG 级别完整调用明细会自动双写落盘至：
~/.config/bdpan/logs/bdpan.log  # (默认最大 10MB x 5 份自动轮转)
```


---

## 10. AI 原生集成：Model Context Protocol (MCP)

`bdpan-cli` 内置了纯原生、零外部重量级依赖的 MCP Server，使各类主流 AI 编程助手（如 Claude Code、Cursor、Google Antigravity 等）能够直接受控管理百度网盘资产。

### 10.1 启动 stdio 服务
```bash
bdpan mcp
```

### 10.2 在 Claude Code 中接入
在终端运行：
```bash
claude mcp add bdpan uv run bdpan mcp
```
或者在 `~/.claude.json` / Claude Desktop 配置中注册：
```json
{
  "mcpServers": {
    "bdpan": {
      "command": "uv",
      "args": ["run", "bdpan", "mcp"]
    }
  }
}
```
接入后，AI 即可直接调用 `bdpan_ls`、`bdpan_upload`、`bdpan_download`、`bdpan_info`、`bdpan_stats`、`bdpan_scrape_preview` 等 14 项完整工具。

---

## 11. 常见问题与排错 (FAQ)

### Q1: 运行命令时提示 `401 Unauthorized` 或 Token 过期？
**A**: `bdpan-cli` 内置了基于 `refresh_token` 的自动无感刷新机制。如果连续长时间未活跃导致 `refresh_token` 彻底失效，只需重新执行一次登录命令即可刷新授权：
```bash
bdpan auth login
```

### Q2: 批量移动或删除时是否会超过百度接口限制？
**A**: 百度 OpenAPI 规定批量接口单批次最大支持 50 项。`bdpan-cli` 底层 `FileManager.batch_move` 与 `batch_delete` 均内建了 50 项/批自动分块防护逻辑，并在每个分批返回后逐项校验 `errno`，确保部分失败时能够精准感知与安全处理。

### Q3: 为什么下载大文件时提示没有权限或速度受限？
**A**: 百度 OpenAPI 对下载直链有严格防盗链机制，必须携带百度指定的合法 `User-Agent`。`bdpan download` 与 `bdpan dlink` 已内置处理；如果使用导出的 `curl` 或 `aria2c` 脚本，请保持其自带的 `-U "pan.baidu.com"` 参数。

---

## 修订历史

| 版本 | 日期 | 变更摘要 |
|:---|:---|:---|
| V1.0.0 | 2026-10-29 | 首次发布全功能用户使用手册，涵盖环境、授权、基础命令、传输、影视刮削、安全撤销、多账号、可观测性与 MCP 集成 |
