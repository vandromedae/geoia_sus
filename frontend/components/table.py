import streamlit as st
import pandas as pd


def render_table(dados: list[dict] | dict):
    if isinstance(dados, dict):
        total = dados.get("total_setores")
        dados = dados.get("setores") or dados.get("dados") or [dados]
    else:
        total = None
    if not dados:
        return

    df = pd.DataFrame(dados)
    if total:
        st.caption(f"Total de setores: {total}")
    st.dataframe(df, use_container_width=True, hide_index=True)
