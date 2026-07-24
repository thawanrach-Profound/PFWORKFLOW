"""ราคาตลาดโลก — ทองคำ / น้ำมันดิบ Brent / ยูเรีย

แหล่งข้อมูล:
- ทองคำ realtime: gold-api.com (ฟรี ไม่ต้องมี key)
- Brent / Urea / Gold รายเดือน: World Bank Commodity Price Data (Pink Sheet)
- ยูเรียจากซัพพลายเออร์: คีย์เองผ่าน POST /api/market/manual
"""
import io
import json
import logging
import urllib.request
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

logger = logging.getLogger("crm.market")

router = APIRouter(prefix="/api/market", tags=["market"])

GOLD_API_URL = "https://api.gold-api.com/price/XAU"
WB_CMO_URL = (
    "https://thedocs.worldbank.org/en/doc/"
    "5d903e848db1d1b83e0ec8f744e55570-0350012021/related/CMO-Historical-Data-Monthly.xlsx"
)

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1d"

# symbol → (ชื่อไทย, หน่วย)
SYMBOLS = {
    "gold_spot": ("ทองคำ (Spot)", "USD/oz"),
    "brent_spot": ("น้ำมันดิบ Brent (Realtime)", "USD/บาร์เรล"),
    "wti_spot": ("น้ำมันดิบ WTI (Realtime)", "USD/บาร์เรล"),
    "usd_thb": ("ค่าเงินบาท (USD/THB)", "บาท/ดอลลาร์"),
    "gold_wb": ("ทองคำ (เฉลี่ยรายเดือน)", "USD/oz"),
    "brent": ("น้ำมันดิบ Brent (เฉลี่ยรายเดือน)", "USD/บาร์เรล"),
    "urea": ("ยูเรีย (World Bank)", "USD/ตัน"),
    "urea_cn": ("ยูเรีย จีน (SunSirs)", "CNY/ตัน"),
    "dap_cn": ("DAP จีน (SunSirs)", "CNY/ตัน"),
    "amsul_cn": ("แอมโมเนียมซัลเฟต จีน (100ppi)", "CNY/ตัน"),
    "kcl_cn": ("โพแทสเซียมคลอไรด์ จีน (SunSirs)", "CNY/ตัน"),
    "urea_manual": ("ยูเรีย (ซัพพลายเออร์)", "USD/ตัน"),
}


def _http_get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (crm-market)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _upsert(db: Session, symbol: str, price_date: date, price, source: str):
    db.execute(text("""
        INSERT INTO market_prices (symbol, price_date, price, source)
        VALUES (:s, :d, :p, :src)
        ON CONFLICT (symbol, price_date)
        DO UPDATE SET price = EXCLUDED.price, source = EXCLUDED.source, fetched_at = now()
    """), {"s": symbol, "d": price_date, "p": price, "src": source})


def _fetch_gold_spot(db: Session) -> Optional[dict]:
    try:
        data = json.loads(_http_get(GOLD_API_URL, timeout=20))
        price = data["price"]
        _upsert(db, "gold_spot", date.today(), price, "gold-api.com")
        return {"price": price, "updated_at": data.get("updatedAt")}
    except Exception as e:
        logger.warning("gold spot fetch failed: %s", e)
        return None


def _get_with_hwcheck(url: str) -> str:
    """เว็บจีน (SunSirs/100ppi) มีด่านกันบอท: หน้าแรกส่ง md5 มาให้ตั้ง cookie HW_CHECK แล้วโหลดซ้ำ"""
    import re
    first = _http_get(url, timeout=30).decode("utf-8", "ignore")
    m = re.search(r'"([0-9a-f]{32})"', first)
    if not m:
        return first  # ไม่เจอด่าน — ได้หน้าจริงเลย
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (crm-market)",
        "Cookie": "HW_CHECK=" + m.group(1),
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "ignore")


# symbol → (url, parser) ราคาแม่ปุ๋ยจีนรายวัน
def _parse_sunsirs(html: str):
    """ตาราง: Commodity | Sectors | Price | Date — เอาแถวล่าสุด"""
    import re
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "|", html))
    cells = [s.strip() for s in txt.split("|") if s.strip()]
    if "Date" not in cells:
        return None
    i = cells.index("Date")
    price, d = cells[i + 3], cells[i + 4]
    return float(price.replace(",", "")), datetime.strptime(d, "%Y-%m-%d").date()


def _parse_100ppi(html: str):
    import re
    mp = re.search(r"([\d,]{3,}\.?\d*)\s*元", html)
    md = re.search(r"(20\d\d-\d\d-\d\d)", html)
    if not (mp and md):
        return None
    return float(mp.group(1).replace(",", "")), datetime.strptime(md.group(1), "%Y-%m-%d").date()


CN_FERT_SOURCES = {
    "urea_cn": ("https://www.sunsirs.com/uk/prodetail-89.html", _parse_sunsirs, "sunsirs.com"),
    "dap_cn": ("https://www.sunsirs.com/uk/prodetail-99.html", _parse_sunsirs, "sunsirs.com"),
    "amsul_cn": ("https://www.100ppi.com/vane/detail-741.html", _parse_100ppi, "100ppi.com"),
    "kcl_cn": ("https://www.sunsirs.com/uk/prodetail-759.html", _parse_sunsirs, "sunsirs.com"),
}


def _fetch_cn_fertilizer(db: Session) -> dict:
    out = {}
    for sym, (url, parser, src) in CN_FERT_SOURCES.items():
        try:
            parsed = parser(_get_with_hwcheck(url))
            if not parsed:
                raise RuntimeError("parse ไม่ได้ — โครงสร้างหน้าอาจเปลี่ยน")
            price, price_date = parsed
            _upsert(db, sym, price_date, price, src)
            out[sym] = {"price": price, "date": price_date.isoformat()}
        except Exception as e:
            logger.warning("cn fertilizer fetch failed (%s): %s", sym, e)
            out[sym] = None
    return out


# symbol ในระบบ → ticker ของ Yahoo Finance
YAHOO_TICKERS = {"brent_spot": "BZ=F", "wti_spot": "CL=F", "usd_thb": "THB=X"}


def _fetch_oil_spot(db: Session) -> dict:
    out = {}
    for sym, ticker in YAHOO_TICKERS.items():
        try:
            data = json.loads(_http_get(YAHOO_CHART_URL.format(sym=ticker), timeout=20))
            meta = data["chart"]["result"][0]["meta"]
            price = meta["regularMarketPrice"]
            _upsert(db, sym, date.today(), price, "yahoo-finance")
            out[sym] = price
        except Exception as e:
            logger.warning("oil spot fetch failed (%s): %s", ticker, e)
            out[sym] = None
    return out


def _fetch_worldbank(db: Session) -> int:
    """โหลด Pink Sheet รายเดือน แล้ว upsert brent/urea/gold_wb ย้อนหลัง 36 เดือน"""
    import openpyxl
    raw = _http_get(WB_CMO_URL, timeout=120)
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    ws = wb["Monthly Prices"]
    rows = list(ws.iter_rows(values_only=True))
    header = rows[4]
    cols = {}
    for i, v in enumerate(header):
        name = str(v or "").strip()
        if name == "Crude oil, Brent":
            cols["brent"] = i
        elif name == "Urea":
            cols["urea"] = i
        elif name == "Gold":
            cols["gold_wb"] = i
    if not cols:
        raise RuntimeError("ไม่พบคอลัมน์ราคาในไฟล์ World Bank")
    data_rows = [r for r in rows[6:] if r and r[0] and "M" in str(r[0])]
    count = 0
    for r in data_rows[-36:]:
        # r[0] เช่น "2024M12"
        try:
            y, m = str(r[0]).split("M")
            d = date(int(y), int(m), 1)
        except ValueError:
            continue
        for sym, idx in cols.items():
            val = r[idx]
            if isinstance(val, (int, float, Decimal)):
                _upsert(db, sym, d, float(val), "worldbank-pinksheet")
                count += 1
    return count


@router.post("/refresh")
def refresh_prices(db: Session = Depends(get_db)):
    """ดึงราคาล่าสุดจากทุกแหล่ง (ทอง realtime + World Bank รายเดือน)"""
    gold = _fetch_gold_spot(db)
    oil = _fetch_oil_spot(db)
    cn_fert = _fetch_cn_fertilizer(db)
    wb_count = 0
    wb_error = None
    try:
        wb_count = _fetch_worldbank(db)
    except Exception as e:
        logger.warning("worldbank fetch failed: %s", e)
        wb_error = str(e)
    db.commit()
    return {"gold_spot": gold, "oil_spot": oil, "cn_fertilizer": cn_fert,
            "worldbank_rows": wb_count, "worldbank_error": wb_error}


@router.get("/prices")
def latest_prices(db: Session = Depends(get_db)):
    """ราคาล่าสุดของทุก symbol + อายุข้อมูล — ถ้าทอง spot เก่ากว่า 1 ชม. จะดึงใหม่ให้อัตโนมัติ"""
    row = db.execute(text("""
        SELECT fetched_at FROM market_prices
        WHERE symbol = 'gold_spot' ORDER BY price_date DESC LIMIT 1
    """)).fetchone()
    stale = (not row) or (datetime.now(timezone.utc) - row[0]).total_seconds() > 3600
    if stale:
        _fetch_gold_spot(db)
        _fetch_oil_spot(db)
        _fetch_cn_fertilizer(db)
        db.commit()

    out = []
    for sym, (name_th, unit) in SYMBOLS.items():
        r = db.execute(text("""
            SELECT price_date, price, source, fetched_at
            FROM market_prices WHERE symbol = :s
            ORDER BY price_date DESC LIMIT 2
        """), {"s": sym}).fetchall()
        if not r:
            continue
        latest, prev = r[0], (r[1] if len(r) > 1 else None)
        out.append({
            "symbol": sym,
            "name_th": name_th,
            "unit": unit,
            "price": float(latest[1]),
            "price_date": latest[0].isoformat(),
            "prev_price": float(prev[1]) if prev else None,
            "source": latest[2],
            "fetched_at": latest[3].isoformat() if latest[3] else None,
        })
    return out


@router.get("/history")
def price_history(symbol: str, months: int = 24, db: Session = Depends(get_db)):
    if symbol not in SYMBOLS:
        raise HTTPException(400, "symbol ไม่ถูกต้อง")
    rows = db.execute(text("""
        SELECT price_date, price FROM market_prices
        WHERE symbol = :s ORDER BY price_date DESC LIMIT :n
    """), {"s": symbol, "n": max(1, min(months, 120))}).fetchall()
    return [{"date": r[0].isoformat(), "price": float(r[1])} for r in reversed(rows)]


@router.get("/forecast")
def price_forecast(symbol: str, horizon: int = 6, db: Session = Depends(get_db)):
    """พยากรณ์แนวโน้มรายเดือนด้วย Holt's linear trend + ช่วงความเชื่อมั่น 95%

    ข้อมูลรายวันถูกยุบเป็นค่าเฉลี่ยรายเดือนก่อน แล้วพยากรณ์ต่อ horizon เดือน
    เป็นการประมาณแนวโน้มทางสถิติ ไม่ใช่ราคาที่รับประกัน
    """
    if symbol not in SYMBOLS:
        raise HTTPException(400, "symbol ไม่ถูกต้อง")
    horizon = max(1, min(horizon, 12))
    rows = db.execute(text("""
        SELECT date_trunc('month', price_date)::date AS m, AVG(price) AS p
        FROM market_prices WHERE symbol = :s
        GROUP BY 1 ORDER BY 1
    """), {"s": symbol}).fetchall()
    if len(rows) < 4:
        raise HTTPException(400, "ข้อมูลย้อนหลังไม่พอสำหรับพยากรณ์ (ต้องมีอย่างน้อย 4 เดือน)")

    dates = [r[0] for r in rows]
    vals = [float(r[1]) for r in rows]

    # Holt's linear trend (double exponential smoothing)
    alpha, beta = 0.5, 0.3
    level, trend = vals[0], vals[1] - vals[0]
    residuals = []
    for v in vals[1:]:
        pred = level + trend
        residuals.append(v - pred)
        new_level = alpha * v + (1 - alpha) * (level + trend)
        trend = beta * (new_level - level) + (1 - beta) * trend
        level = new_level
    sigma = (sum(r * r for r in residuals) / len(residuals)) ** 0.5

    def add_months(d: date, n: int) -> date:
        y, m = d.year + (d.month - 1 + n) // 12, (d.month - 1 + n) % 12 + 1
        return date(y, m, 1)

    forecast = []
    for h in range(1, horizon + 1):
        point = level + h * trend
        ci = 1.96 * sigma * (h ** 0.5)
        forecast.append({
            "date": add_months(dates[-1], h).isoformat(),
            "price": round(point, 2),
            "lower": round(point - ci, 2),
            "upper": round(point + ci, 2),
        })

    pct_per_month = (trend / level * 100) if level else 0
    direction = "up" if pct_per_month > 0.5 else ("down" if pct_per_month < -0.5 else "flat")
    name_th, unit = SYMBOLS[symbol]
    return {
        "symbol": symbol,
        "name_th": name_th,
        "unit": unit,
        "history": [{"date": d.isoformat(), "price": round(v, 2)} for d, v in zip(dates, vals)],
        "forecast": forecast,
        "trend_pct_per_month": round(pct_per_month, 2),
        "direction": direction,
    }


class ManualPrice(BaseModel):
    symbol: str = "urea_manual"
    price_date: date
    price: float
    note: Optional[str] = None


@router.post("/manual", status_code=201)
def add_manual_price(payload: ManualPrice, db: Session = Depends(get_db)):
    """คีย์ราคาเอง เช่น ราคายูเรียจากซัพพลายเออร์"""
    if payload.symbol not in SYMBOLS:
        raise HTTPException(400, "symbol ไม่ถูกต้อง")
    if payload.price <= 0:
        raise HTTPException(400, "ราคาต้องมากกว่า 0")
    _upsert(db, payload.symbol, payload.price_date,
            payload.price, payload.note or "manual")
    db.commit()
    return {"ok": True}
