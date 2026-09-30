import streamlit as st

from frontend.components.map import render_map, tem_pontos
from frontend.components.table import render_table
from frontend.utils import health_check, query_api

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


def _renderizar(msg: dict) -> None:
    """Rotina única para o primeiro desenho e para os reruns seguintes.

    Antes a resposta era desenhada só no run em que chegava, enquanto o
    histórico lia `msg["mapa"]` — que nunca era gravado. Resultado: o mapa e
    o erro sumiam no próximo rerun do Streamlit.
    """
    if msg.get("erro"):
        st.error(f"Erro: {msg['erro']}")
        return
    st.markdown(msg.get("content") or "")
    dados = msg.get("dados")
    if dados:
        render_table(dados)
        if tem_pontos(dados):
            render_map(dados, centro=msg.get("mapa_centro"), zoom=msg.get("mapa_zoom"))


# Chat
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        _renderizar(msg)

if pergunta := st.chat_input("Pergunte sobre saúde em SP..."):
    st.session_state.messages.append({"role": "user", "content": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    with st.chat_message("assistant"):
        with st.spinner("Consultando dados..."):
            try:
                result = query_api(pergunta)
                msg = {
                    "role": "assistant",
                    "content": result["resposta"],
                    "dados": result.get("dados"),
                    "mapa_centro": result.get("mapa_centro"),
                    "mapa_zoom": result.get("mapa_zoom"),
                }
            except Exception as e:
                # Persiste também o erro: sem isto a pergunta ficava no
                # histórico sem resposta nenhum, como se nunca tivesse sido
                # respondida.
                msg = {"role": "assistant", "content": None, "erro": str(e)}
        st.session_state.messages.append(msg)
        _renderizar(msg)
