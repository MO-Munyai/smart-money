# Backend/portfolio.py
from sqlalchemy.orm import Session
from services.market import get_live_price
from crud import get_positions, get_assets
import pandas as pd

def generate_portfolio_report(db: Session):
    """
    Generates the full portfolio snapshot:
    - Positions (quantity, avg cost)
    - Live price per ticker
    - Current value per position
    - Gain/Loss
    - Total invested, total current value, total gain/loss
    - Sector and industry breakdown
    - Weighted metrics: PE, Beta, ROE, Dividend Yield
    """
    positions = get_positions(db)
    if not positions:
        return {
            "total_invested": 0,
            "total_current_value": 0,
            "total_gain_loss": 0,
            "positions": [],
            "sector_breakdown": {},
            "industry_breakdown": {},
            "weighted_metrics": {}
        }

    # Fetch all assets for metrics
    assets_list = get_assets(db)
    assets_dict = {a.ticker.upper(): a for a in assets_list}

    total_invested = 0
    total_current_value = 0
    positions_data = []

    sector_breakdown = {}
    industry_breakdown = {}
    weighted_metrics = {"pe_ratio": 0, "beta": 0, "roe": 0, "dividend_yield": 0}
    weight_sum = 0

    for pos in positions:
        ticker = pos["ticker"].upper()
        quantity = pos["quantity"]
        avg_cost = pos["avg_cost"]
        invested = quantity * avg_cost

        live_price = get_live_price(ticker)
        if live_price is None:
            continue

        current_value = quantity * live_price
        gain_loss = current_value - invested

        # Update totals
        total_invested += invested
        total_current_value += current_value

        # Append position
        positions_data.append({
            "ticker": ticker,
            "quantity": quantity,
            "avg_cost": avg_cost,
            "live_price": live_price,
            "invested": invested,
            "current_value": current_value,
            "gain_loss": gain_loss
        })

        # Sector & Industry breakdown
        asset = assets_dict.get(ticker)
        if asset:
            if asset.sector:
                sector_breakdown.setdefault(asset.sector, 0)
                sector_breakdown[asset.sector] += current_value

            if asset.industry:
                industry_breakdown.setdefault(asset.industry, 0)
                industry_breakdown[asset.industry] += current_value

            # Weighted metrics
            weight = current_value
            weight_sum += weight
            for key in ["pe_ratio", "beta", "roe", "dividend_yield"]:
                value = getattr(asset, key) or 0
                weighted_metrics[key] += value * weight

    # Normalize sector/industry breakdown
    for key in sector_breakdown:
        sector_breakdown[key] = sector_breakdown[key] / total_current_value if total_current_value > 0 else 0
    for key in industry_breakdown:
        industry_breakdown[key] = industry_breakdown[key] / total_current_value if total_current_value > 0 else 0

    # Normalize weighted metrics
    if weight_sum > 0:
        for key in weighted_metrics:
            weighted_metrics[key] /= weight_sum
    else:
        for key in weighted_metrics:
            weighted_metrics[key] = 0

    return {
        "total_invested": total_invested,
        "total_current_value": total_current_value,
        "total_gain_loss": total_current_value - total_invested,
        "positions": positions_data,
        "sector_breakdown": sector_breakdown,
        "industry_breakdown": industry_breakdown,
        "weighted_metrics": weighted_metrics
    }