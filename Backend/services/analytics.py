# services/analytics.py

from sqlalchemy.orm import Session
from models import Position, Asset
from services.market import get_live_prices

def generate_portfolio_report(db: Session):
    """
    Generates a complete portfolio analytics report.
    Returns a dictionary with total value, allocations, sector breakdown,
    weighted metrics (PE, beta, ROE, dividend yield) and gain/loss info.
    """
    positions = db.query(Position).all()
    if not positions:
        return {
            "total_value": 0,
            "total_invested": 0,
            "total_gain_loss": 0,
            "allocations": {},
            "sector_breakdown": {},
            "weighted_metrics": {},
            "positions": []
        }

    total_invested = 0
    total_value = 0
    positions_data = []
    allocations = {}
    sector_breakdown = {}
    weighted_metrics = {"pe_ratio": 0, "beta": 0, "roe": 0, "dividend_yield": 0}
    weight_sum = 0

    # Collect tickers for batch price fetch
    tickers = [pos.ticker.upper() for pos in positions]
    live_prices = get_live_prices(tickers)

    for pos in positions:
        ticker = pos.ticker.upper()
        quantity = pos.quantity
        avg_cost = pos.avg_cost
        invested = quantity * avg_cost

        live_price = live_prices.get(ticker)
        if live_price is None:
            continue

        current_value = quantity * live_price
        gain_loss = current_value - invested

        # Update totals
        total_invested += invested
        total_value += current_value

        # Append individual position
        positions_data.append({
            "ticker": ticker,
            "quantity": quantity,
            "avg_cost": avg_cost,
            "live_price": live_price,
            "invested": invested,
            "current_value": current_value,
            "gain_loss": gain_loss
        })

        # Allocation by ticker
        allocations[ticker] = current_value

        # Sector metrics
        asset = db.query(Asset).filter(Asset.ticker == ticker).first()
        if asset and asset.sector:
            sector_breakdown.setdefault(asset.sector, 0)
            sector_breakdown[asset.sector] += current_value

            weight = current_value
            weight_sum += weight

            for key in ["pe_ratio", "beta", "roe", "dividend_yield"]:
                value = getattr(asset, key) or 0
                weighted_metrics[key] += value * weight

    # Normalize allocations and sector breakdown
    if total_value > 0:
        allocations = {k: v / total_value for k, v in allocations.items()}
        sector_breakdown = {k: v / total_value for k, v in sector_breakdown.items()}

    # Normalize weighted metrics
    if weight_sum > 0:
        for key in weighted_metrics:
            weighted_metrics[key] /= weight_sum
    else:
        for key in weighted_metrics:
            weighted_metrics[key] = 0

    return {
        "total_value": total_value,
        "total_invested": total_invested,
        "total_gain_loss": total_value - total_invested,
        "allocations": allocations,
        "sector_breakdown": sector_breakdown,
        "weighted_metrics": weighted_metrics,
        "positions": positions_data
    }