import re
from html import escape

import folium
import streamlit as st
from streamlit_folium import st_folium


def _coordenadas(row: dict) -> tuple[float, float] | None:
    lat = row.get("latitude")
    if lat is None:
        lat = row.get("lat")
    lon = row.get("longitude")
    if lon is None:
        lon = row.get("lon")
    # `is None` e não truthiness: 0.0 é coordenada válida.
    if lat is None or lon is None:
        return None
    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return None


def _linhas(dados: list[dict] | dict) -> list[dict]:
    if isinstance(dados, dict):
        dados = dados.get("setores") or dados.get("dados") or [dados]
    if not isinstance(dados, list):
        return []
    return [linha for linha in dados if isinstance(linha, dict)]


def tem_pontos(dados: list[dict] | dict) -> bool:
    """True se houver ao menos um ponto plotável.

    Sem isto o app chamava `render_map` para qualquer resultado e ouvia
    "Sem coordenadas disponíveis" em rankings e comparações.
    """
    return any(_coordenadas(linha) for linha in _linhas(dados))


def _cor_de(row: dict) -> str:
    """1-2 verde, 3 laranja, 4-6 vermelho.

    Prefere o número de `categoria_acesso` ("3. Moderado (acesso médio)") a
    casar texto — "4. Limitado (acesso baixo)" e "6. Deserto médico" também
    contêm a palavra "baixo".
    """
    categoria = str(row.get("categoria_acesso") or "")
    casamento = re.match(r"\s*(\d+)", categoria)
    if casamento:
        return {1: "green", 2: "green", 3: "orange"}.get(int(casamento.group(1)), "red")
    texto = categoria.casefold()
    if "excelente" in texto or "bom" in texto:
        return "green"
    if "moderad" in texto or "médio" in texto or "medio" in texto:
        return "orange"
    return "red"


def _titulo(row: dict) -> str:
    local = " — ".join(str(v) for v in (row.get("nm_mun"), row.get("nm_dist")) if v)
    if local:
        return local
    return str(row.get("cd_setor") or row.get("cod_setor") or row.get("nm_mun") or "")


def render_map(
    dados: list[dict] | dict,
    centro: list[float] | None = None,
    zoom: int | None = None,
):
    linhas = [linha for linha in _linhas(dados) if _coordenadas(linha)]
    if not linhas:
        st.info("Sem coordenadas disponíveis para exibir mapa.")
        return

    coords = [_coordenadas(linha) for linha in linhas]
    coords = [c for c in coords if c is not None]
    media = [sum(c[0] for c in coords) / len(coords), sum(c[1] for c in coords) / len(coords)]

    # `mapa_centro`/`mapa_zoom` vêm prontos da API; a média local é o plano B
    # para quando a resposta não os trouxer.
    location = media
    if centro and len(centro) == 2:
        try:
            location = [float(centro[0]), float(centro[1])]
        except (TypeError, ValueError):
            location = media

    m = folium.Map(location=location, zoom_start=int(zoom) if zoom is not None else 11)

    for row in linhas:
        ponto = _coordenadas(row)
        if ponto is None:
            continue
        lat, lon = ponto

        titulo = escape(_titulo(row))
        popup_parts = [f"<b>{titulo}</b>"]
        e2sfca = row.get("acessibilidade_e2sfca")
        if e2sfca is not None:
            popup_parts.append(f"E2SFCA: {e2sfca:.4f}")
        if row.get("categoria_acesso"):
            popup_parts.append(f" Categoria: {escape(str(row['categoria_acesso']))}")

        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            color=_cor_de(row),
            fill=True,
            fill_opacity=0.7,
            popup=folium.Popup("<br>".join(popup_parts), max_width=250),
        ).add_to(m)

    st_folium(m, width=700, height=500)
