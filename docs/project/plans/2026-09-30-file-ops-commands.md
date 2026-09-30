# CLI 文件操作命令补齐（cp/rm/rename + mv 语义修复）实施计划

> **文档控制信息**
> - **文档标识**: PLAN-FILEOPS-2026
> - **当前版本**: V1.0.0
> - **文档所有者**: 主调度智能体
> - **生效日期**: 2026-09-30

> **目标元数据**
> - **所属项目**: bdpan-cli
> - **执行通道**: Heavy Track（契约扩展期：新增对外 CLI 命令；P0.5 豁免——复用 vendored SDK 既有 `filemanagercopy`，无新依赖；P0 豁免——不涉及并发竞态/分布式状态/核心数据流改造，破坏性操作安全性由 `rm` 确认机制显式设计覆盖）
> - **目标简述**: 补齐网盘文件操作命令 `cp`/`rm`/`rename`，并修复 `mv` 无法"移动并改名"的语义缺陷，使 CLI 具备对标 POSIX 的基础文件管理能力
> - **创建日期**: 2026-09-30
> - **计划负责人**: 主调度智能体（goal-loop）
> - **需求方**: 用户（项目所有者）
> - **批准人 (User Nod)**: 用户 | **批准时间**: 2026-09-30（方案 A 最小补齐 + 当前会话内联执行）
> - **批准基线**: main@`dbf193a`
> - **状态**: 已完成 [已完成]
> - **隔离分支**: `feature/file-ops-commands`
> - **技术调研备忘录**: [豁免: P0.5 豁免——直接复用 vendored SDK 既有 `filemanagercopy` 接口，无选型裁决需求]
> - **临时 Scratchpad**: `.goal-loop/scratchpad.md`（已被 `.gitignore` 忽略）

> **唯一可读真相源声明**：本文件是当前目标的唯一人类可读真相源。本文件的复选框与下方检查点锚点必须与机器状态保持一致。

---

## 🚀 活跃执行状态与持久化检查点 (Active Checkpoint)
- **当前执行通道**: Heavy Track
- **当前活跃阶段**: P3.6 L2 集成验证（进行中）
- **当前活跃子任务**: 无
- **当前子任务重试计数**: 0/3
- **外层循环迭代**: 0/5
- **最后一次验证状态**: Exit Code 0, 42 passed（P3.0–P3.5 全部完成并原子提交；L2 沙箱实测发现 dest 探测缺陷，转入 P3.2b）
- **最新有效提交**: P3.5 mv 语义修复提交（见 git log）
- **阻断原因**: 无
- **派发账本**: `.goal-loop/dispatch-ledger.md`（当前在途派发：无）

### P3.6 实测缺陷记录（2026-09-30）
- **现象**: 真网盘执行 `cp /bdpan-cli-devtest/src-movie /bdpan-cli-devtest/renamed-copy`（目标不存在）实际复制为 `renamed-copy/src-movie`，未按"目录/新名"改名复制。
- **根因**: 百度 `xpanfilelist` 对不存在的目录返回空列表而非错误，`_resolve_dest` 以"list_dir(dest) 抛错"判定"dest 非目录"失效。
- **修复方案**: 改为探测 dest 的**父目录**列表，按条目 `path` + `isdir==1` 精确匹配判定"dest 是已存在目录"；父目录列表失败时交由后续 copy/move 在服务端报错。不新增 FileManager 契约。

---

## 1. 目标范围与验收基线 (Scope & Acceptance Baseline)

### 1.0 验收口径 (Acceptance Criteria — 由需求方定义)
- **验收人**: 用户（项目所有者）
- **验收场景**:
  1. `bdpan cp <src> <dest>`：dest 为已存在目录（或以 `/` 结尾）→ 复制入内并保持原名；否则按 `目录/新名` 复制并改名；
  2. `bdpan rm <path>... [-y]`：删除一个或多个路径，默认列出目标并交互确认，`-y` 跳过确认；
  3. `bdpan rename <path> <new_name>`：原地改名；
  4. `bdpan mv <src> <dest>`：修复语义——dest 为已存在目录 → 移入保名（向后兼容）；否则 → 移动并改名（修复现状缺陷）；
  5. 上述命令在真网盘沙箱 `/bdpan-cli-devtest/` 全链路实测通过，测后清理干净（用户已授权该测试目录）。
- **明确不验收项**: 多源批量参数（`cp a b dir`）、`search`/`tree`/回收站命令（属方案 B/C 范围，本轮不做）；`meta` 子系统不在本轮。
- **口径冲突裁决人**: 用户。

### 1.1 核心交付物清单
- [ ] 核心模块新增/修改: `src/bdpan_cli/file_manager.py`（copy/batch_copy）、`src/bdpan_cli/cli.py`（cp/rm/rename + mv 修复）
- [ ] 自动化测试用例: `tests/test_file_manager.py`、`tests/test_cli.py` 扩展
- [ ] 关联技术与用户文档: `README.md`、`docs/index.md`、`docs/project/changelog.md`、`docs/project/backlog.md`、`docs/reference/api/baidu-pan-sdk.md`（新增调用接口须同步第 3 节代码映射）、`docs/GOVERNANCE.md`（目录职责表补 `project/plans/`）、`docs/llms.txt`（重生成）

### 1.2 依赖选型与开源调研结论 (Research & Feasibility Spike)
- **P0.5 备忘录**: [豁免] 复用 vendored SDK `openapi_client.api.filemanager_api.FilemanagerApi.filemanagercopy(access_token, _async, filelist, ondup=...)`（`vendor/baidu-pan-sdk/openapi_client/api/filemanager_api.py:322`），payload 与 `filemanagermove` 同构：`[{"path": src, "dest": dest_dir, "newname": name}]`
- **开源复用/自研裁决**: 复用既有封装（vendored SDK + 既有 `FileManager` 批处理惯例）
- **API 权威契约与版本验证**: baidu-pan-sdk 1.0.0（vendored, editable）；`_async=0` 同步模式与既有 rename/move 用法一致

### 1.3 严禁事项与反模式 (Strict Exclusions)
- 严禁修改 scrape/meta 等不在本轮范围的模块与公共契约；
- 严禁未跑全量测试直接提交代码；
- 严禁引入新技术栈清单外的第三方库（不加 linter/类型检查器，L0 用 `python -m compileall`）；
- 严禁在真网盘测试时触碰 `/bdpan-cli-devtest/` 以外路径；rm 命令必须保留确认机制。

---

## 2. 测试策略与级别裁定 (Test Scope Determination)

> 依据 `testing-decision-matrix.md` 4 步推理：改动涉及公共 CLI 契约扩展（新增命令）+ 破坏性命令引入 → 风险 MEDIUM；`FileManager` 被 cli/scrape 全链路依赖（骨干节点）→ 触发 L2；运行时跨网络边界（真网盘 I/O）→ 必须 L2 真实装配验证；CLI 操作者可直接观测行为 → 纳入 L2 沙箱全链路（替代独立 L3 框架）。

- **改动风险定级**: MEDIUM
- **强制执行测试级别**:
  - [x] **L0 静态代码门禁**: `uv run python -m compileall src tests`（项目无 lint/类型检查器配置，不新引入）
  - [x] **L1 单元测试**: `uv run pytest`（全量整套件，当前基线 28 passed，先红后绿）
  - [x] **L2 模块集成测试**: 真网盘沙箱 `/bdpan-cli-devtest/` 全链路实测（mkdir→cp→rename→mv→rm + 逐步 `ls` 对账 + 测后清理），符合本项目"live verification is part of tested"惯例
- **豁免测试级别与充分依据**: 豁免独立 L3 E2E 框架——本项目无 E2E 测试设施；L2 沙箱实测直接经 CLI 主入口驱动全部新命令，已覆盖"用户主干交互链路"验证目标，无额外增量信息。
- **精确验证命令清单**:
  ```bash
  # L0 静态语法检查
  uv run python -m compileall -q src tests
  # L1 单元测试（全量）
  uv run pytest -q
  # L2 集成验证（真网盘沙箱，命令清单见 Task P3.6）
  uv run bdpan mkdir /bdpan-cli-devtest/src-movie  # ...全链路
  # 文档门禁（P5）
  python3 .agents/skills/doc-governance/scripts/check-doc-links.py --root docs
  python3 .agents/skills/doc-governance/scripts/trim-revision.py --root docs --fix --keep 5
  python3 .agents/skills/doc-governance/scripts/generate-llms-txt.py --root docs --output docs/llms.txt
  ```

---

## 3. 分阶段实施与子任务清单 (Phased Implementation & Tasks)

### P3 准备: 隔离分支与环境前置检查
- [x] **Task P3.0**: 创建功能分支 `feature/file-ops-commands`（基线 main@`dbf193a`）、基线测试确认 28 passed、修复 `uv run pytest` console script 失效（`.venv` 自旧项目目录迁移残留）、`.gitignore` 补 `.goal-loop/`
  - **验收方式**: `uv run pytest -q` → 28 passed, Exit Code 0 ✅

### P3: 核心功能原子实现 (TDD 循环)
- [x] **Task P3.1**: `FileManager.copy` / `FileManager.batch_copy` 原语（payload 与 batch_move 同构，50/批防超时惯例，`_async=0`，errno 校验与错误包装一致）— 提交 `865edc9`
  - **涉及文件**: `src/bdpan_cli/file_manager.py`, `tests/test_file_manager.py`
  - **TDD 步骤**: 🔴 失败单测（copy 成功 payload / copy 错误 / batch_copy 105 项 3 批）➔ 🟢 最简实现 ➔ ✅ 全量测试 ➔ 💾 原子提交
  - **验收命令**: `uv run pytest -q`
- [x] **Task P3.2**: CLI `cp` 命令 + dest 消歧助手 `_resolve_dest`（已存在目录→入内保名；`/` 结尾→入内保名；否则→`dirname/basename` 改名复制）
  - **涉及文件**: `src/bdpan_cli/cli.py`, `tests/test_cli.py`
  - **TDD 步骤**: 🔴 失败单测（入内/改名/尾斜杠/list_dir 失败回退）➔ 🟢 ➔ ✅ ➔ 💾 原子提交
  - **验收命令**: `uv run pytest -q`
- [x] **Task P3.3**: CLI `rm` 命令（多路径、默认交互确认、`-y/--yes` 跳过；确认取消时退出码 0 且不调用 delete；删除失败返回 1）
  - **涉及文件**: `src/bdpan_cli/cli.py`, `tests/test_cli.py`
  - **TDD 步骤**: 🔴 失败单测（-y 直删/确认 y/确认 n/失败退出码）➔ 🟢 ➔ ✅ ➔ 💾 原子提交
  - **验收命令**: `uv run pytest -q`
- [x] **Task P3.4**: CLI `rename` 命令（`rename <path> <new_name>` → `mgr.rename`）
  - **涉及文件**: `src/bdpan_cli/cli.py`, `tests/test_cli.py`
  - **TDD 步骤**: 🔴 失败单测 ➔ 🟢 ➔ ✅ ➔ 💾 原子提交
  - **验收命令**: `uv run pytest -q`
- [x] **Task P3.5**: `mv` 语义修复（复用 `_resolve_dest`；dest 已存在目录 → 移入保名向后兼容；否则移动并改名）
  - **涉及文件**: `src/bdpan_cli/cli.py`, `tests/test_cli.py`
  - **TDD 步骤**: 🔴 失败单测（dest 全路径改名移动/尾斜杠/既有测试回归）➔ 🟢 ➔ ✅ ➔ 💾 原子提交
  - **验收命令**: `uv run pytest -q`

### P3.5→P3.6: 集成验证（真网盘沙箱，用户已授权 `/bdpan-cli-devtest/`）
- [x] **Task P3.2b**: （L2 实测发现缺陷修复）`_resolve_dest` 存在性探测改为父目录列表 + `path`/`isdir` 精确匹配；更新 cp/mv 测试夹具并新增"目标不存在→改名复制"回归测试
  - **涉及文件**: `src/bdpan_cli/cli.py`, `tests/test_cli.py`
  - **TDD 步骤**: 🔴 失败单测（新探测契约）➔ 🟢 修复 ➔ ✅ 全量 ➔ 💾 原子提交
  - **验收命令**: `uv run pytest -q`
- [x] **Task P3.6**: L2 全链路实测：`mkdir` 建沙箱双目录 → `cp` 入目录与改名复制 → `rename` → `mv` 入目录与移动改名 → 每步 `ls` 对账 → `rm -y` 清理沙箱 → 根目录确认无残留；输出证据记入 Scratchpad 与提交事实
  - **验收命令**: 见 Scratchpad 实测清单；全部 Exit Code 0 且对账守恒

### P4: 双轮对抗终审与再循环闭环硬门禁 (Dual-Round Review & Re-Loop Gate)
- [x] **Task P4.1**: 调用 `dual-round-review`：R1 红队子智能体（Diff 边界锁 `dbf193a..b799fe3`）→ R2 元架构师审判；派发账本记录于 `.goal-loop/dispatch-ledger.md`
  - **结果**: R1（agent_a12050fb）候选 P2×3/P3×11、无 P0/P1；R2（agent_f78549eb）逐条裁定：Blockers=0，Suggestion×4（RT-01/02/03/10 记入 backlog），驳回×10（含边界越界拦截 RT-11..14）
  - **验收标准**: 独立子智能体终审裁决明细表 ✅（`.review-context/review-dbf193a.md`）
- [x] **Task P4.2**: （条件）阻断项修复与 Delta Re-Loop 再循环 —— 未触发（Blockers=0，一次通过）
- [x] **Task P4.3**: Zero Blockers 裁决后合并 `feature/file-ops-commands` → `main`，删除临时分支

### P5: 文档全向归档与联动升级
- [x] **Task P5.1**: 文档联动：README 命令清单、`docs/reference/api/baidu-pan-sdk.md` 第 3 节代码映射（新增 filemanagercopy 封装）、`docs/project/changelog.md` 追加、`docs/project/backlog.md` 对应项闭环、`docs/GOVERNANCE.md` 目录职责表补 `project/plans/`、`docs/index.md` 核对、重生成 `docs/llms.txt`、三门禁 Exit Code 0
- [ ] **Task P5.2**: 本计划状态标记 `[已完成]`，沉淀最终执行总结
- [ ] **Task P5.3**: (可选) 触发 `doc-governance` 技能工作流

---

## 4. 研究发现与环境状态记录 (Context Log)

- **[2026-09-30] 探查 1**: vendored SDK `filemanagercopy` 位于 `filemanager_api.py:322`，签名 `(access_token, _async, filelist, ondup=可选)`；`FileManager.delete()` 已实现但无 CLI 入口；`cmd_mv` 固定以源 basename 为 newname，无法移动改名。
- **[2026-09-30] 探查 2**: `.venv` 系旧项目目录迁移残留（含 `bd-net-disc-mgr`/`hindsight-zcode` 旧安装），`uv run pytest` console script 失效；`uv sync --reinstall-package pytest` 修复后 `uv run pytest` 28 passed。规范测试命令：`uv run pytest`。
- **[2026-09-30] 探查 3**: 真网盘测试无需上传能力——所有新命令验证均可用目录对象完成（copy/rename/mv/delete 对目录有效），L2 沙箱方案成立。

---

## 5. 修订历史 (Revision History)
- **[2026-09-30]**: 计划完成归档。P3 全任务（P3.0–P3.6 含 L2 实测缺陷修复 P3.2b）原子提交；L2 真网盘沙箱全链路通过并清理；P4 双轮审查一次通过（R2 终审 Blockers=0）；P5 文档四门禁全绿；合并回 main。
- **[2026-09-30]**: 计划创建（P-1 方案 A 获 User Nod；P0.5/P0 豁免理由已记录）。
