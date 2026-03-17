import streamlit as st

from data.defaults import DEFAULT_INPUTS
from core.model import evaluate_model
from ui.sidebar import render_sidebar
from ui.dashboard import render_header, render_summary_metrics, render_tabs

st.set_page_config(page_title="Xavier Finance Pro Lite", layout="wide")

st.title("Xavier Finance Pro Lite")
st.caption("Versión modular y más ligera para análisis financiero de proyectos energéticos.")

if "inputs" not in st.session_state:
    st.session_state.inputs = DEFAULT_INPUTS.copy()

new_inputs = render_sidebar(st.session_state.inputs)
if new_inputs is not None:
    st.session_state.inputs = new_inputs

inputs = st.session_state.inputs
model_inputs = {k: v for k, v in inputs.items() if k not in ["project_name", "client_name", "currency"]}

result = evaluate_model(model_inputs)

render_header(inputs, result)
render_summary_metrics(inputs, result)
render_tabs(inputs, result)
