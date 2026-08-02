import streamlit as st
import folium
from streamlit_folium import st_folium


def render_map(dados: list[dict] | dict):
    if isinstance(dados, dict):
        dados = dados.get("setores") or dados.get("dados") or [dados]
    if not dados:
        return

    coords = []
    for row in dados:
        lat = row.get("latitude") or row.get("lat")
        lon = row.get("longitude") or row.get("lon")
        if lat and lon:
            try:
                coords.append((float(lat), float(lon)))
            except (ValueError, TypeError):
                continue

    if not coords:
        st.info("Sem coordenadas disponíveis para exibir mapa.")
        return

    center_lat = sum(c[0] for c in coords) / len(coords)
    center_lon = sum(c[1] for c in coords) / len(coords)

    m = folium.Map(location=[center_lat, center_lon], zoom_start=11)

    for row in dados:
        lat = row.get("latitude") or row.get("lat")
        lon = row.get("longitude") or row.get("lon")
        if not lat or not lon:
            continue
        try:
            lat, lon = float(lat), float(lon)
        except (ValueError, TypeError):
            continue

        nome = row.get("nm_mun") or row.get("cod_setor") or ""
        e2sfca = row.get("acessibilidade_e2sfca")
        cat = row.get("categoria_acesso")

        from html import escape

        popup_parts = [f"<b>{escape(str(nome))}</b>"]
        if e2sfca is not None:
            popup_parts.append(f"E2SFCA: {e2sfca:.4f}")
        if cat:
            popup_parts.append(f" Categoria: {escape(str(cat))}")

        color = "red"
        if cat:
            cat_lower = cat.lower()
            if "bom" in cat_lower or "alto" in cat_lower:
                color = "green"
            elif "moderad" in cat_lower or "medio" in cat_lower or "médio" in cat_lower:
                color = "orange"

        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            color=color,
            fill=True,
            fill_opacity=0.7,
            popup=folium.Popup("<br>".join(popup_parts), max_width=250),
        ).add_to(m)

    st_folium(m, width=700, height=500)
