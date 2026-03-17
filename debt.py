import numpy as np
import pandas as pd
import numpy_financial as npf
import streamlit as st

@st.cache_data(show_spinner=False)
def build_amortization(principal, annual_rate, years, payments_per_year, grace_periods=0):
    n = int(years * payments_per_year)
    periodic_rate = annual_rate / payments_per_year if payments_per_year else 0.0

    if n <= 0 or principal <= 0:
        cols = ["Periodo", "Cuota", "Interés", "Abono a capital", "Saldo"]
        return pd.DataFrame(columns=cols), 0.0

    effective_n = max(n - grace_periods, 1)
    regular_payment = float(-npf.pmt(periodic_rate, effective_n, principal))

    balance = principal
    rows = []
    for period in range(1, n + 1):
        interest = balance * periodic_rate
        if period <= grace_periods:
            payment = interest
            principal_payment = 0.0
        else:
            payment = regular_payment
            principal_payment = max(0.0, payment - interest)
            balance = max(0.0, balance - principal_payment)

        rows.append({
            "Periodo": period,
            "Cuota": payment,
            "Interés": interest,
            "Abono a capital": principal_payment,
            "Saldo": balance,
        })

    return pd.DataFrame(rows), regular_payment

@st.cache_data(show_spinner=False)
def annualize_debt_service(amort_df, payments_per_year, years_to_show):
    full_years = pd.DataFrame({"Año": list(range(1, years_to_show + 1))})
    if amort_df.empty:
        full_years["Servicio deuda"] = 0.0
        return full_years

    temp = amort_df.copy()
    temp["Año"] = ((temp["Periodo"] - 1) // payments_per_year) + 1
    annual = temp.groupby("Año", as_index=False)["Cuota"].sum()
    annual = annual.rename(columns={"Cuota": "Servicio deuda"})
    return full_years.merge(annual, on="Año", how="left").fillna(0.0)
