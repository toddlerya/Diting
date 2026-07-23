# AGENTS.md - Diting (谛听) 项目开发规范与智能体指南

> **Diting (谛听)** 是一个面向 Agent Runtime 的可重复、可评测、可扩展的分布式系统状态仿真与评估平台 (AgentBench ASSEP)。
> 
> 本文档定义了 Diting 项目的技术栈约束、虚拟环境管理、代码质量检查与编码规范。所有开发者与 AI Agent 在参与本项目的开发、重构或修 Bug 时，均必须严格遵守以下约定。

---

## 🛠️ 技术栈与管理工具

Diting 项目强制采用现代化 Python 基础设施规范：

* **Python 版本**: `>= 3.13`（指定为 `.python-version` 与 `pyproject.toml` 中的基础版本）。
* **虚拟环境与包管理**: 统一使用 [**`uv`**](https://github.com/astral-sh/uv)。
* **镜像加速源**: 统一使用阿里云 PyPI 镜像源 `https://mirrors.aliyun.com/pypi/simple/`。
* **代码 Lint & 格式化**: 统一使用 [**`ruff`**](https://github.com/astral-sh/ruff)。
* **单元测试框架**: 统一使用 **`pytest`**。

---

## 🐍 Python 虚拟环境与依赖管理 (`uv`)

### 1. 环境初始化与版本管理
项目目录下已配置 `.python-version`。切换或固定 Python 版本：
```bash
uv python pin 3.13
```

创建虚拟环境：
```bash
uv venv
```

### 2. PyPI 镜像源设置
推荐配置环境变量或在 `uv` 执行时指定镜像源：
```bash
# 环境变量（推荐放入 ~/.bashrc 或 shell 环境中）
export UV_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/"

# 或在安装/同步时显式指定
uv sync --index-url https://mirrors.aliyun.com/pypi/simple/
```

### 3. 依赖同步与管理
在修改 `pyproject.toml` 后，同步安装虚拟环境依赖：
```bash
uv sync
```

添加或移除依赖库：
```bash
# 添加生产依赖
uv add <package_name>

# 添加开发/测试依赖
uv add --dev <package_name>

# 移除依赖
uv remove <package_name>
```

### 4. 指令安全执行 (`uv run`)
**重要规约**：所有 Python 脚本、测试命令与 CLI 工具必须使用 `uv run` 引导执行，以保证始终运行在隔离的虚拟环境中：
```bash
# 运行 demo 仿真脚本
uv run python run_simulator_demo.py

# 执行单元测试
uv run pytest

# 运行 FastAPI 状态服务器
uv run uvicorn simulator.state_server:app --port 8000

# 运行 MCP 服务 (STDIO 标准模式)
uv run python -m mcp.prometheus_server

# 运行 MCP 服务 (Streamable HTTP 端口模式)
uv run python -m mcp.prometheus_server --transport streamable-http --port 8001
```


---

## 🧹 代码检查与格式化规范 (`ruff`)

项目使用 `ruff` 作为唯一的静态代码检查与格式化工具。配置集中收录于 `pyproject.toml`。

### 1. `pyproject.toml` 中的 Ruff 配置规范
```toml
[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
ignore = ["E501"]  # line-length 由 ruff format 统一处理，忽略 String/Docstring 的 E501
```

* **E / F**: Python 基础语法与标准 PEP8 错误检查。
* **I (isort)**: 自动优化与规范 `import` 引用排序。
* **UP (pyupgrade)**: 强制使用 Python 3.13 现代语法风格（如 `str | None`, `isinstance(x, A | B)`）。
* **B (flake8-bugbear)**: 预判潜在逻辑缺陷与盲区。

### 2. Ruff 常用命令

#### (1) 代码风格检查 (Lint Check)
```bash
# 检查全项目 Lint 问题
uv run ruff check .

# 自动修复可自动解决的警告/错误（例如未使用的 import、过时的语法等）
uv run ruff check --fix .
```

#### (2) 代码格式化 (Format)
```bash
# 自动对全项目进行代码格式化
uv run ruff format .

# 检查代码格式是否合规（CI/验证场景）
uv run ruff format --check .
```

---

## 📐 核心设计原则与编码规范

在编写 `simulator/`、`mcp/`、`runtime/` 及 `evaluator/` 代码时，必须贯彻以下设计原则：

1. **Deterministic (确定性仿真)**
   - 状态演进依赖基于离散步进的 `SimulationClock`（默认 1 Tick = 100ms）。
   - 严禁在仿真演进代码中使用真实 `time.sleep()` 阻塞逻辑。
   - 所有白噪声与故障注入需支持由场景（Scenario）显式指定的 `seed` 隔离。

2. **Single Source of Truth (单一事实源)**
   - `World State Engine` 中的 `Entity` 物理资源状态为物理客观事实的唯一源头。
   - 时序指标、日志、Trace 与系统告警必须通过 `Projections` 投影产生，严禁在 Agent 端或 MCP 端篡改物理事实。

3. **UTC 标准时区约定 (`+00:00`)**
   - 所有导出的 ISO 8601 时间戳及状态 API 返回的时间格式必须显式携带 `+00:00` 后缀（UTC 标准时间）。
   - 避免使用无时区的 `datetime.now()`，统一使用 `datetime.now(timezone.utc)`。

4. **强类型配置与 Fail-Fast**
   - 物理资源（`ServiceResource`, `InfraResource`）、环境配置与 Scenario YAML 解析必须统一使用 **Pydantic** (`simulator/schema.py`) 强类型 Schema 定义与校验。
   - 参数非法（如负数容量、遗漏必需字段）时必须在加载期 Fail-Fast 抛出清晰异常。

5. **模块化解耦架构**
   - **`simulator/`**: 物理资源抽象、时钟步进、离线投影与共享内存 State HTTP API Server。
   - **`mcp/`**: 基于标准 MCP 协议暴露 Prometheus, Loki, Trace, Knowledge 接口。
   - **`runtime/`**: 基于 LangGraph 的多 Agent 协作诊断工作流。
   - **`evaluator/`**: 多维打分与 Ground Truth 校验算法。
   - **`tests/`**: pytest 单元测试。

---

## ✅ 开发者与 Agent 提交前验证工作流 (Verification Workflow)

在提出 Pull Request 或宣布任务完成之前，必须严格按顺序在终端运行以下三步指令，并确保**全部通过且零错误**：

```bash
# 1. 自动修饰与 Lint 检查
uv run ruff check --fix .

# 2. 自动格式化代码
uv run ruff format .

# 3. 运行全量单元测试
uv run pytest
```

---
