# AoE2: The Conquerors Replay Analyzer

一个可直接运行的回放分析器，支持：

- 从回放摘要中提取基础信息（玩家、文明、地图、时长）
- 生成关键时间线（升时代、常见建筑）
- 导出 `match_summary.json` 与 `timeline.csv`

> 说明：项目默认支持两种输入路径：
> 1) 直接喂 `.mgz/.mgl` 回放（通过 `mgz` 命令行工具解析）
> 2) 喂回放摘要 JSON（离线/无网络环境推荐）

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 模式 A：直接解析回放文件

先安装 `mgz` 解析器（命令名通常为 `mgz`，由 `aoc-mgz` 项目提供）。

```bash
python src/main.py analyze --rec /path/to/game.mgz --out ./out
```

### 模式 B：从摘要 JSON 解析（推荐先跑通）

```bash
python src/main.py analyze --summary-json examples/sample_summary.json --out ./out
```

## 输出

- `out/match_summary.json`
- `out/timeline.csv`

## 运行测试

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

