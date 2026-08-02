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
                    "description": "Número máximo de resultados (padrão: 50)",
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
                    "description": "Número de municípios no ranking (padrão: 10)",
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
            "Compara indicadores de saúde entre 2 ou mais municípios. Retorna dados lado a lado."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "municipios": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de nomes dos municípios para comparar",
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
        "description": "Retorna os setores de um município com seus indicadores de acesso à saúde, "
        "com filtro opcional por nível de acesso (1 a 6). "
        "Responde com um resumo: total_setores (total de setores que casam) e "
        "setores (lista de até 100 setores). Use total_setores na resposta ao usuário.",
        "parameters": {
            "type": "object",
            "properties": {
                "municipio": {
                    "type": "string",
                    "description": "Nome do município",
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
            "required": ["municipio"],
        },
    },
}

ALL_TOOLS = [
    TOOL_BUSCAR_SETORES_PROXIMOS,
    TOOL_RANKING_MUNICIPIOS,
    TOOL_COMPARAR_MUNICIPIOS,
    TOOL_BUSCAR_SETORES_MUNICIPIO,
]
