import numpy as np
import pandas as pd
import streamlit as st

@st.cache_data(show_spinner=False)
def build_cashflows(
    capex,
    equity_amount,
    project_years,
    annual_generation_kwh,
    degradation,
    tariff0,
    tariff_growth,
    opex0,
    opex_growth,
    corrective0,
    corrective_growth,
    tax_rate,
    discount_rate,
    annual_debt_service_df,
    major_replacement_year,
    major_replacement_cost,
):
    years = np.arange(1, project_years + 1)
    generation = annual_generation_kwh * ((1 - degradation) ** (years - 1))
    tariff = tariff0 * ((1 + tariff_growth) ** (years - 1))
    revenue = generation * tariff

    opex = opex0 * ((1 + opex_growth) ** (years - 1))
    corrective = corrective0 * ((1 + corrective_growth) ** (years - 1))
    replacement = (
        np.where(years == major_replacement_year, major_replacement_cost, 0.0)
        if major_replacement_year > 0
        else np.zeros_like(years, dtype=float)
    )

    operating_cost = opex + corrective + replacement
    ebitda = revenue - operating_cost
    taxes = np.maximum(0.0, ebitda * tax_rate)
    project_flow = ebitda - taxes

    debt_map = annual_debt_service_df.set_index("Año")["Servicio deuda"].to_dict()
    debt_service = np.array([debt_map.get(int(y), 0.0) for y in years], dtype=float)

    cfads = revenue - operating_cost
    equity_flow = project_flow - debt_service
    dscr = np.where(debt_service > 0, cfads / debt_service, np.nan)

    df = pd.DataFrame({
        "Año": years,
        "Generación (kWh)": generation,
        "Tarifa": tariff,
        "Ahorro/Ingreso": revenue,
        "OPEX": opex,
        "Mto correctivo": corrective,
        "Reposición mayor": replacement,
        "EBITDA": ebitda,
        "Impuestos": taxes,
        "CFADS": cfads,
        "Servicio deuda": debt_service,
        "DSCR": dscr,
        "Flujo proyecto": project_flow,
        "Flujo equity": equity_flow,
        "Flujo proyecto descontado": project_flow / ((1 + discount_rate) ** years),
        "Flujo equity descontado": equity_flow / ((1 + discount_rate) ** years),
    })

    project_flows = np.concatenate(([-capex], project_flow))
    equity_flows = np.concatenate(([-equity_amount], equity_flow))
    return df, project_flows, equity_flows

def min_avg_dscr(df):
    valid = df["DSCR"].dropna()
    if valid.empty:
        return np.nan, np.nan
    return float(valid.min()), float(valid.mean())
