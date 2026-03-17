import pandas as pd
import streamlit as st

from core.model import evaluate_sensitivity
from utils.formatting import format_num, format_pct
from utils.exports import to_excel_bytes

def render_header(inputs, result):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cliente", inputs["client_name"])
    c2.metric("Proyecto", inputs["project_name"])
    c3.metric("Monto financiado", format_num(result["financed_amount"], inputs["currency"]))
    c4.metric("Aporte propio", format_num(result["equity_amount"], inputs["currency"]))

def render_summary_metrics(inputs, result):
    currency = inputs["currency"]
    cashflow_df = result["cashflow_df"]
    annual_debt = result["annual_debt"]
    first_year_savings = float(cashflow_df.iloc[0]["Ahorro/Ingreso"]) if not cashflow_df.empty else 0.0
    first_year_debt = float(annual_debt.iloc[0]["Servicio deuda"]) if not annual_debt.empty else 0.0

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
    k9.metric("ROI equity", "N/D" if pd.isna(result["equity_roi"]) else f"{result['equity_roi'] * 100:,.2f}%")
    k10.metric("Payback proyecto", "N/D" if result["project_pb"] is None else f"{result['project_pb']} años")
    k11.metric("Payback equity", "N/D" if result["equity_pb"] is None else f"{result['equity_pb']} años")
    k12.metric("DSCR promedio", "N/D" if pd.isna(result["dscr_avg"]) else f"{result['dscr_avg']:,.2f}x")

def render_tabs(inputs, result):
    tabs = st.tabs(["Dashboard", "Flujos", "Amortización", "Sensibilidad", "Descargas"])

    with tabs[0]:
        cashflow_df = result["cashflow_df"]
        st.line_chart(cashflow_df.set_index("Año")[["Ahorro/Ingreso", "EBITDA", "Flujo proyecto", "Flujo equity"]])
        st.line_chart(cashflow_df.set_index("Año")[["DSCR"]])

    with tabs[1]:
        st.dataframe(result["cashflow_df"], use_container_width=True)

    with tabs[2]:
        st.dataframe(result["amort_df"], use_container_width=True)

    with tabs[3]:
        if st.toggle("Calcular sensibilidad", value=False):
            choice = st.selectbox(
                "Variable de sensibilidad",
                [("Tarifa", "tariff0"), ("Generación", "annual_generation_kwh"), ("CAPEX", "capex"), ("OPEX", "opex0")],
                format_func=lambda x: x[0],
            )
            base_inputs = {k: v for k, v in inputs.items() if k not in ["project_name", "client_name", "currency"]}
            sens_df = evaluate_sensitivity(base_inputs, choice[1], [0.85, 0.95, 1.00, 1.05, 1.15])
            st.dataframe(sens_df, use_container_width=True)
        else:
            st.caption("Activa el cálculo solo cuando lo necesites.")

    with tabs[4]:
        if st.toggle("Preparar Excel", value=False):
            excel_bytes = to_excel_bytes({
                "Resumen": pd.DataFrame({
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
                }),
                "Flujos": result["cashflow_df"],
                "Amortizacion": result["amort_df"],
                "ServicioDeuda": result["annual_debt"],
            })
            st.download_button(
                "Descargar Excel del análisis",
                data=excel_bytes,
                file_name="xavier_finance_pro_lite.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        st.download_button(
            "Descargar flujos CSV",
            data=result["cashflow_df"].to_csv(index=False).encode("utf-8"),
            file_name="flujos_xavier_finance_pro_lite.csv",
            mime="text/csv",
        )
