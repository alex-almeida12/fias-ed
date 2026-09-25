"""Task 14: `montar_dataset` (app/export/service.py) — o adaptador que lê o
banco do Web e alimenta `fias_ed_engine.export.build_dataset`.

Nenhuma regra científica é testada aqui: as dez tabelas são decididas pelo
motor, que já tem suíte própria (fias-ed-shared/engine-py/tests/test_export.py).
O que importa nesta suíte é que o adaptador lê as fontes certas — a coleta QTI
VIGENTE (não qualquer coleta, `coleta_vigente`, o mesmo que a triangulação e o
MTSS usam), a evidência de fala do diarizador quando existe, e nunca captura
`ExportPrivacyError` — e nunca calcula nada por conta própria.
"""
import pytest

from app.export.service import montar_dataset
from app.models import RespostaQTI
from app.pipeline.estados import avancar
from fias_ed_engine.export import TABLES, ExportPrivacyError


def _gravar_respostas(db, coleta, n=12, valor=3):
    """`coleta_em` (conftest.py) só grava o resultado agregado (ResultadoQTI),
    não as respostas cruas — ela serve aos testes de triangulação, que só leem
    o agregado. `montar_dataset` lê `RespostaQTI` (as respostas cruas), então
    esta fixture completa o que falta. `n=12` >= `min_responses` (10, em
    qti_config.json), para que `displayable` saia True quando o motor
    recalcular a agregação."""
    for i in range(n):
        db.add(RespostaQTI(coleta_id=coleta.id, response_index=i,
                           respostas={str(q): valor for q in range(1, 25)}))
    db.commit()


@pytest.fixture
def ciclo_completo(db, ciclo, coleta_em, aula_classificada):
    """`aula_classificada` (conftest.py raiz) já está em FIAS_COMPLETED,
    ligada ao ciclo da fixture `ciclo` (fixtures cacheadas por teste — mesmo
    uso de `aula_report_ready` em test_relatorio_aula.py). Uma coleta QTI
    vigente, datada antes da aula, com respostas cruas gravadas, e `avancar`
    (app/pipeline/estados.py) pelo caminho real de produção — triangula e
    interpreta o MTSS — até REPORT_READY.

    Não força o status à mão: isso deixaria a aula sem Processamento/
    Triangulacao coerentes com o que o motor recalcula depois, e o dataset
    exportado precisa ser exatamente o que uma aula real de produção geraria."""
    coleta = coleta_em(ciclo, "2026-09-01")
    _gravar_respostas(db, coleta)
    avancar(db, aula_classificada)
    db.refresh(aula_classificada)
    assert aula_classificada.status == "REPORT_READY"
    return aula_classificada


def test_dez_tabelas_preenchidas_para_ciclo_completo(db, ciclo_completo):
    ds = montar_dataset(db, [ciclo_completo], include_text=False, exported_at="2026-09-24T12:00:00Z")
    assert set(ds) - {"manifest"} == set(TABLES)
    for tabela in TABLES:
        assert ds[tabela], f"tabela {tabela} veio vazia para um ciclo completo"


def test_qti_agreement_aparece_em_mtss_e_recommendations(db, ciclo_completo):
    """A lacuna que a Parte 1 fechou no motor: antes, `mtss`/`recommendations`
    nunca traziam `qti_agreement`. Aqui a prova é de ponta a ponta, partindo
    do banco do Web — não só do motor isolado (já provado em
    test_export.py::test_mtss_e_recommendations_trazem_qti_agreement)."""
    ds = montar_dataset(db, [ciclo_completo], include_text=False, exported_at="2026-09-24T12:00:00Z")
    assert ds["mtss"] and all("qti_agreement" in r for r in ds["mtss"])
    assert ds["recommendations"] and all("qti_agreement" in r for r in ds["recommendations"])

    # Com uma coleta vigente de verdade (respostas cruas gravadas), ao menos
    # uma regra tem de sair realmente qualificada — "unpaired" sozinho não
    # provaria que o QTI foi usado, só que uma regra sem par existe.
    valores = {r["qti_agreement"] for r in ds["mtss"]}
    assert valores & {"agree", "disagree"}, valores

    # E a recomendação repete o qti_agreement da regra que a originou.
    por_regra = {r["rule_id"]: r["qti_agreement"] for r in ds["mtss"]}
    assert all(r["qti_agreement"] == por_regra[r["rule_id"]] for r in ds["recommendations"])


def test_aula_sem_coleta_vigente_dataset_sai_sem_erro(db, aula_avulsa_classificada):
    """Uma aula fora de qualquer ciclo é caso legítimo, não falha (brief):
    `coleta_vigente` devolve None porque `ciclo_da_aula` já devolve None para
    ela. O dataset ainda sai — com `qti_responses` vazio, `qti_results` não
    exibível e `qti_agreement` "no_qti" nas regras que têm par (a regra sem
    par continua "unpaired", como sempre)."""
    ds = montar_dataset(db, [aula_avulsa_classificada], include_text=False,
                        exported_at="2026-09-24T12:00:00Z")
    assert ds["qti_responses"] == []
    assert ds["qti_results"][0]["displayable"] is False
    assert ds["mtss"]  # a aula dispara regras mesmo sem QTI (o MTSS nunca depende do QTI para disparar)
    valores = {r["qti_agreement"] for r in ds["mtss"]}
    assert valores <= {"no_qti", "unpaired"}, valores
    assert "no_qti" in valores


def test_include_text_false_nao_traz_texto_em_nenhum_segmento(db, ciclo_completo):
    ds = montar_dataset(db, [ciclo_completo], include_text=False, exported_at="2026-09-24T12:00:00Z")
    assert ds["segments"]
    assert all("text_pseudonymized" not in s for s in ds["segments"])


def test_include_text_true_sem_pseudonimo_levanta_e_nao_devolve_nada(db, ciclo_completo):
    """`classificar_para_triangulacao` (tests/helpers.py) nunca preenche
    `text_pseudonymized` — nenhum segmento desta aula tem versão pseudonimizada,
    então pedir texto tem que estourar `ExportPrivacyError`, não devolver texto
    vazio nem filtrar o segmento. `pytest.raises` já garante que nenhum valor
    de retorno existe quando a exceção sobe: a chamada nunca completa."""
    with pytest.raises(ExportPrivacyError):
        montar_dataset(db, [ciclo_completo], include_text=True, exported_at="2026-09-24T12:00:00Z")


def test_speech_ausente_registra_que_o_silencio_caiu_nos_segmentos(db, ciclo_completo):
    """`classificar_para_triangulacao` nunca grava `TrechoDeFala` (a aula não
    passa pela diarização de verdade), então `fala_detectada` devolve None e
    `montar_dataset` não deve inventar uma linha do tempo — o motor cai nos
    próprios segmentos e declara isso em `silence_source`."""
    ds = montar_dataset(db, [ciclo_completo], include_text=False, exported_at="2026-09-24T12:00:00Z")
    assert ds["lessons"][0]["silence_source"] == "asr_segments"


def test_usa_a_coleta_vigente_e_nao_uma_posterior_a_aula(db, ciclo, coleta_em, ciclo_completo):
    """Lacuna encontrada por mutação: trocar `coleta_vigente` por "a coleta mais
    recente do ciclo" não derrubava nenhum teste, porque o ciclo da fixture só
    tem uma coleta.

    Um dataset que usasse a coleta mais recente compararia a aula com uma
    percepção medida DEPOIS dela — uma opinião que ainda não existia quando a
    aula aconteceu. As respostas desta coleta posterior valem 5; as da vigente,
    3. É por isso que a asserção olha o valor: contar respostas não distingue
    as duas, já que ambas têm 12."""
    posterior = coleta_em(ciclo, "2026-12-01")
    _gravar_respostas(db, posterior, valor=5)

    ds = montar_dataset(db, [ciclo_completo], include_text=False, exported_at="2026-09-24T12:00:00Z")
    assert {linha["q1"] for linha in ds["qti_responses"]} == {3}
