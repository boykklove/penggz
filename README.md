# OKX Futures Executor（生产增强版）

> ⚠️ 高风险提示：本项目仅用于 API 自动化执行示例，不构成投资建议。请先在 **模拟盘** 完整验证。

## 功能亮点
- OKX V5 REST 签名鉴权 + 自动重试（429/5xx）
- 目标仓位执行：`long` / `short` / `flat`
- 风控保护：
  - `ENABLE_TRADING=false` 默认 DRY-RUN（不下真单）
  - 最小净值保护 `MIN_USDT_EQUITY`
  - 最大单笔限制 `MAX_SINGLE_ORDER_SIZE`
  - 最大回撤熔断 `MAX_DRAWDOWN_PCT`
  - 下单冷却 `COOLDOWN_SEC`
- 可选止盈止损（按百分比自动计算触发价）
- Docker / Compose 一键部署

---

## 1) 快速开始（本地）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env（先用 OKX_SIMULATED=true + ENABLE_TRADING=false）
set -a && source .env && set +a
python okx_futures_bot.py
```

---

## 2) 关键环境变量

- `TARGET_POSITION=long|short|flat`：目标仓位
- `ORDER_SIZE`：目标仓位张数
- `ENABLE_TRADING=false|true`：是否允许真实下单（默认 false）
- `OKX_SIMULATED=true|false`：模拟盘/实盘
- `TP_PCT` / `SL_PCT`：止盈止损百分比（0 表示不挂）
- `LOOP_ENABLED=true|false`：守护循环或单次执行
- `MODE=run|healthcheck`：正常运行 / 健康检查

---

## 3) Docker 直接部署（推荐）

### 3.1 本地构建并运行

```bash
cp .env.example .env
# 编辑 .env

docker build -t okx-futures-bot:latest .
docker run -d --name okx-futures-bot --env-file .env okx-futures-bot:latest

docker logs -f okx-futures-bot
```

### 3.2 Docker Compose

```bash
cp .env.example .env
# 编辑 .env

docker compose up -d --build
docker compose logs -f okx-bot
```

### 3.3 Docker Pull 直接拉取部署（生产建议）

你可以把镜像推到自己的仓库（如 GHCR / Docker Hub）后，在服务器直接拉取：

```bash
# 示例：请替换为你自己的镜像地址
export IMAGE=ghcr.io/your-org/okx-futures-bot:latest

docker pull $IMAGE
docker run -d \
  --name okx-futures-bot \
  --restart unless-stopped \
  --env-file /opt/okx-bot/.env \
  $IMAGE
```

---

## 4) 生产上线建议

1. **先模拟盘至少跑 3~7 天**，确认日志、风控和参数无异常。  
2. 首次实盘：`ENABLE_TRADING=true` 但把 `ORDER_SIZE` 设为极小。  
3. 持续观察 `equity`、`drawdown`、成交失败重试日志。  
4. API Key 最小权限原则（只给交易需要权限，不给提币权限）。

---

## 5) 常见运维命令

```bash
# 健康检查（容器内）
MODE=healthcheck python okx_futures_bot.py

# 查看运行日志
docker logs -f okx-futures-bot

# 重启
docker restart okx-futures-bot
```

---

## 6) GitHub Actions 自动构建并推送 GHCR

仓库已包含工作流：`.github/workflows/ghcr.yml`。默认行为：
- push 到 `main`：自动构建并推送 `latest` + `sha` 标签
- push `v*` tag：自动推送版本标签
- 支持手动触发 `workflow_dispatch`

### 6.1 仓库设置

1. GitHub 仓库 `Settings -> Actions -> General` 中允许工作流运行。  
2. 仓库 `Settings -> Actions -> Workflow permissions` 设为 **Read and write permissions**（用于发布包）。

> 工作流使用 `secrets.GITHUB_TOKEN` 登录 GHCR，不需要额外 PAT（同仓库发布场景）。

### 6.2 拉取镜像

推送成功后可直接拉取：

```bash
docker pull ghcr.io/<your-org>/okx-futures-bot:latest
docker pull ghcr.io/<your-org>/okx-futures-bot:<git-sha>
```

### 6.3 服务器滚动更新

```bash
export IMAGE=ghcr.io/<your-org>/okx-futures-bot:latest
docker pull $IMAGE
docker rm -f okx-futures-bot || true
docker run -d \
  --name okx-futures-bot \
  --restart unless-stopped \
  --env-file /opt/okx-bot/.env \
  $IMAGE
```
