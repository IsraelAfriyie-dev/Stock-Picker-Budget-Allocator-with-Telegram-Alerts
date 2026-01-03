#!/usr/bin/env python3
"""
Pick top N performing stocks from the universe, allocate a given budget,
and produce buy quantities + take-profit and stop-loss levels. Sends results to Telegram.
"""

import os
import math
import time
from dotenv import load_dotenv
import yfinance as yf
import pandas as pd
import requests
from ta.momentum import RSIIndicator

load_dotenv()

# CONFIG from env (with defaults)
UNIVERSE = os.getenv("UNIVERSE", "AAPL,MSFT,AMZN,NVDA,TSLA").split(",")
TOP_N = int(os.getenv("TOP_N", "3"))
TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "0.10"))  # 10%
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "0.05"))  # 5%
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# --- Helpers ---
def fetch_history(symbol, period="3mo", interval="1d"):
    """Download OHLC data for the given symbol from Yahoo (yfinance)."""
    try:
        # Suppress the FutureWarning by setting auto_adjust explicitly
        df = yf.download(symbol, period=period, interval=interval,
                         progress=False, threads=False, auto_adjust=False)
        if df is None or df.empty:
            print(f"[debug] {symbol}: DataFrame is None or empty")
            return None
        df = df.dropna()
        print(f"[debug] {symbol}: Downloaded {len(df)} data points")
        return df
    except Exception as e:
        print(f"[err] fetch {symbol}: {e}")
        return None


def compute_score(df):
    """
    Score stocks by combining:
      - 10-day momentum (higher is better)
      - RSI (prefer moderate values; too high penalized)
      - Recent SMA relationship (20 > 50 is positive)
    Returns a dict with score and metrics (higher score = better).
    """
    try:
        # Handle MultiIndex columns (yfinance sometimes returns these)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df["Close"].astype(float)
        print(f"[debug] compute_score: {len(close)} close prices available")

        if len(close) < 20:  # Reduced from 30 to 20 for more flexibility
            print(f"[debug] compute_score: insufficient data - only {len(close)} points")
            return None

        # Momentum: pct change over 10 trading days
        momentum_10d = 0.0
        if len(close) >= 10:
            momentum_10d = (close.iloc[-1] / close.iloc[-10] - 1)

        # RSI with error handling
        try:
            rsi_indicator = RSIIndicator(close, window=14)
            rsi = rsi_indicator.rsi().iloc[-1]
            if pd.isna(rsi):
                rsi = 50.0  # neutral default
        except Exception as e:
            print(f"[debug] RSI calculation failed: {e}")
            rsi = 50.0

        # SMA20 / SMA50 with error handling
        try:
            sma20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.iloc[-1]
            sma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else close.iloc[-1]
        except Exception as e:
            print(f"[debug] SMA calculation failed: {e}")
            sma20 = close.iloc[-1]
            sma50 = close.iloc[-1]

        score = 0.0

        # Momentum component
        score += momentum_10d * 10.0

        # RSI component
        if rsi < 30:
            score += 0.8  # oversold might bounce
        elif 40 <= rsi <= 70:
            score += 0.7
        elif rsi > 75:
            score -= 0.8

        # SMA relationship component
        if sma20 > sma50:
            score += 0.8
        else:
            score -= 0.2

        # Recent price change component
        try:
            recent_change = close.pct_change(1).iloc[-1]
            if not pd.isna(recent_change):
                score += recent_change * 5.0
        except:
            pass

        result = {
            "score": float(score),
            "momentum_10d": float(momentum_10d),
            "rsi": float(rsi),
            "sma20": float(sma20),
            "sma50": float(sma50),
            "price": float(close.iloc[-1])
        }

        print(f"[debug] Score calculated: {result}")
        return result

    except Exception as e:
        print(f"[err] compute_score failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def pick_top_symbols(universe, top_n=3):
    results = []
    print(f"[debug] Starting symbol analysis for {len(universe)} symbols")

    for sym in universe:
        s = sym.strip().upper()
        print(f"[debug] Processing {s}...")

        df = fetch_history(s, period="3mo")
        if df is None:
            print(f"  - {s}: no data")
            continue

        score_obj = compute_score(df)
        if not score_obj:
            print(f"  - {s}: insufficient data for scoring")
            continue

        score_obj.update({"symbol": s})
        print(f"  - {s}: score={score_obj['score']:.3f} price=${score_obj['price']:.2f} rsi={score_obj['rsi']:.1f}")
        results.append(score_obj)

        # Small delay to be nice to Yahoo Finance
        time.sleep(0.1)

    print(f"[debug] Found {len(results)} valid results")

    if not results:
        return []

    dfres = pd.DataFrame(results)
    dfres = dfres.sort_values("score", ascending=False)
    picks = dfres.head(top_n).to_dict("records")

    print(f"[debug] Selected top {len(picks)} picks")
    return picks


def allocate_budget(budget, picks, take_profit_pct=TAKE_PROFIT_PCT, stop_loss_pct=STOP_LOSS_PCT):
    """Given budget and picks (with price), compute allocation and targets per pick."""
    n = len(picks)
    if n == 0:
        return []
    per = budget / n
    plan = []
    for p in picks:
        price = p["price"]
        shares = per / price  # fractional shares allowed
        # round shares to 4 decimal places (adjustable)
        shares = round(shares, 4)
        cost = round(shares * price, 2)
        target_price = round(price * (1 + take_profit_pct), 2)
        stop_price = round(price * (1 - stop_loss_pct), 2)
        plan.append({
            "symbol": p["symbol"],
            "price": price,
            "score": p["score"],
            "rsi": p["rsi"],
            "allocation": round(per, 2),
            "shares": shares,
            "cost": cost,
            "take_profit_price": target_price,
            "stop_loss_price": stop_price
        })
    return plan


def format_message(budget, plan):
    if not plan:
        return f"⚠️ No picks found for the universe.\n"
    lines = []
    lines.append(f"💰 Budget: ${budget:,.2f}")
    lines.append(f"📌 Picks (top {len(plan)}):\n")
    for i, p in enumerate(plan, 1):
        lines.append(
            f"{i}. {p['symbol']} — Price ${p['price']:.2f} | Buy shares: {p['shares']} | Alloc ${p['allocation']:.2f}\n"
            f"     TP: ${p['take_profit_price']:.2f} (+{int(TAKE_PROFIT_PCT * 100)}%)  SL: ${p['stop_loss_price']:.2f} (-{int(STOP_LOSS_PCT * 100)}%)"
        )
    lines.append("\nNote: This is a recommendation only. Review before trading.")
    return "\n".join(lines)


def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[warn] Telegram not configured, printing message instead:")
        print(msg)
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    try:
        r = requests.post(url, data=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[err] Telegram send failed: {e}")
        print(msg)
        return False


# --- Main CLI function ---
def plan_trades_from_budget(budget):
    print(f"Scanning universe: {UNIVERSE}")
    picks = pick_top_symbols(UNIVERSE, top_n=TOP_N)
    if not picks:
        msg = "No suitable picks found today."
        print(msg)
        send_telegram(msg)
        return None
    plan = allocate_budget(budget, picks)
    message = format_message(budget, plan)
    print("\n" + message + "\n")
    send_telegram(message)
    return plan


# If run directly: ask user for budget and run once
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pick top N performing stocks and allocate a budget.")
    parser.add_argument("--budget", "-b", type=float, required=False, default=None, help="Total USD budget (e.g. 1000)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    if args.budget is None:
        try:
            raw = input("Enter budget in USD (e.g. 1000): ").strip()
            budget = float(raw)
        except Exception:
            print("Invalid budget. Exiting.")
            exit(1)
    else:
        budget = args.budget

    plan_trades_from_budget(budget)