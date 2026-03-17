import pandas as pd

def format_pct(value):
    return "N/D" if pd.isna(value) else f"{value * 100:,.2f}%"

def format_num(value, currency):
    return f"{currency} {value:,.2f}"
