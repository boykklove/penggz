#!/usr/bin/env python3
"""
OKX 合约交易执行器（生产增强版）

特性：
- 完整签名鉴权 + 请求重试 + 超时
- 模拟盘/实盘切换
- 守护进程模式（按轮询间隔执行）
- 目标仓位模型（long / short / flat）
- 基础风控（最大单笔、最小净值、最大回撤保护、冷却时间）
- 可选止盈止损自动挂单
- 结构化日志，适合容器部署

⚠️ 不构成投资建议。请务必先模拟盘。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ----------------------------
# 配置与日志
# ----------------------------


def setup_logger() -> logging.Logger:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("okx-bot")


logger = setup_logger()


@dataclass
class OkxConfig:
    base_url: str
    api_key: str
    api_secret: str
    passphrase: str
    simulated: bool


@dataclass
class BotConfig:
    inst_id: str
    td_mode: str
    target_position: str  # long / short / flat
    order_size: Decimal
    loop_enabled: bool
    loop_interval_sec: int
    enable_trading: bool
    min_usdt_equity: Decimal
    max_single_order_size: Decimal
    max_drawdown_pct: Decimal
    cooldown_sec: int
    tp_pct: Decimal
    sl_pct: Decimal


class RiskError(RuntimeError):
    pass


class OkxRestClient:
    def __init__(self, cfg: OkxConfig):
        self.cfg = cfg
        self.session = requests.Session()
        retry = Retry(
            total=4,
            connect=4,
            read=4,
            backoff_factor=0.6,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers.update({"Content-Type": "application/json"})

    @staticmethod
    def _iso_ts() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _sign(self, timestamp: str, method: str, path_with_query: str, body_str: str = "") -> str:
        msg = f"{timestamp}{method.upper()}{path_with_query}{body_str}"
        mac = hmac.new(self.cfg.api_secret.encode(), msg.encode(), digestmod=hashlib.sha256)
        return base64.b64encode(mac.digest()).decode()

    def _headers(self, timestamp: str, signature: str) -> Dict[str, str]:
        h = {
            "OK-ACCESS-KEY": self.cfg.api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.cfg.passphrase,
        }
        if self.cfg.simulated:
            h["x-simulated-trading"] = "1"
        return h

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        params = params or {}
        body = body or {}
        query = ""
        if params:
            query = "?" + "&".join(f"{k}={v}" for k, v in params.items())
        path_with_query = f"{path}{query}"

        body_str = json.dumps(body, separators=(",", ":")) if body else ""
        ts = self._iso_ts()
        signature = self._sign(ts, method, path_with_query, body_str)

        url = f"{self.cfg.base_url}{path_with_query}"
        r = self.session.request(
            method=method.upper(),
            url=url,
            headers=self._headers(ts, signature),
            data=body_str if body else None,
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") != "0":
            raise RuntimeError(f"OKX API error code={data.get('code')} msg={data.get('msg')} data={data.get('data')}")
        return data

    def get_server_time(self) -> Dict[str, Any]:
        r = self.session.get(f"{self.cfg.base_url}/api/v5/public/time", timeout=10)
        r.raise_for_status()
        return r.json()

    def get_ticker(self, inst_id: str) -> Dict[str, Any]:
        return self._request("GET", "/api/v5/market/ticker", params={"instId": inst_id})

    def get_balance(self) -> Dict[str, Any]:
        return self._request("GET", "/api/v5/account/balance")

    def get_positions(self, inst_id: str) -> Dict[str, Any]:
        return self._request("GET", "/api/v5/account/positions", params={"instId": inst_id})

    def place_order(
        self,
        inst_id: str,
        td_mode: str,
        side: str,
        pos_side: str,
        size: Decimal,
        reduce_only: bool,
    ) -> Dict[str, Any]:
        cl_ord_id = f"bot{int(time.time() * 1000)}{random.randint(100, 999)}"
        payload = {
            "instId": inst_id,
            "tdMode": td_mode,
            "side": side,
            "posSide": pos_side,
            "ordType": "market",
            "sz": str(size),
            "reduceOnly": str(reduce_only).lower(),
            "clOrdId": cl_ord_id,
        }
        return self._request("POST", "/api/v5/trade/order", body=payload)

    def place_tp_sl(
        self,
        inst_id: str,
        td_mode: str,
        side: str,
        pos_side: str,
        size: Decimal,
        tp_trigger_px: Optional[Decimal],
        sl_trigger_px: Optional[Decimal],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "instId": inst_id,
            "tdMode": td_mode,
            "side": side,
            "posSide": pos_side,
            "ordType": "conditional",
            "sz": str(size),
        }
        if tp_trigger_px:
            payload["tpTriggerPx"] = str(tp_trigger_px)
            payload["tpOrdPx"] = "-1"
            payload["tpTriggerPxType"] = "last"
        if sl_trigger_px:
            payload["slTriggerPx"] = str(sl_trigger_px)
            payload["slOrdPx"] = "-1"
            payload["slTriggerPxType"] = "last"
        return self._request("POST", "/api/v5/trade/order-algo", body=payload)


def d(value: str, name: str) -> Decimal:
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} 不是合法数字: {value}") from exc


def env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


def load_configs() -> tuple[OkxConfig, BotConfig]:
    okx_cfg = OkxConfig(
        base_url=os.getenv("OKX_BASE_URL", "https://www.okx.com").strip(),
        api_key=os.getenv("OKX_API_KEY", "").strip(),
        api_secret=os.getenv("OKX_API_SECRET", "").strip(),
        passphrase=os.getenv("OKX_API_PASSPHRASE", "").strip(),
        simulated=env_bool("OKX_SIMULATED", "true"),
    )
    if not okx_cfg.api_key or not okx_cfg.api_secret or not okx_cfg.passphrase:
        raise ValueError("缺少 OKX API 凭据：OKX_API_KEY / OKX_API_SECRET / OKX_API_PASSPHRASE")

    target = os.getenv("TARGET_POSITION", "flat").strip().lower()
    if target not in {"long", "short", "flat"}:
        raise ValueError("TARGET_POSITION 只能是 long / short / flat")

    bot_cfg = BotConfig(
        inst_id=os.getenv("INST_ID", "BTC-USDT-SWAP").strip(),
        td_mode=os.getenv("TD_MODE", "cross").strip(),
        target_position=target,
        order_size=d(os.getenv("ORDER_SIZE", "1"), "ORDER_SIZE"),
        loop_enabled=env_bool("LOOP_ENABLED", "true"),
        loop_interval_sec=int(os.getenv("LOOP_INTERVAL_SEC", "15")),
        enable_trading=env_bool("ENABLE_TRADING", "false"),
        min_usdt_equity=d(os.getenv("MIN_USDT_EQUITY", "100"), "MIN_USDT_EQUITY"),
        max_single_order_size=d(os.getenv("MAX_SINGLE_ORDER_SIZE", "5"), "MAX_SINGLE_ORDER_SIZE"),
        max_drawdown_pct=d(os.getenv("MAX_DRAWDOWN_PCT", "20"), "MAX_DRAWDOWN_PCT"),
        cooldown_sec=int(os.getenv("COOLDOWN_SEC", "20")),
        tp_pct=d(os.getenv("TP_PCT", "0"), "TP_PCT"),
        sl_pct=d(os.getenv("SL_PCT", "0"), "SL_PCT"),
    )

    if bot_cfg.order_size <= 0:
        raise ValueError("ORDER_SIZE 必须 > 0")
    if bot_cfg.order_size > bot_cfg.max_single_order_size:
        raise ValueError("ORDER_SIZE 超过 MAX_SINGLE_ORDER_SIZE")

    return okx_cfg, bot_cfg


def extract_equity_usdt(balance_data: Dict[str, Any]) -> Decimal:
    # 账户结构可能因账户模式不同而有差异，优先 totalEq，再 fallback 细项
    item = (balance_data.get("data") or [{}])[0]
    total_eq = item.get("totalEq")
    if total_eq:
        return d(str(total_eq), "totalEq")
    for detail in item.get("details", []):
        if detail.get("ccy") == "USDT":
            val = detail.get("eq") or detail.get("cashBal") or "0"
            return d(str(val), "USDT eq")
    return Decimal("0")


def parse_position_size(positions_data: Dict[str, Any]) -> Dict[str, Decimal]:
    long_sz = Decimal("0")
    short_sz = Decimal("0")
    for p in positions_data.get("data", []):
        side = (p.get("posSide") or "").lower()
        sz_val = d(str(p.get("pos", "0")), "position")
        if side == "long":
            long_sz += abs(sz_val)
        elif side == "short":
            short_sz += abs(sz_val)
    return {"long": long_sz, "short": short_sz}


def calc_tp_sl(entry_px: Decimal, target_position: str, tp_pct: Decimal, sl_pct: Decimal) -> tuple[Optional[Decimal], Optional[Decimal]]:
    tp_trigger = None
    sl_trigger = None
    if target_position == "long":
        if tp_pct > 0:
            tp_trigger = (entry_px * (Decimal("1") + tp_pct / Decimal("100"))).quantize(Decimal("0.1"))
        if sl_pct > 0:
            sl_trigger = (entry_px * (Decimal("1") - sl_pct / Decimal("100"))).quantize(Decimal("0.1"))
    elif target_position == "short":
        if tp_pct > 0:
            tp_trigger = (entry_px * (Decimal("1") - tp_pct / Decimal("100"))).quantize(Decimal("0.1"))
        if sl_pct > 0:
            sl_trigger = (entry_px * (Decimal("1") + sl_pct / Decimal("100"))).quantize(Decimal("0.1"))
    return tp_trigger, sl_trigger


class TradingEngine:
    def __init__(self, client: OkxRestClient, cfg: BotConfig):
        self.client = client
        self.cfg = cfg
        self.last_trade_ts: float = 0.0
        self.initial_equity: Optional[Decimal] = None

    def _risk_checks(self, equity: Decimal) -> None:
        if equity < self.cfg.min_usdt_equity:
            raise RiskError(f"触发最小净值保护：{equity} < {self.cfg.min_usdt_equity}")

        if self.initial_equity is None:
            self.initial_equity = equity
            return

        if self.initial_equity > 0:
            drawdown_pct = (self.initial_equity - equity) / self.initial_equity * Decimal("100")
            if drawdown_pct >= self.cfg.max_drawdown_pct:
                raise RiskError(
                    f"触发最大回撤保护：{drawdown_pct:.2f}% >= {self.cfg.max_drawdown_pct}%"
                )

    def _cooldown_check(self) -> bool:
        return (time.time() - self.last_trade_ts) >= self.cfg.cooldown_sec

    def _close_if_needed(self, side_to_close: str, size: Decimal) -> None:
        if size <= 0:
            return
        if not self.cfg.enable_trading:
            logger.warning("[DRY-RUN] 需要平仓 side=%s size=%s", side_to_close, size)
            return
        pos_side = "long" if side_to_close == "sell" else "short"
        res = self.client.place_order(
            inst_id=self.cfg.inst_id,
            td_mode=self.cfg.td_mode,
            side=side_to_close,
            pos_side=pos_side,
            size=size,
            reduce_only=True,
        )
        logger.info("平仓成功: %s", res)
        self.last_trade_ts = time.time()

    def _open_target(self, target: str, size: Decimal, last_px: Decimal) -> None:
        if size <= 0:
            return

        side = "buy" if target == "long" else "sell"
        pos_side = target

        if not self.cfg.enable_trading:
            logger.warning("[DRY-RUN] 需要开仓 target=%s size=%s", target, size)
            return

        res = self.client.place_order(
            inst_id=self.cfg.inst_id,
            td_mode=self.cfg.td_mode,
            side=side,
            pos_side=pos_side,
            size=size,
            reduce_only=False,
        )
        logger.info("开仓成功: %s", res)
        self.last_trade_ts = time.time()

        tp_px, sl_px = calc_tp_sl(last_px, target, self.cfg.tp_pct, self.cfg.sl_pct)
        if tp_px or sl_px:
            close_side = "sell" if target == "long" else "buy"
            algo = self.client.place_tp_sl(
                inst_id=self.cfg.inst_id,
                td_mode=self.cfg.td_mode,
                side=close_side,
                pos_side=target,
                size=size,
                tp_trigger_px=tp_px,
                sl_trigger_px=sl_px,
            )
            logger.info("TP/SL 条件单已提交: %s", algo)

    def run_once(self) -> None:
        balance = self.client.get_balance()
        equity = extract_equity_usdt(balance)
        self._risk_checks(equity)

        ticker = self.client.get_ticker(self.cfg.inst_id)
        last_px = d(str((ticker.get("data") or [{}])[0].get("last", "0")), "last price")

        positions = self.client.get_positions(self.cfg.inst_id)
        pos = parse_position_size(positions)
        long_sz, short_sz = pos["long"], pos["short"]

        logger.info(
            "状态 | inst=%s target=%s price=%s equity=%s long=%s short=%s trading=%s",
            self.cfg.inst_id,
            self.cfg.target_position,
            last_px,
            equity,
            long_sz,
            short_sz,
            self.cfg.enable_trading,
        )

        if not self._cooldown_check():
            logger.info("冷却中，跳过本轮")
            return

        target = self.cfg.target_position
        if target == "flat":
            self._close_if_needed("sell", long_sz)
            self._close_if_needed("buy", short_sz)
            return

        if target == "long":
            if short_sz > 0:
                self._close_if_needed("buy", short_sz)
            delta = self.cfg.order_size - long_sz
            if delta > 0:
                self._open_target("long", delta, last_px)
            return

        if target == "short":
            if long_sz > 0:
                self._close_if_needed("sell", long_sz)
            delta = self.cfg.order_size - short_sz
            if delta > 0:
                self._open_target("short", delta, last_px)


def healthcheck(client: OkxRestClient) -> int:
    try:
        data = client.get_server_time()
        ts = (data.get("data") or [{}])[0].get("ts", "unknown")
        logger.info("healthcheck ok, server ts=%s", ts)
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.error("healthcheck failed: %s", exc)
        return 1


def main() -> None:
    okx_cfg, bot_cfg = load_configs()
    client = OkxRestClient(okx_cfg)

    if os.getenv("MODE", "run").strip().lower() == "healthcheck":
        raise SystemExit(healthcheck(client))

    engine = TradingEngine(client, bot_cfg)

    logger.info(
        "启动完成 | simulated=%s enable_trading=%s loop=%s interval=%ss target=%s inst=%s",
        okx_cfg.simulated,
        bot_cfg.enable_trading,
        bot_cfg.loop_enabled,
        bot_cfg.loop_interval_sec,
        bot_cfg.target_position,
        bot_cfg.inst_id,
    )

    while True:
        try:
            engine.run_once()
        except RiskError as exc:
            logger.error("风险控制触发，暂停下单: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("运行异常: %s", exc)

        if not bot_cfg.loop_enabled:
            break
        time.sleep(bot_cfg.loop_interval_sec)


if __name__ == "__main__":
    main()
