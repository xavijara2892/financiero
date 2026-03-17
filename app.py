from io import BytesIO

import numpy as np
import numpy_financial as npf
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Xavier Finance Pro Fast", layout="wide")

# ---------------------------
# Fast helpers
# ---------------------------
def format_pct(value):
    return "N/D" if pd.isna(value) else f"{value*100:,.2f}%"

def format_num(value, currency):
    return f"{currency} {value:,.2f}"

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

@st.cache_data(show_spinner=False)
def build_amortization(principal, annual_rate, years, payments_per_year, grace_periods=0):
    n = int(years * payments_per_year)
    periodic_rate = annual_rate / payments_per_year if payments_per_year else 0.0

    if n <= 0 or principal <= 0:
        return pd.DataFrame(columns=["Periodo", "Cuota", "Interés", "Abono a capital", "Saldo"]), 0.0

    effective_n = max(n - grace_periods, 1)
    cuota_regular = float(-npf.pmt(periodic_rate, effective_n, principal))

    balance = principal
    rows = []

    for period in range(1, n + 1):
        interest = balance * periodic_rate

        if period <= grace_periods:
            payment = interest
            principal_payment = 0.0
        else:
            payment = cuota_regular
            principal_payment = max(0.0, payment - interest)
            balance = max(0.0, balance - principal_payment)

        rows.append(
            {
                "Periodo": period,
                "Cuota": payment,
                "Interés": interest,
                "Abono a capital": principal_payment,
                "Saldo": balance,
            }
        )

    return pd.DataFrame(rows), cuota_regular

@st.cache_data(show_spinner=False)
def annualize_debt_service(amort_df, payments_per_year, years_to_show):
    full_years = pd.DataFrame({"Año": list(range(1, years_to_show + 1))})
    if amort_df.empty:
        full_years["Servicio deuda"] = 0.0
        return full_years

    temp = amort_df.copy()
    temp["Año"] = ((temp["Periodo"] - 1) // payments_per_year) + 1
    annual = temp.groupby("Año", as_index=False)["Cuota"].sum().rename(columns={"Cuota": "Servicio deuda"})
    return full_years.merge(annual, on="Año", how="left").fillna(0.0)

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
    replacement = np.where(years == major_replacement_year, major_replacement_cost, 0.0) if major_replacement_year > 0 else np.zeros_like(years, dtype=float)

    operating_cost = opex + corrective + replacement
    ebitda = revenue - operating_cost
    taxes = np.maximum(0.0, ebitda * tax_rate)
    fcf_project = ebitda - taxes

    debt_map = annual_debt_service_df.set_index("Año")["Servicio deuda"].to_dict()
    debt_service = np.array([debt_map.get(int(y), 0.0) for y in years], dtype=float)

    cfads = revenue - operating_cost
    fcf_equity = fcf_project - debt_service
    dscr = np.where(debt_service > 0, cfads / debt_service, np.nan)

    df = pd.DataFrame(
        {
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
            "Flujo proyecto": fcf_project,
            "Flujo equity": fcf_equity,
            "Flujo proyecto descontado": fcf_project / ((1 + discount_rate) ** years),
            "Flujo equity descontado": fcf_equity / ((1 + discount_rate) ** years),
        }
    )

    project_flows = np.concatenate(([-capex], fcf_project))
    equity_flows = np.concatenate(([-equity_amount], fcf_equity))
    return df, project_flows, equity_flows

def roi_from_flows(initial_investment, flows):
    if initial_investment == 0:
        return np.nan
    return (float(np.sum(flows[1:])) - initial_investment) / initial_investment

def min_avg_dscr(df):
    valid = df["DSCR"].dropna()
    if valid.empty:
        return np.nan, np.nan
    return float(valid.min()), float(valid.mean())

@st.cache_data(show_spinner=False)
def evaluate_model(inputs):
    capex = inputs["capex"]
    financed_pct = inputs["financed_pct"]
    financed_amount = capex * financed_pct
    equity_amount = capex - financed_amount

    amort_df, periodic_payment = build_amortization(
        financed_amount,
        inputs["interest_rate"],
        inputs["debt_years"],
        inputs["payments_per_year"],
        inputs["grace_periods"],
    )
    annual_debt = annualize_debt_service(amort_df, inputs["payments_per_year"], inputs["project_years"])

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

    project_npv = float(npf.npv(inputs["discount_rate"], project_flows[1:]) + project_flows[0])
    project_irr = float(npf.irr(project_flows)) if np.any(project_flows < 0) and np.any(project_flows > 0) else np.nan
    project_roi = roi_from_flows(capex, project_flows)
    project_pb = payback(project_flows)
    project_dpb = discounted_payback(inputs["discount_rate"], project_flows)

    equity_npv = float(npf.npv(inputs["discount_rate"], equity_flows[1:]) + equity_flows[0])
    equity_irr = float(npf.irr(equity_flows)) if np.any(equity_flows < 0) and np.any(equity_flows > 0) else np.nan
    equity_roi = roi_from_flows(equity_amount, equity_flows)
    equity_pb = payback(equity_flows)
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
        "project_irr": project_irr,
        "project_roi": project_roi,
        "project_pb": project_pb,
        "project_dpb": project_dpb,
        "equity_npv": equity_npv,
        "equity_irr": equity_irr,
        "equity_roi": equity_roi,
        "equity_pb": equity_pb,
        "equity_dpb": equity_dpb,
        "dscr_min": dscr_min,
        "dscr_avg": dscr_avg,
    }

@st.cache_data(show_spinner=False)
def make_sensitivity_table(base_inputs, field_name, factors):
    rows = []
    for factor in factors:
        local = dict(base_inputs)
        local[field_name] = base_inputs[field_name] * factor
        result = evaluate_model(local)
        rows.append(
            {
                "Escenario": f"{int((factor - 1) * 100):+d}%",
                "VAN proyecto": result["project_npv"],
                "TIR proyecto": result["project_irr"],
                "VAN equity": result["equity_npv"],
                "TIR equity": result["equity_irr"],
                "DSCR mínimo": result["dscr_min"],
            }
        )
    return pd.DataFrame(rows)

@st.cache_data(show_spinner=False)
def to_excel_bytes(dataframes_dict):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in dataframes_dict.items():
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return output.getvalue()

# ---------------------------
# UI
# ---------------------------
st.markdown("## Xavier Finance Pro Fast")
st.caption("Versión optimizada para evitar recálculo completo en cada cambio.")

default_inputs = {
    "project_name": "Proyecto Solar Xavier",
    "client_name": "Cliente Demo",
    "currency": "USD",
    "capex": 125000.0,
    "financed_pct": 0.70,
    "interest_rate": 0.08,
    "debt_years": 10,
    "payments_per_year": 12,
    "grace_periods": 0,
    "project_years": 20,
    "annual_generation_kwh": 190000.0,
    "degradation": 0.005,
    "tariff0": 0.17,
    "tariff_growth": 0.03,
    "opex0": 2600.0,
    "opex_growth": 0.02,
    "corrective0": 900.0,
    "corrective_growth": 0.02,
    "tax_rate": 0.00,
    "discount_rate": 0.10,
    "major_replacement_year": 12,
    "major_replacement_cost": 10000.0,
}

if "inputs" not in st.session_state:
    st.session_state.inputs = default_inputs.copy()

with st.sidebar:
    st.header("Configuración")
    with st.form("input_form"):
        project_name = st.text_input("Nombre del proyecto", value=st.session_state.inputs["project_name"])
        client_name = st.text_input("Cliente", value=st.session_state.inputs["client_name"])
        currency = st.selectbox("Moneda", ["USD", "CRC", "EUR"], index=["USD", "CRC", "EUR"].index(st.session_state.inputs["currency"]))

        st.subheader("CAPEX y estructura")
        capex = st.number_input("CAPEX / Presupuesto", min_value=0.0, value=float(st.session_state.inputs["capex"]), step=1000.0)
        financed_pct = st.slider("% financiado", 0, 100, int(st.session_state.inputs["financed_pct"] * 100), 5) / 100

        st.subheader("Deuda")
        interest_rate = st.number_input("Tasa interés anual (%)", min_value=0.0, value=float(st.session_state.inputs["interest_rate"] * 100), step=0.1) / 100
        debt_years = st.number_input("Plazo deuda (años)", min_value=1, value=int(st.session_state.inputs["debt_years"]), step=1)
        payments_per_year = st.selectbox("Pagos por año", [1, 2, 4, 12], index=[1, 2, 4, 12].index(st.session_state.inputs["payments_per_year"]))
        grace_periods = st.number_input("Períodos de gracia solo interés", min_value=0, value=int(st.session_state.inputs["grace_periods"]), step=1)

        st.subheader("Operación")
        project_years = st.number_input("Horizonte de análisis (años)", min_value=1, value=int(st.session_state.inputs["project_years"]), step=1)
        annual_generation_kwh = st.number_input("Generación anual estimada (kWh)", min_value=0.0, value=float(st.session_state.inputs["annual_generation_kwh"]), step=1000.0)
        degradation = st.number_input("Degradación anual (%)", min_value=0.0, value=float(st.session_state.inputs["degradation"] * 100), step=0.1) / 100
        tariff0 = st.number_input("Tarifa inicial energía", min_value=0.0, value=float(st.session_state.inputs["tariff0"]), step=0.01)
        tariff_growth = st.number_input("Crecimiento tarifa (%)", min_value=0.0, value=float(st.session_state.inputs["tariff_growth"] * 100), step=0.1) / 100

        st.subheader("Costos")
        opex0 = st.number_input("OPEX anual inicial", min_value=0.0, value=float(st.session_state.inputs["opex0"]), step=100.0)
        opex_growth = st.number_input("Crecimiento OPEX (%)", min_value=0.0, value=float(st.session_state.inputs["opex_growth"] * 100), step=0.1) / 100
        corrective0 = st.number_input("Mantenimiento correctivo inicial", min_value=0.0, value=float(st.session_state.inputs["corrective0"]), step=100.0)
        corrective_growth = st.number_input("Crecimiento correctivo (%)", min_value=0.0, value=float(st.session_state.inputs["corrective_growth"] * 100), step=0.1) / 100

        st.subheader("Impuestos y descuento")
        tax_rate = st.number_input("Tasa de impuesto (%)", min_value=0.0, value=float(st.session_state.inputs["tax_rate"] * 100), step=0.5) / 100
        discount_rate = st.number_input("Tasa de descuento / WACC (%)", min_value=0.0, value=float(st.session_state.inputs["discount_rate"] * 100), step=0.1) / 100

        st.subheader("Reposiciones")
        major_replacement_year = st.number_input("Año de reposición mayor (0 = ninguna)", min_value=0, value=int(st.session_state.inputs["major_replacement_year"]), step=1)
        major_replacement_cost = st.number_input("Costo reposición mayor", min_value=0.0, value=float(st.session_state.inputs["major_replacement_cost"]), step=500.0)

        submitted = st.form_submit_button("Actualizar análisis", use_container_width=True)

    if submitted:
        st.session_state.inputs = {
            "project_name": project_name,
            "client_name": client_name,
            "currency": currency,
            "capex": capex,
            "financed_pct": financed_pct,
            "interest_rate": interest_rate,
            "debt_years": int(debt_years),
            "payments_per_year": int(payments_per_year),
            "grace_periods": int(grace_periods),
            "project_years": int(project_years),
            "annual_generation_kwh": annual_generation_kwh,
            "degradation": degradation,
            "tariff0": tariff0,
            "tariff_growth": tariff_growth,
            "opex0": opex0,
            "opex_growth": opex_growth,
            "corrective0": corrective0,
            "corrective_growth": corrective_growth,
            "tax_rate": tax_rate,
            "discount_rate": discount_rate,
            "major_replacement_year": int(major_replacement_year),
            "major_replacement_cost": major_replacement_cost,
        }

inputs = st.session_state.inputs
result = evaluate_model({k: v for k, v in inputs.items() if k not in ["project_name", "client_name", "currency"]})

cashflow_df = result["cashflow_df"]
amort_df = result["amort_df"]
annual_debt = result["annual_debt"]
currency = inputs["currency"]

first_year_savings = float(cashflow_df.iloc[0]["Ahorro/Ingreso"]) if not cashflow_df.empty else 0.0
first_year_debt = float(annual_debt.iloc[0]["Servicio deuda"]) if not annual_debt.empty else 0.0

top1, top2, top3, top4 = st.columns(4)
top1.metric("Cliente", inputs["client_name"])
top2.metric("Proyecto", inputs["project_name"])
top3.metric("Monto financiado", format_num(result["financed_amount"], currency))
top4.metric("Aporte propio", format_num(result["equity_amount"], currency))

st.subheader("Resumen ejecutivo")
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Ingreso año 1", format_num(first_year_savings, currency))
k2.metric("Cuota periódica", format_num(result["periodic_payment"], currency))
k3.metric("Servicio deuda año 1", format_num(first_year_debt, currency))
k4.metric("VAN proyecto", format_num(result["project_npv"], currency))
k5.metric("TIR proyecto", format_pct(result["project_irr"]))
k6.metric("DSCR mínimo", "N/D" if pd.isna(result["dscr_min"]) else f"{result['dscr_min']:,.2f}x")

k7, k8, k9, k10, k11, k12 = st.columns(6)
k7.metric("VAN equity", format_num(result["equity_npv"], currency))
k8.metric("TIR equity", format_pct(result["equity_irr"]))
k9.metric("ROI equity", "N/D" if pd.isna(result["equity_roi"]) else f"{result['equity_roi']*100:,.2f}%")
k10.metric("Payback proyecto", "N/D" if result["project_pb"] is None else f"{result['project_pb']} años")
k11.metric("Payback equity", "N/D" if result["equity_pb"] is None else f"{result['equity_pb']} años")
k12.metric("DSCR promedio", "N/D" if pd.isna(result["dscr_avg"]) else f"{result['dscr_avg']:,.2f}x")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Dashboard", "Flujos", "Amortización", "Sensibilidad", "Descargas"])

with tab1:
    st.line_chart(cashflow_df.set_index("Año")[["Ahorro/Ingreso", "EBITDA", "Flujo proyecto", "Flujo equity"]])
    st.line_chart(cashflow_df.set_index("Año")[["DSCR"]])

with tab2:
    st.dataframe(cashflow_df, use_container_width=True)

with tab3:
    st.dataframe(amort_df, use_container_width=True)
    if not amort_df.empty:
        st.line_chart(amort_df.set_index("Periodo")[["Interés", "Abono a capital", "Saldo"]])

with tab4:
    run_sensitivity = st.toggle("Calcular sensibilidad", value=False)
    if run_sensitivity:
        sens_choice = st.selectbox(
            "Variable de sensibilidad",
            [("Tarifa", "tariff0"), ("Generación", "annual_generation_kwh"), ("CAPEX", "capex"), ("OPEX", "opex0")],
            format_func=lambda x: x[0],
        )
        sens_df = make_sensitivity_table(
            {k: v for k, v in inputs.items() if k not in ["project_name", "client_name", "currency"]},
            sens_choice[1],
            [0.85, 0.95, 1.00, 1.05, 1.15],
        )
        st.dataframe(sens_df, use_container_width=True)
    else:
        st.caption("Activa el cálculo solo cuando lo necesites para acelerar la app.")

with tab5:
    prepare_excel = st.toggle("Preparar archivo Excel", value=False)
    if prepare_excel:
        excel_bytes = to_excel_bytes(
            {
                "Resumen": pd.DataFrame(
                    {
                        "Proyecto": [inputs["project_name"]],
                        "Cliente": [inputs["client_name"]],
                        "CAPEX": [inputs["capex"]],
                        "Financiado": [result["financed_amount"]],
                        "Equity": [result["equity_amount"]],
                        "VAN proyecto": [result["project_npv"]],
                        "TIR proyecto": [result["project_irr"]],
                        "VAN equity": [result["equity_npv"]],
                        "TIR equity": [result["equity_irr"]],
                        "DSCR mínimo": [result["dscr_min"]],
                    }
                ),
                "Flujos": cashflow_df,
                "Amortizacion": amort_df,
                "ServicioDeuda": annual_debt,
            }
        )
        st.download_button(
            "Descargar Excel del análisis",
            data=excel_bytes,
            file_name="xavier_finance_pro_fast.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    st.download_button(
        "Descargar flujos CSV",
        data=cashflow_df.to_csv(index=False).encode("utf-8"),
        file_name="flujos_xavier_finance_pro_fast.csv",
        mime="text/csv",
    )
