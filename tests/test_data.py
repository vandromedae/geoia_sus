from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import select, text

from src.models import Cnes
from src.services.data import (
    ColunasFaltandoError,
    atualizar_centroides,
    atualizar_codigos_ibge,
    importar_cnes,
    importar_municipios,
    importar_setores,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestValidacaoDeColunas:
    """Coluna obrigatória ausente tinha virado `KeyError` no meio do import."""

    def test_municipios_sem_cod_mun_ibge(self, tmp_path, db_session):
        caminho = tmp_path / "municipios.parquet"
        pd.DataFrame({"nm_mun": ["Xpto"]}).to_parquet(caminho)

        with pytest.raises(ColunasFaltandoError) as erro:
            importar_municipios(caminho, db_session)

        assert "cod_mun_ibge" in str(erro.value)

    def test_mensagem_lista_colunas_presentes(self, tmp_path, db_session):
        caminho = tmp_path / "municipios.parquet"
        pd.DataFrame({"nm_mun": ["Xpto"]}).to_parquet(caminho)

        with pytest.raises(ColunasFaltandoError) as erro:
            importar_municipios(caminho, db_session)

        assert "Colunas presentes" in str(erro.value)

    def test_setores_sem_cd_setor(self, tmp_path, db_session):
        caminho = tmp_path / "setores.parquet"
        pd.DataFrame({"NM_MUN": ["Xpto"]}).to_parquet(caminho)

        with pytest.raises(ColunasFaltandoError) as erro:
            importar_setores(caminho, db_session)

        assert "CD_SETOR" in str(erro.value)


class TestImportarMunicipios:
    def test_importa_fixture(self, db_session):
        assert importar_municipios(FIXTURES / "municipios.parquet", db_session) == 10

    def test_reimportar_nao_duplica(self, db_session):
        from src.models import Municipio

        importar_municipios(FIXTURES / "municipios.parquet", db_session)
        importar_municipios(FIXTURES / "municipios.parquet", db_session)
        codigos = db_session.scalars(
            select(Municipio.cod_mun_ibge).where(Municipio.nm_mun == "Adamantina")
        ).all()
        assert codigos == ["3500105"]


class TestImportarCNES:
    def test_importa_fixture(self, db_session):
        assert importar_cnes(FIXTURES / "cnes.parquet", db_session) == 20

    def test_aceita_nome_fantasia_corrigido(self, tmp_path, db_session):
        """A origem publica `nome_fantaia` (typo); se corrigirem, não pode quebrar."""
        df = pd.read_parquet(FIXTURES / "cnes.parquet").rename(
            columns={"nome_fantaia": "nome_fantasia"}
        )
        caminho = tmp_path / "cnes.parquet"
        df.to_parquet(caminho)

        assert importar_cnes(caminho, db_session) == len(df)
        nomes = db_session.scalars(select(Cnes.nome_fantasia)).all()
        assert any(nomes)

    def test_grafia_antiga_continua_funcionando(self, db_session):
        df = pd.read_parquet(FIXTURES / "cnes.parquet")
        assert importar_cnes(FIXTURES / "cnes.parquet", db_session) == len(df)
        nomes = [n for n in db_session.scalars(select(Cnes.nome_fantasia)).all() if n]
        assert nomes, "nome_fantasia não foi preenchido com o typo da origem"


class TestAtualizarCentroides:
    def test_preenche_centroides(self, db_session):
        from src.models import Municipio

        linhas = atualizar_centroides(db_session)
        assert linhas > 0
        preenchidos = db_session.scalar(
            select(Municipio.centroide).where(Municipio.centroide.isnot(None)).limit(1)
        )
        assert preenchidos is not None


class TestAtualizarCodigosIBGE:
    """O parquet de municípios traz 6 dígitos; o check digit é dos setores."""

    def test_completa_check_digit_das_duas_tabelas(self, db_session):
        from src.models import Municipio, Setor

        db_session.add(Municipio(cod_mun_ibge="999990", nm_mun="Municipio Teste"))
        db_session.add(
            Setor(
                cd_setor="999990001000001",
                nm_mun="Municipio Teste",
                cod_mun_ibge="999990",
                cd_mun="9999901",
            )
        )
        db_session.flush()

        try:
            corrigidos = atualizar_codigos_ibge(db_session)
            db_session.expire_all()

            mun = db_session.scalar(
                select(Municipio.cod_mun_ibge).where(Municipio.nm_mun == "Municipio Teste")
            )
            setor = db_session.scalar(
                select(Setor.cod_mun_ibge).where(Setor.cd_setor == "999990001000001")
            )
            assert corrigidos == (1, 1)
            assert mun == "9999901"
            assert setor == "9999901"
        finally:
            db_session.execute(text("DELETE FROM setores WHERE cd_setor = '999990001000001'"))
            db_session.execute(
                text("DELETE FROM municipios WHERE cod_mun_ibge IN ('999990', '9999901')")
            )
            db_session.commit()

    def test_setores_sem_cd_mun_nao_sao_tocados(self, db_session):
        """Sem `cd_mun` não há fonte do 7º dígito — deixar como está."""
        from src.models import Setor

        db_session.add(Setor(cd_setor="999990002000001", cod_mun_ibge="999991", cd_mun=None))
        db_session.flush()

        try:
            atualizar_codigos_ibge(db_session)
            db_session.expire_all()
            assert (
                db_session.scalar(
                    select(Setor.cod_mun_ibge).where(Setor.cd_setor == "999990002000001")
                )
                == "999991"
            )
        finally:
            db_session.execute(text("DELETE FROM setores WHERE cd_setor = '999990002000001'"))
            db_session.commit()
