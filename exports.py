from io import BytesIO
import pandas as pd
import streamlit as st

@st.cache_data(show_spinner=False)
def to_excel_bytes(dataframes_dict):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in dataframes_dict.items():
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    return output.getvalue()
