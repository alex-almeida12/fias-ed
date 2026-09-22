from sqlalchemy import inspect

from app.models import (ClassificacaoFIAS, Falante, IndicadorFIAS, ModeloIA, Segmento,
                        Transcricao)


def _colunas(modelo):
    return {c.name: c for c in inspect(modelo).columns}


def test_falante_tem_os_tres_papeis_do_shared():
    col = _colunas(Falante)["role"]
    assert set(col.type.enums) == {"PROFESSOR", "ALUNO", "UNASSIGNED"}


def test_falante_liga_a_transcricao_e_nao_a_aula():
    colunas = _colunas(Falante)
    assert "transcricao_id" in colunas
    assert "aula_id" not in colunas


def test_segmento_usa_os_nomes_de_tempo_do_shared():
    colunas = _colunas(Segmento)
    assert {"start_ms", "end_ms"} <= set(colunas)
    assert "inicio_ms" not in colunas


def test_segmento_exige_falante_e_aceita_pseudonimizado_nulo():
    colunas = _colunas(Segmento)
    # O schema do shared resolve "ainda não se sabe quem falou" com
    # role=UNASSIGNED, não com FK nula.
    assert colunas["falante_id"].nullable is False
    assert colunas["text_pseudonymized"].nullable is True
    assert colunas["texto_revisado"].nullable is True
    assert colunas["revisado"].nullable is False


def test_classificacao_guarda_a_predicao_crua_e_a_restrita_por_papel():
    colunas = _colunas(ClassificacaoFIAS)
    assert {"pred_raw", "pred_role_constrained", "confidence_raw", "confidence",
            "uncertain"} <= set(colunas)
    # Liga ao segmento, não à aula.
    assert "segmento_id" in colunas and "aula_id" not in colunas


def test_indicador_guarda_a_evidencia_estruturada():
    colunas = _colunas(IndicadorFIAS)
    assert {"index_id", "value", "reason", "numerator_count", "denominator_count",
            "n_intervals", "validation_status"} <= set(colunas)
    assert colunas["value"].nullable is True  # sem dado suficiente


def test_modelo_ia_guarda_licenca_e_procedencia():
    colunas = _colunas(ModeloIA)
    assert {"model_id", "name", "model_version", "task", "format", "sha256",
            "size_bytes", "source", "license", "parameters"} <= set(colunas)


def test_transcricao_fixa_o_idioma_do_produto():
    col = _colunas(Transcricao)["language"]
    assert set(col.type.enums) == {"pt-BR"}
