from sqlalchemy import text

from src.services.spatial import (
    buscar_setores_municipio_db,
    buscar_setores_proximos_db,
    comparar_municipios_db,
    ranking_municipios_db,
    resumo_setores_db,
)


class TestBuscarSetoresProximos:
    def test_retorna_setores(self, db_session):
        rows = buscar_setores_proximos_db(db_session, municipio="Adamantina", raio_km=50)
        assert len(rows) > 0

    def test_ordenado_por_e2sfca(self, db_session):
        rows = buscar_setores_proximos_db(db_session, municipio="Adamantina", raio_km=50)
        e2sfcas = [r.acessibilidade_e2sfca for r in rows if r.acessibilidade_e2sfca is not None]
        assert e2sfcas == sorted(e2sfcas)

    def test_filtro_e2sfca(self, db_session):
        rows = buscar_setores_proximos_db(
            db_session, municipio="Adamantina", raio_km=50, limite_e2sfca=0.05
        )
        for r in rows:
            if r.acessibilidade_e2sfca is not None:
                assert r.acessibilidade_e2sfca < 0.05

    def test_limite(self, db_session):
        rows = buscar_setores_proximos_db(db_session, municipio="Adamantina", raio_km=100, limite=5)
        assert len(rows) <= 5

    def test_municipio_inexistente(self, db_session):
        rows = buscar_setores_proximos_db(db_session, municipio="CidadeFantasma", raio_km=30)
        assert rows == []


class TestRankingMunicipios:
    def test_ranking_asc(self, db_session):
        rows = ranking_municipios_db(db_session, indicador="medicos_por_1k", ordem="asc", limite=5)
        assert len(rows) > 0
        values = [r.medicos_por_1k for r in rows if r.medicos_por_1k is not None]
        assert values == sorted(values)

    def test_ranking_desc(self, db_session):
        rows = ranking_municipios_db(db_session, indicador="medicos_por_1k", ordem="desc", limite=5)
        values = [r.medicos_por_1k for r in rows if r.medicos_por_1k is not None]
        assert values == sorted(values, reverse=True)

    def test_indicador_invalido(self, db_session):
        rows = ranking_municipios_db(db_session, indicador="invalido", ordem="asc")
        assert len(rows) > 0  # fallback para medicos_por_1k


class TestCompararMunicipios:
    def test_comparar_dois(self, db_session):
        rows = comparar_municipios_db(db_session, municipios=["Adamantina", "Adolfo"])
        assert len(rows) == 2
        noms = {r.nm_mun for r in rows}
        assert "Adamantina" in noms
        assert "Adolfo" in noms

    def test_comparar_um(self, db_session):
        rows = comparar_municipios_db(db_session, municipios=["Adamantina"])
        assert len(rows) == 1

    def test_comparar_vazio(self, db_session):
        rows = comparar_municipios_db(db_session, municipios=[])
        assert rows == []


class TestBuscarSetoresMunicipio:
    def test_todos_setores(self, db_session):
        rows = buscar_setores_municipio_db(db_session, municipio="Adamantina")
        assert len(rows) > 0
        for r in rows:
            assert r.nm_mun == "Adamantina"

    def test_filtrar_categoria(self, db_session):
        rows = buscar_setores_municipio_db(
            db_session, municipio="Adamantina", categoria="1. Excelente (acesso muito alto)"
        )
        for r in rows:
            assert r.categoria_acesso == "1. Excelente (acesso muito alto)"

    def test_filtrar_por_nivel(self, db_session):
        rows = buscar_setores_municipio_db(db_session, municipio="Adamantina", categoria=5)
        for r in rows:
            assert r.categoria_acesso_nivel == 5

    def test_filtrar_categoria_abreviada(self, db_session):
        rows = buscar_setores_municipio_db(
            db_session, municipio="Adamantina", categoria="5. Muito baixo"
        )
        for r in rows:
            assert r.categoria_acesso_nivel == 5

    def test_filtrar_texto_livre(self, db_session):
        rows = buscar_setores_municipio_db(
            db_session, municipio="Adamantina", categoria="muito baixo"
        )
        for r in rows:
            assert "muito baixo" in r.categoria_acesso

    def test_municipio_inexistente(self, db_session):
        rows = buscar_setores_municipio_db(db_session, municipio="CidadeFantasma")
        assert rows == []

    def test_sem_filtro_de_localizacao_retorna_vazio(self, db_session):
        # Sem municipio/distrito a query varreria a tabela inteira — deve retornar [].
        assert buscar_setores_municipio_db(db_session) == []
        assert buscar_setores_municipio_db(db_session, categoria=1) == []
        assert resumo_setores_db(db_session) == {"total_setores": 0}

    def test_filtrar_por_distrito(self, db_session):
        distrito = db_session.execute(
            text(
                "SELECT nm_dist FROM setores WHERE nm_dist IS NOT NULL "
                "GROUP BY 1 ORDER BY count(*) DESC LIMIT 1"
            )
        ).scalar()
        rows = buscar_setores_municipio_db(db_session, distrito=distrito)
        assert len(rows) > 0
        assert {r.nm_dist for r in rows} == {distrito}

    def test_ordenado_do_pior_para_o_melhor_acesso(self, db_session):
        rows = buscar_setores_municipio_db(db_session, municipio="Adamantina")
        valores = [r.acessibilidade_e2sfca for r in rows if r.acessibilidade_e2sfca is not None]
        assert valores == sorted(valores)

    def test_limite(self, db_session):
        rows = buscar_setores_municipio_db(db_session, municipio="Adamantina", limite=5)
        assert len(rows) <= 5

    def test_resumo_agrega_todos_os_setores(self, db_session):
        resumo = resumo_setores_db(db_session, municipio="Adamantina")
        assert resumo["total_setores"] > 0
        assert resumo["setores_avaliados"] <= resumo["total_setores"]
        assert resumo["media_e2sfca"] is None or resumo["media_e2sfca"] >= 0
        assert sum(d["setores"] for d in resumo["distribuicao"]) == resumo["total_setores"]

    def test_resumo_com_distrito(self, db_session):
        distrito = db_session.execute(
            text(
                "SELECT nm_dist FROM setores WHERE nm_dist IS NOT NULL "
                "GROUP BY 1 ORDER BY count(*) DESC LIMIT 1"
            )
        ).scalar()
        resumo = resumo_setores_db(db_session, distrito=distrito)
        assert resumo["total_setores"] > 0
