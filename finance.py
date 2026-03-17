import numpy as np
import numpy_financial as npf

def payback(cashflows):
    cumulative = 0.0
    for year, cf in enumerate(cashflows):
        cumulative += cf
        if cumulative >= 0:
            return year
    return None

def discounted_payback(rate, cashflows):
    cumulative = 0.0
    for year, cf in enumerate(cashflows):
        cumulative += cf / ((1 + rate) ** year)
        if cumulative >= 0:
            return year
    return None

def roi_from_flows(initial_investment, flows):
    if initial_investment == 0:
        return np.nan
    return (float(np.sum(flows[1:])) - initial_investment) / initial_investment

def npv(rate, flows):
    return float(npf.npv(rate, flows[1:]) + flows[0])

def irr(flows):
    if np.any(flows < 0) and np.any(flows > 0):
        return float(npf.irr(flows))
    return np.nan
