import streamlit as st

def render_sidebar(current_inputs):
    with st.sidebar:
        st.header("Configuración")
        with st.form("input_form"):
            project_name = st.text_input("Nombre del proyecto", value=current_inputs["project_name"])
            client_name = st.text_input("Cliente", value=current_inputs["client_name"])
            currency = st.selectbox(
                "Moneda",
                ["USD", "CRC", "EUR"],
                index=["USD", "CRC", "EUR"].index(current_inputs["currency"]),
            )

            st.subheader("CAPEX y estructura")
            capex = st.number_input("CAPEX / Presupuesto", min_value=0.0, value=float(current_inputs["capex"]), step=1000.0)
            financed_pct = st.slider("% financiado", 0, 100, int(current_inputs["financed_pct"] * 100), 5) / 100

            st.subheader("Deuda")
            interest_rate = st.number_input("Tasa interés anual (%)", min_value=0.0, value=float(current_inputs["interest_rate"] * 100), step=0.1) / 100
            debt_years = st.number_input("Plazo deuda (años)", min_value=1, value=int(current_inputs["debt_years"]), step=1)
            payments_per_year = st.selectbox("Pagos por año", [1, 2, 4, 12], index=[1, 2, 4, 12].index(current_inputs["payments_per_year"]))
            grace_periods = st.number_input("Períodos de gracia solo interés", min_value=0, value=int(current_inputs["grace_periods"]), step=1)

            st.subheader("Operación")
            project_years = st.number_input("Horizonte de análisis (años)", min_value=1, value=int(current_inputs["project_years"]), step=1)
            annual_generation_kwh = st.number_input("Generación anual estimada (kWh)", min_value=0.0, value=float(current_inputs["annual_generation_kwh"]), step=1000.0)
            degradation = st.number_input("Degradación anual (%)", min_value=0.0, value=float(current_inputs["degradation"] * 100), step=0.1) / 100
            tariff0 = st.number_input("Tarifa inicial energía", min_value=0.0, value=float(current_inputs["tariff0"]), step=0.01)
            tariff_growth = st.number_input("Crecimiento tarifa (%)", min_value=0.0, value=float(current_inputs["tariff_growth"] * 100), step=0.1) / 100

            st.subheader("Costos")
            opex0 = st.number_input("OPEX anual inicial", min_value=0.0, value=float(current_inputs["opex0"]), step=100.0)
            opex_growth = st.number_input("Crecimiento OPEX (%)", min_value=0.0, value=float(current_inputs["opex_growth"] * 100), step=0.1) / 100
            corrective0 = st.number_input("Mantenimiento correctivo inicial", min_value=0.0, value=float(current_inputs["corrective0"]), step=100.0)
            corrective_growth = st.number_input("Crecimiento correctivo (%)", min_value=0.0, value=float(current_inputs["corrective_growth"] * 100), step=0.1) / 100

            st.subheader("Impuestos y descuento")
            tax_rate = st.number_input("Tasa de impuesto (%)", min_value=0.0, value=float(current_inputs["tax_rate"] * 100), step=0.5) / 100
            discount_rate = st.number_input("Tasa de descuento / WACC (%)", min_value=0.0, value=float(current_inputs["discount_rate"] * 100), step=0.1) / 100

            st.subheader("Reposiciones")
            major_replacement_year = st.number_input("Año de reposición mayor (0 = ninguna)", min_value=0, value=int(current_inputs["major_replacement_year"]), step=1)
            major_replacement_cost = st.number_input("Costo reposición mayor", min_value=0.0, value=float(current_inputs["major_replacement_cost"]), step=500.0)

            submitted = st.form_submit_button("Actualizar análisis", use_container_width=True)

    if not submitted:
        return None

    return {
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
