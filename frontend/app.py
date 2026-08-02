import streamlit as st
import json

from frontend.utils import query_api, health_check
from frontend.components.map import render_map
from frontend.components.table import render_table

st.set_page_config(page_title="GeoIA_SUS", page_icon="🏥", layout="wide")

st.title("GeoIA_SUS")
st.caption("Assistente de saúde geoespacial com IA generativa — Estado de São Paulo")

# Sidebar
with st.sidebar:
    st.header("Sobre")
    st.markdown("""
    Pergunte sobre acesso à saúde em SP.

    **Exemplos:**
    - "Quais setores perto de Campinas têm acesso muito ruim?"
    - "Ranking dos municípios com menos médicos"
    - "Compare São Paulo com Guarulhos"
    - "Mostre os setores de Santos"
    """)
    if st.button("Verificar API"):
        try:
            status = health_check()
            st.success(f"API: {status['status']}")
        except Exception as e:
            st.error(f"API offline: {e}")

# Chat
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("dados"):
            render_table(msg["dados"])
        if msg.get("mapa"):
            render_map(msg["mapa"])

if pergunta := st.chat_input("Pergunte sobre saúde em SP..."):
    st.session_state.messages.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    with st.chat_message("assistant"):
        with st.spinner("Consultando dados..."):
            try:
                result = query_api(pergunta)
                st.markdown(result["resposta"])

                if result.get("dados"):
                    render_table(result["dados"])

                    dados_mapa = result["dados"]
                    if isinstance(dados_mapa, dict):
                        dados_mapa = dados_mapa.get("setores") or dados_mapa.get("dados") or []
                    has_coords = any(
                        d.get("latitude") or d.get("lat")
                        for d in dados_mapa
                        if isinstance(d, dict)
                    )
                    if has_coords:
                        render_map(result["dados"])

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": result["resposta"],
                    "dados": result.get("dados"),
                })
            except Exception as e:
                st.error(f"Erro: {e}")
