import streamlit as st

from core.debt import build_amortization, annualize_debt_service
from core.cashflows import build_cashflows, min_avg_dscr
from core.finance import npv, irr, roi_from_flows, payback, discounted_payback

@st.cache_data(show_spinner=False)
def evaluate_model(inputs):
    capex = inputs["capex"]
    financed_amount = capex * inputs["financed_pct"]
    equity_amount = capex - financed_amount

    amort_df, periodic_payment = build_amortization(
        financed_amount,
        inputs["interest_rate"],
        inputs["debt_years"],
        inputs["payments_per_year"],
        inputs["grace_periods"],
    )

    annual_debt = annualize_debt_service(
        amort_df,
        inputs["payments_per_year"],
        inputs["project_years"],
    )

    cashflow_df, project_flows, equity_flows = build_cashflows(
        capex=capex,
        equity_amount=equity_amount,
        project_years=inputs["project_years"],
        annual_generation_kwh=inputs["annual_generation_kwh"],
        degradation=inputs["degradation"],
        tariff0=inputs["tariff0"],
        tariff_growth=inputs["tariff_growth"],
        opex0=inputs["opex0"],
        opex_growth=inputs["opex_growth"],
        corrective0=inputs["corrective0"],
        corrective_growth=inputs["corrective_growth"],
        tax_rate=inputs["tax_rate"],
        discount_rate=inputs["discount_rate"],
        annual_debt_service_df=annual_debt,
        major_replacement_year=inputs["major_replacement_year"],
        major_replacement_cost=inputs["major_replacement_cost"],
    )

    project_npv = npv(inputs["discount_rate"], project_flows)
    equity_npv = npv(inputs["discount_rate"], equity_flows)
    project_irr = irr(project_flows)
    equity_irr = irr(equity_flows)
    project_roi = roi_from_flows(capex, project_flows)
    equity_roi = roi_from_flows(equity_amount, equity_flows)
    project_pb = payback(project_flows)
    equity_pb = payback(equity_flows)
    project_dpb = discounted_payback(inputs["discount_rate"], project_flows)
    equity_dpb = discounted_payback(inputs["discount_rate"], equity_flows)
    dscr_min, dscr_avg = min_avg_dscr(cashflow_df)

    return {
        "financed_amount": financed_amount,
        "equity_amount": equity_amount,
        "periodic_payment": periodic_payment,
        "annual_debt": annual_debt,
        "amort_df": amort_df,
        "cashflow_df": cashflow_df,
        "project_npv": project_npv,
        "equity_npv": equity_npv,
        "project_irr": project_irr,
        "equity_irr": equity_irr,
        "project_roi": project_roi,
        "equity_roi": equity_roi,
        "project_pb": project_pb,
        "equity_pb": equity_pb,
        "project_dpb": project_dpb,
        "equity_dpb": equity_dpb,
        "dscr_min": dscr_min,
        "dscr_avg": dscr_avg,
    }

def evaluate_sensitivity(base_inputs, field_name, factors):
    rows = []
    for factor in factors:
        local = dict(base_inputs)
        local[field_name] = base_inputs[field_name] * factor
        result = evaluate_model(local)
        rows.append({
            "Escenario": f"{int((factor - 1) * 100):+d}%",
            "VAN proyecto": result["project_npv"],
            "TIR proyecto": result["project_irr"],
            "VAN equity": result["equity_npv"],
            "TIR equity": result["equity_irr"],
            "DSCR mínimo": result["dscr_min"],
        })
    import pandas as pd
    return pd.DataFrame(rows)
