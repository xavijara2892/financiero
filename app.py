from io import BytesIO
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Xavier Finance Pro", layout="wide")

def pmt(rate, nper, pv):
    if nper <= 0:
        return 0.0
    if rate == 0:
        return pv / nper
    return (rate * pv) / (1 - (1 + rate) ** (-nper))

def npv(rate, cashflows):
    return sum(cf / ((1 + rate) ** i) for i, cf in enumerate(cashflows))

def irr(cashflows, guess=0.10):
    x = guess
    for _ in range(100):
        f = sum(cf / ((1 + x) ** i) for i, cf in enumerate(cashflows))
        df = sum(-i * cf / ((1 + x) ** (i + 1)) for i, cf in enumerate(cashflows) if i > 0)
        if abs(df) < 1e-12:
            break
        new_x = x - f / df
        if new_x <= -0.9999:
            break
        if abs(new_x - x) < 1e-10:
            return new_x
        x = new_x

    grid = np.linspace(-0.95, 2.5, 12000)
    vals = [npv(r, cashflows) for r in grid]
    for i in range(len(vals) - 1):
        if vals[i] == 0:
            return grid[i]
        if vals[i] * vals[i + 1] < 0:
            return grid[i]
    return np.nan

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

def format_pct(value):
    return "N/D" if pd.isna(value) else f"{value*100:,.2f}%"

def format_num(value, currency):
    return f"{currency} {value:,.2f}"

def build_amortization(principal, annual_rate, years, payments_per_year, grace_periods=0):
    n = int(years * payments_per_year)
    periodic_rate = annual_rate / payments_per_year if payments_per_year else 0.0

    if n <= 0 or principal <= 0:
        return pd.DataFrame(columns=["Periodo", "Cuota", "Interés", "Abono a capital", "Saldo"]), 0.0

    effective_n = max(n - grace_periods, 1)
    cuota_regular = pmt(periodic_rate, effective_n, principal)

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

def annualize_debt_service(amort_df, payments_per_year, years_to_show):
    full_years = pd.DataFrame({"Año": list(range(1, years_to_show + 1))})
    if amort_df.empty:
        full_years["Servicio deuda"] = 0.0
        return full_years

    temp = amort_df.copy()
    temp["Año"] = ((temp["Periodo"] - 1) // payments_per_year) + 1
    annual = temp.groupby("Año", as_index=False)["Cuota"].sum().rename(columns={"Cuota": "Servicio deuda"})
    return full_years.merge(annual, on="Año", how="left").fillna(0.0)

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
    rows = []
    project_flows = [-capex]
    equity_flows = [-equity_amount]

    for year in range(1, project_years + 1):
        generation = annual_generation_kwh * ((1 - degradation) ** (year - 1))
        tariff = tariff0 * ((1 + tariff_growth) ** (year - 1))
        revenue = generation * tariff

        opex = opex0 * ((1 + opex_growth) ** (year - 1))
        corrective = corrective0 * ((1 + corrective_growth) ** (year - 1))
        replacement = major_replacement_cost if (major_replacement_year > 0 and year == major_replacement_year) else 0.0

        operating_cost = opex + corrective + replacement
        ebitda = revenue - operating_cost
        taxes = max(0.0, ebitda * tax_rate)
        fcf_project = ebitda - taxes

        debt_service = 0.0
        matched = annual_debt_service_df.loc[annual_debt_service_df["Año"] == year, "Servicio deuda"]
        if len(matched) > 0:
            debt_service = float(matched.iloc[0])

        cfads = revenue - operating_cost
        fcf_equity = fcf_project - debt_service
        dscr = (cfads / debt_service) if debt_service > 0 else np.nan

        rows.append(
            {
                "Año": year,
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
                "Flujo proyecto descontado": fcf_project / ((1 + discount_rate) ** year),
                "Flujo equity descontado": fcf_equity / ((1 + discount_rate) ** year),
            }
        )

        project_flows.append(fcf_project)
        equity_flows.append(fcf_equity)

    return pd.DataFrame(rows), project_flows, equity_flows

def roi_from_flows(initial_investment, flows):
    if initial_investment == 0:
        return np.nan
    return (sum(flows[1:]) - initial_investment) / initial_investment

def min_avg_dscr(df):
    valid = df["DSCR"].dropna()
    if valid.empty:
        return np.nan, np.nan
    return valid.min(), valid.mean()

def to_excel_bytes(dataframes_dict):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in dataframes_dict.items():
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return output.getvalue()

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

    project_npv = npv(inputs["discount_rate"], project_flows)
    project_irr = irr(project_flows)
    project_roi = roi_from_flows(capex, project_flows)
    project_pb = payback(project_flows)
    project_dpb = discounted_payback(inputs["discount_rate"], project_flows)

    equity_npv = npv(inputs["discount_rate"], equity_flows)
    equity_irr = irr(equity_flows)
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

def make_sensitivity_table(base_inputs, field_name, factors):
    rows = []
    for factor in factors:
        local = base_inputs.copy()
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

st.markdown(
    """
    <style>
    .main-title {font-size: 2.1rem; font-weight: 700; margin-bottom: 0.1rem;}
    .sub-title {color: #6b7280; margin-bottom: 1rem;}
    .box-note {padding: 0.8rem 1rem; border: 1px solid rgba(120,120,120,0.2); border-radius: 0.8rem; margin-bottom: 1rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">Xavier Finance Pro</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Calculadora financiera profesional para freelancers y proyectos energéticos</div>', unsafe_allow_html=True)

col_a, col_b = st.columns([2, 1])
with col_a:
    st.markdown(
        """
        <div class="box-note">
        Modela financiamiento, flujos del proyecto, flujos del inversionista, DSCR, escenarios y sensibilidad.
        </div>
        """,
        unsafe_allow_html=True,
    )
with col_b:
    st.info("Lista para usar en propuestas, prefactibilidad y análisis rápido.")

with st.sidebar:
    st.header("Configuración")
    project_name = st.text_input("Nombre del proyecto", value="Proyecto Solar Xavier")
    client_name = st.text_input("Cliente", value="Cliente Demo")
    currency = st.selectbox("Moneda", ["USD", "CRC", "EUR"], index=0)

    st.subheader("CAPEX y estructura")
    capex = st.number_input("CAPEX / Presupuesto", min_value=0.0, value=125000.0, step=1000.0)
    financed_pct = st.slider("% financiado", 0, 100, 70, 5) / 100

    st.subheader("Deuda")
    interest_rate = st.number_input("Tasa interés anual (%)", min_value=0.0, value=8.0, step=0.1) / 100
    debt_years = st.number_input("Plazo deuda (años)", min_value=1, value=10, step=1)
    payments_per_year = st.selectbox("Pagos por año", [1, 2, 4, 12], index=3)
    grace_periods = st.number_input("Períodos de gracia solo interés", min_value=0, value=0, step=1)

    st.subheader("Operación")
    project_years = st.number_input("Horizonte de análisis (años)", min_value=1, value=20, step=1)
    annual_generation_kwh = st.number_input("Generación anual estimada (kWh)", min_value=0.0, value=190000.0, step=1000.0)
    degradation = st.number_input("Degradación anual (%)", min_value=0.0, value=0.5, step=0.1) / 100
    tariff0 = st.number_input("Tarifa inicial energía", min_value=0.0, value=0.17, step=0.01)
    tariff_growth = st.number_input("Crecimiento tarifa (%)", min_value=0.0, value=3.0, step=0.1) / 100

    st.subheader("Costos")
    opex0 = st.number_input("OPEX anual inicial", min_value=0.0, value=2600.0, step=100.0)
    opex_growth = st.number_input("Crecimiento OPEX (%)", min_value=0.0, value=2.0, step=0.1) / 100
    corrective0 = st.number_input("Mantenimiento correctivo inicial", min_value=0.0, value=900.0, step=100.0)
    corrective_growth = st.number_input("Crecimiento correctivo (%)", min_value=0.0, value=2.0, step=0.1) / 100

    st.subheader("Impuestos y descuento")
    tax_rate = st.number_input("Tasa de impuesto (%)", min_value=0.0, value=0.0, step=0.5) / 100
    discount_rate = st.number_input("Tasa de descuento / WACC (%)", min_value=0.0, value=10.0, step=0.1) / 100

    st.subheader("Reposiciones")
    major_replacement_year = st.number_input("Año de reposición mayor (0 = ninguna)", min_value=0, value=12, step=1)
    major_replacement_cost = st.number_input("Costo reposición mayor", min_value=0.0, value=10000.0, step=500.0)

base_inputs = {
    "capex": capex,
    "financed_pct": financed_pct,
    "interest_rate": interest_rate,
    "debt_years": debt_years,
    "payments_per_year": payments_per_year,
    "grace_periods": grace_periods,
    "project_years": project_years,
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
    "major_replacement_year": major_replacement_year,
    "major_replacement_cost": major_replacement_cost,
}

result = evaluate_model(base_inputs)
cashflow_df = result["cashflow_df"]
amort_df = result["amort_df"]
annual_debt = result["annual_debt"]

first_year_savings = float(cashflow_df.iloc[0]["Ahorro/Ingreso"]) if not cashflow_df.empty else 0.0
first_year_debt = float(annual_debt.iloc[0]["Servicio deuda"]) if not annual_debt.empty else 0.0

top1, top2, top3, top4 = st.columns(4)
top1.metric("Cliente", client_name)
top2.metric("Proyecto", project_name)
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

if not pd.isna(result["dscr_min"]):
    if result["dscr_min"] >= 1.20:
        st.success("La cobertura de deuda luce saludable bajo este escenario.")
    elif result["dscr_min"] >= 1.00:
        st.warning("La cobertura de deuda es ajustada. Conviene revisar tasa, plazo o CAPEX.")
    else:
        st.error("La cobertura de deuda es débil. El proyecto podría no sostener el servicio de deuda.")

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
    sens_choice = st.selectbox(
        "Variable de sensibilidad",
        [("Tarifa", "tariff0"), ("Generación", "annual_generation_kwh"), ("CAPEX", "capex"), ("OPEX", "opex0")],
        format_func=lambda x: x[0],
    )
    sens_df = make_sensitivity_table(base_inputs, sens_choice[1], [0.85, 0.95, 1.00, 1.05, 1.15])
    st.dataframe(sens_df, use_container_width=True)

with tab5:
    excel_bytes = to_excel_bytes(
        {
            "Resumen": pd.DataFrame(
                {
                    "Proyecto": [project_name],
                    "Cliente": [client_name],
                    "CAPEX": [capex],
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
        file_name="xavier_finance_pro.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.download_button(
        "Descargar flujos CSV",
        data=cashflow_df.to_csv(index=False).encode("utf-8"),
        file_name="flujos_xavier_finance_pro.csv",
        mime="text/csv",
    )
