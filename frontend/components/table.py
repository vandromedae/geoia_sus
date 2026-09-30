import pandas as pd
import streamlit as st


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
    # `use_container_width` está depreciado desde o Streamlit 1.49 e some
    # depois de 2025-12-31; `width="stretch"` é o equivalente (e o default).
    st.dataframe(df, width="stretch", hide_index=True)
