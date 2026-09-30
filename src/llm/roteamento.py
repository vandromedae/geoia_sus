"""Roteamento de pergunta: o que o GeoIA_SUS aceita e o que recusa cedo.

O gate roda **antes** de qualquer chamada de LLM. Sem ele uma pergunta
qualquer virava uma rodada de modelo (e, no tier free, cota de TPM) só para
o assistente responder "não sei".
"""

SCOPE_KEYWORDS = [
    "saúde",
    "saude",
    "médico",
    "medico",
    "médicos",
    "medicos",
    "hospital",
    "ubs",
    "posto de saúde",
    "posto de saude",
    "atenção primaria",
    "atencao primaria",
    "acesso",
    "e2sfca",
    "densidade",
    "população",
    "populacao",
    "setor",
    "município",
    "municipio",
    "campinas",
    "santos",
    "são paulo",
    "sao paulo",
    "guarulhos",
    "sorocaba",
    "ranking",
    "comparar",
    "comparação",
    "comparacao",
    "compare",
    "cnes",
    "leito",
    "leitos",
    "enfermeiro",
    "enfermeiros",
    "dentista",
    "farmácia",
    "farmacia",
    "mostre",
    "exiba",
    "liste",
]

MENSAGEM_FORA_DE_ESCOPO = (
    "Essa pergunta está fora do escopo do GeoIA_SUS. "
    "Posso ajudar com perguntas sobre acesso à saúde, densidade "
    "de médicos, e dados do SUS no Estado de São Paulo."
)


def dentro_do_escopo(pergunta: str) -> bool:
    pergunta_lower = pergunta.lower()
    return any(kw in pergunta_lower for kw in SCOPE_KEYWORDS)
