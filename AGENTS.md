# bdpan-cli Agent Rules & Guidelines

> 本文件是当前项目（`bdpan-cli`）的最高优先级 Agent 行为指引与项目级约束。全局通用规则遵循系统全局设定，当项目特性与通用习惯冲突时，**以本文件为准**。

---

## 1. ⚡ 核心红线：CLI 工具缺陷、Bug 与功能需求确认机制 (MANDATORY)

在使用或维护 `bdpan-cli` 的过程中，**严格禁止智能体擅自越权扩充任务范围或私自修改 CLI 源码**。

### 1.1 触发场景
智能体在使用 `bdpan` CLI 命令（如 `ls`、`mv`、`cp`、`rm`、`tree`、`upload`、`dedup`、`scrape` 等）执行网盘运维、媒体整理、批量操作，或在运行与测试过程中，如果发现：
1. **缺陷与 Bug (Defects/Bugs)**：CLI 工具抛出未捕获异常、参数解析异常、API 边缘情况处理错误、状态输出与实际行为不一致、静默失败等；
2. **功能需求缺失 (Feature Requests)**：CLI 工具缺少必要命令、缺少关键参数或过滤能力、无法满足当前处理场景的特定边界条件等；
3. **行为/契约不符 (Contract Inconsistencies)**：实际运行结果偏离帮助文档、命令手册或预期契约。

### 1.2 行为军规 (Strict Invariants)
- ⛔ **严禁擅自修改源码**：绝对禁止未向用户汇报即私自修改 `src/bdpan_cli/` 源码进行“顺手修 Bug”或“随手加功能”；
- ⛔ **严禁上下文偷渡**：当前用户委托的任务（如媒体整理、网盘清理、数据统计等）与 CLI 工具自身的开发维护任务严格隔离，不得偷换核心任务；
- ⛔ **严禁隐瞒或滥用 ad-hoc 脚本**：发现工具缺陷不得装作没看见跳过，也不得私下编写一次性脱轨脚本绕过而不做反馈。

### 1.3 处理规程 (Action Protocol: 3-Step)
遇到上述缺陷、Bug 或功能缺失时，必须严格执行以下三步闭环：

1. 🛑 **HALT（暂停动作）**：
   立即停止在 CLI 源码上的修改意图，保留当前环境现场与报错上下文。
2. 📋 **REPORT & OPTIONS（汇报并给出选项）**：
   向用户清晰陈述发现的现象，结构化说明：
   - **问题/需求现象**：触发命令、具体报错、预期行为 vs 实际表现；
   - **根因初步分析**：是代码缺陷、网盘 API 限制，还是特性缺失；
   - **提供 2~3 个具体可行方案**供用户抉择，典型选项：
     - **选项 A（记录待办，变通推进）**：将该缺陷/需求登记入 `docs/project/backlog.md`，当前任务采用稳定参数或手动方式继续完成；
     - **选项 B（立即立项修复/开发）**：挂起当前主任务，切换至 CLI 研发流程，经需求澄清与 TDD 修复/实现并补充单元测试；
     - **选项 C（维持现状/终止操作）**：若风险不可控或成本过高，说明影响并听取用户进一步指示。
   - **主动提醒远端 Issue 反馈**：在向用户汇报时，主动提醒用户可以向开源远端仓库提交 Issue 进行追踪或建议（https://github.com/CodingRookie98/bdpan-cli/issues）。
3. ✅ **CONFIRM BEFORE ACTION（确认后再行动）**：
   **必须取得用户的明确确认或决策答复后**，方可开展对应的修复、实现或记录工作。

---

## 2. 网盘操作与安全底线 (Safety & Netdisk Protection)

本项目涉及对百度网盘线上资产的变更与操作，必须时刻遵循数据安全防线：

- **只读先行与预演原则 (Preview, Then Apply)**：
  - 对网盘文件进行批量改名、移动、去重或删除前，必须先使用只读命令（`ls`、`tree`）、预演命令（`bdpan scrape preview`）或 `--dry-run` 选项输出清单；
  - 严禁在未经过预演核对的情况下直接执行破坏性网盘操作。
- **资产严格守恒与对账 (Conservation Accounting)**：
  - 文件归集、更名与目录拓扑调整前后，必须通过对账统计核验（文件总数、目录结构）保持 100% 守恒，确保零遗留、零丢失。
- **50 项/批保护上限**：
  - 底层调用百度 OpenAPI 批量移动、复制、删除接口时，必须遵守单批次最大 50 项的限制，防止接口超时导致部分提交失败。
- **凭证与配置隔离**：
  - 开放平台密钥由 `.env` 管理，授权凭据缓存在 `.baidupan_tokens.json`，均受 `.gitignore` 保护，严禁提交或泄露。

---

## 3. 工程与开发规范 (Engineering Standards)

当经用户确认进入 CLI 研发、修复或测试流程时，必须遵循以下工程规范：

- **运行环境**：Python >= 3.12，包管理统一使用 `uv`。
  - 依赖安装：`uv sync`
  - CLI 执行：`uv run bdpan <subcommand>`
- **测试驱动 (TDD) 与全绿门禁**：
  - 任何 Bug 修复与新特性必须配备单元测试（`tests/test_<module>.py`）；
  - 提交前必须保证全量测试套件通过：`uv run pytest`（Exit Code 0，测试数量只增不减）；
  - 测试断言必须严谨，严禁弱化断言迎合实现。
- **文档与治理联动 (Docs-as-Code)**：
  - 遵循 `docs/GOVERNANCE.md` 与 Diátaxis 架构；
  - 涉及命令、参数或 SDK 适配变更时，必须同步更新 `README.md`、`docs/project/changelog.md`、`skills/bdpan-cli/SKILL.md` 等对应文档；
  - 提交前运行文档门禁脚本验证（零断链、健康度合格）：
    ```bash
    python3 .agents/skills/doc-governance/scripts/check-doc-links.py --root docs
    python3 .agents/skills/doc-governance/scripts/generate-llms-txt.py --root docs --output docs/llms.txt
    ```
- **原子提交规范**：
  - 遵循 Conventional Commits 标准（`feat(cli): ...`, `fix(scraper): ...`, `docs: ...`）；
  - 提交信息正文中须记录实际验证结果与退出状态码。
