"""Serialização: do resultado da ferramenta para o prompt, o chat e o mapa.

Três saídas com destinos diferentes e por isso separadas:

* `resumir_para_llm` — projeção compacta para o contexto do modelo;
* `mensagem_assistente` / `resposta_de_fallback` — forma das mensagens de chat;
* `calcular_mapa` — centro/zoom que o frontend usa para enquadrar os pontos.
"""

import json
import math

from src.config import LLM_AMOSTRA_LLM


def calcular_mapa(dados) -> tuple[list[float] | None, int]:
    """Centro e zoom do mapa a partir de **todos** os pontos georreferenciados.

    Antes o centro era o primeiro ponto (que, ordenado do pior para o melhor
    acesso, era sempre um canto do resultado) e o zoom era fixo em 11 — uma
    busca de 30 km quase não cabia na tela.
    """
    pontos = dados.get("setores", []) if isinstance(dados, dict) else dados
    if not isinstance(pontos, list):
        return None, 10

    lats: list[float] = []
    lons: list[float] = []
    for ponto in pontos:
        if not isinstance(ponto, dict):
            continue
        lat = ponto.get("latitude")
        if lat is None:
            lat = ponto.get("lat")
        lon = ponto.get("longitude")
        if lon is None:
            lon = ponto.get("lon")
        if lat is None or lon is None:
            continue
        try:
            lats.append(float(lat))
            lons.append(float(lon))
        except (TypeError, ValueError):
            continue

    if not lats:
        return None, 10

    centro = [sum(lats) / len(lats), sum(lons) / len(lons)]
    extensao = max(max(lats) - min(lats), max(lons) - min(lons))
    return centro, zoom_para(extensao)


def zoom_para(extensao_graus: float) -> int:
    """Zoom em que a extensão dos pontos ocupa ~600 px de uma tela de 700 px.

    Em `z` um grau ocupa `256 * 2**z / 360` px; resolvendo para 600 px.
    """
    if extensao_graus <= 0:
        return 12
    zoom = math.log2(600 * 360 / (extensao_graus * 256))
    return max(4, min(15, round(zoom)))


def mensagem_assistente(resposta: dict, chamadas: list[dict]) -> dict:
    return {
        "role": "assistant",
        "content": resposta.get("content") or "",
        "tool_calls": [
            {
                "id": chamada["id"],
                "type": "function",
                "function": {
                    "name": chamada["name"],
                    "arguments": json.dumps(chamada.get("arguments") or {}),
                },
            }
            for chamada in chamadas
        ],
    }


def resposta_de_fallback(ferramentas: list[str], dados, houve_chamada: bool) -> str:
    """Última linha de defesa quando o modelo devolve `content` vazio.

    Acontece com modelos de raciocínio que estouram `max_tokens` antes de
    escrever texto — sem isto a tela fica em branco.
    """
    ferramenta = ferramentas[-1] if ferramentas else None

    if isinstance(dados, dict) and "erro" in dados:
        return f"Não foi possível executar a ferramenta: {dados['erro']}"
    if isinstance(dados, dict) and dados.get("total_setores") is not None:
        total = dados["total_setores"]
        if total:
            return (
                f"A consulta retornou {total} setores. Os dados estão na tabela e no mapa ao lado."
            )
        return (
            "Nenhum setor encontrado com esses filtros. "
            "Ajuste o município, o distrito ou o nível de acesso."
        )
    if isinstance(dados, list):
        return f"A consulta retornou {len(dados)} registros. Veja a tabela e o mapa."
    if ferramenta:
        return "A consulta foi executada, mas o modelo não gerou texto."
    if houve_chamada:
        return "Não foi possível gerar uma resposta. Tente novamente."
    return "Não foi possível gerar uma resposta. Reformule a pergunta e tente de novo."


def sem_coordenadas(item: dict) -> dict:
    """Remove lat/lon: o mapa é do frontend, não do contexto do LLM.

    Cada par de coordenadas custava ~12 tokens por linha e bastava um `limite`
    grande para estourar o ITPM do tier free (7000 tokens/min).
    """
    return {k: v for k, v in item.items() if k not in ("latitude", "longitude")}


def resumir_para_llm(dados: list[dict] | dict) -> list[dict] | dict:
    """Projeção compacta do resultado da ferramenta para o contexto do LLM.

    Trata as duas formas de retorno: dict com `setores` (com resumo agregado
    já pronto) e listas crus (`ranking_municipios`, `comparar_municipios`,
    `buscar_setores_proximos`), que antes iam inteiras para o prompt.
    """
    if isinstance(dados, dict) and "setores" in dados:
        # A amostra já vem ordenada do pior para o melhor acesso (ORDER BY).
        amostra = [sem_coordenadas(s) for s in dados["setores"][:LLM_AMOSTRA_LLM]]
        return {
            "municipio": dados.get("municipio"),
            "distrito": dados.get("distrito"),
            "categoria": dados.get("categoria"),
            "total_setores": dados.get("total_setores"),
            "resumo": dados.get("resumo"),
            "amostra_ordenada_do_pior_para_o_melhor_acesso": amostra,
        }

    if isinstance(dados, list):
        itens = [sem_coordenadas(x) for x in dados[:LLM_AMOSTRA_LLM] if isinstance(x, dict)]
        return {"total_itens": len(dados), "itens": itens}

    return dados
