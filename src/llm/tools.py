import json

TOOL_BUSCAR_SETORES_PROXIMOS = {
    "type": "function",
    "function": {
        "name": "buscar_setores_proximos",
        "description": (
            "Busca setores censitários próximos a um município ou coordenadas. "
            "Retorna setores dentro de um raio em km com indicadores de acesso à "
            "saúde (E2SFCA)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "municipio": {
                    "type": "string",
                    "description": "Nome do município de referência (ex: 'Campinas', 'São Paulo')",
                },
                "raio_km": {
                    "type": "number",
                    "description": "Raio de busca em quilômetros (padrão: 30)",
                    "default": 30,
                },
                "limite_e2sfca": {
                    "type": "number",
                    "description": "Filtrar setores com E2SFCA menor que este valor "
                    "(desertos médicos)",
                },
                "limite": {
                    "type": "integer",
                    "description": "Número máximo de resultados (padrão: 50, máx: 100)",
                    "default": 50,
                },
            },
            "required": ["municipio"],
        },
    },
}

TOOL_RANKING_MUNICIPIOS = {
    "type": "function",
    "function": {
        "name": "ranking_municipios",
        "description": (
            "Retorna ranking dos municípios de SP por indicador de saúde. Útil para "
            "'quais os piores municípios', 'ranking de acesso'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "indicador": {
                    "type": "string",
                    "enum": ["medicos_por_1k", "total_medicos", "total_cnes", "populacao"],
                    "description": "Indicador para ordenar (padrão: medicos_por_1k)",
                    "default": "medicos_por_1k",
                },
                "ordem": {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "description": "asc = menores primeiro (piores), desc = maiores primeiro",
                    "default": "asc",
                },
                "limite": {
                    "type": "integer",
                    "description": "Número de municípios no ranking (padrão: 10, máx: 100)",
                    "default": 10,
                },
            },
        },
    },
}

TOOL_COMPARAR_MUNICIPIOS = {
    "type": "function",
    "function": {
        "name": "comparar_municipios",
        "description": (
            "Retorna os indicadores AGREGADOS de 1 ou mais municípios: total_medicos, "
            "total_cnes, populacao, area_km2, medicos_por_1k, categoria_densidade. "
            "USE ESTA FERRAMENTA para perguntas sobre o TOTAL ou a QUANTIDADE de médicos, "
            "estabelecimentos, população ou área de um município "
            "(ex: 'quantos médicos tem São Paulo', 'total de médicos em Campinas'). "
            "Aceita também uma única lista com um município."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "municipios": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de nomes dos municípios (pode conter 1 só)",
                },
            },
            "required": ["municipios"],
        },
    },
}

TOOL_BUSCAR_SETORES_MUNICIPIO = {
    "type": "function",
    "function": {
        "name": "buscar_setores_municipio",
        "description": "Retorna setores censitários de um município e/ou de um DISTRITO/BAIRRO "
        "com os indicadores de acesso à saúde. Informe municipio e/ou distrito "
        "(pelo menos um; distrito sozinho também funciona, ex: distrito='Itaim Bibi'). "
        "Filtro opcional por nível de acesso (1 a 6). "
        "Responde com: total_setores (total que casa com o filtro), resumo (média de "
        "acessibilidade_e2sfca, distribuição por categoria e contagens — USE resumo para "
        "responder 'como é o acesso') e setores (até 100, ordenados do pior para o "
        "melhor acesso). "
        "ATENÇÃO: devolve setores INDIVIDUAIS, não totais do município. "
        "NUNCA some total_medicos_dentro — o raio de 5 km se sobrepõe entre setores e a "
        "soma superestima o total. Para totais de um município, use comparar_municipios.",
        "parameters": {
            "type": "object",
            "properties": {
                "municipio": {
                    "type": "string",
                    "description": "Nome do município (ex: 'São Paulo', 'Campinas')",
                },
                "distrito": {
                    "type": "string",
                    "description": "Nome do distrito ou bairro dentro do município "
                    "(ex: 'Itaim Bibi', 'Pinheiros', 'Pirituba'). Se souber o município, "
                    "informe também: existem distritos homônimos em municípios diferentes "
                    "(ex: 'Pinheiros' existe em São Paulo e em Lavrinhas).",
                },
                "categoria": {
                    "type": "integer",
                    "description": "Nível de acesso à saúde (1 a 6). "
                    "1 = Excelente (acesso muito alto), 2 = Bom (acesso alto), "
                    "3 = Moderado (acesso médio), 4 = Limitado (acesso baixo), "
                    "5 = Crítico (acesso muito baixo), 6 = Deserto médico (sem acesso).",
                    "minimum": 1,
                    "maximum": 6,
                },
            },
        },
    },
}

ALL_TOOLS = [
    TOOL_BUSCAR_SETORES_PROXIMOS,
    TOOL_RANKING_MUNICIPIOS,
    TOOL_COMPARAR_MUNICIPIOS,
    TOOL_BUSCAR_SETORES_MUNICIPIO,
]


def carregar_argumentos(bruto) -> dict:
    """Converte `tool_call.function.arguments` em dict, tolerando o que o modelo devolver.

    Groq/Ollama já devolvem dict quando a chamada foi bem formada, mas também
    devolvem `""`, JSON truncado ou JSON malformado — um `json.loads` direto
    derrubava a requisição inteira com `JSONDecodeError` (500).
    """
    if isinstance(bruto, dict):
        return bruto
    if not bruto:
        return {}
    try:
        dados = json.loads(bruto)
    except (json.JSONDecodeError, TypeError):
        return {}
    return dados if isinstance(dados, dict) else {}
