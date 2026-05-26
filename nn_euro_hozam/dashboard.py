import streamlit as st
from db import query_all
import pandas as pd

df = pd.DataFrame(query_all(), columns=['id', 'asset_name', 'date', 'opening_value', 'closing_value', 'period_yield'])
st.title("NN Euro Yields Dashboard")
st.dataframe(df)


