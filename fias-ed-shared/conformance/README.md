# Casos de conformidade FIAS-ED

Cada arquivo em `cases/` contém uma lista de casos:

    {"id": "...", "function": "...", "description": "...", "input": {...}, "expected": ...}

Funções e entradas:

| function | input | expected |
|---|---|---|
| segments_to_intervals | {segments:[{start_ms,end_ms,category}], total_ms} | [int] |
| transition_matrix | {intervals:[int]} | [[int]] 10×10 |
| compute_indices | {intervals, n_segments, confidences} | {id: {value, reason, numerator_count, denominator_count}} |
| constrain_by_role | {logits:[10 floats], role} | {pred_raw, pred_role_constrained, confidence_raw, confidence, uncertain} |
| score_response | {answers:{"1":int..."24":int}} | {octants, agency, communion} |
| aggregate_qti | {responses:[answers]} | {response_count, displayable, octants, agency, communion} |
| evaluate_mtss | {intervals} | [rule_id] (ordem de disparo) |
| triangulate | {intervals, qti_responses:[answers]} | [{pair_id, fias_value, qti_available, qti_values}] |

Regras usadas: sempre os arquivos de `rules/` da mesma versão (`rules_version`).
Floats: tolerância absoluta 1e-9. Chaves de `answers` são strings ("1".."24").
Um motor está de acordo com este conjunto de casos apenas quando passa em
100% deles.
Os casos QTI foram conferidos contra os testes de `avalie-seu-professor/tests/unit/qtiCalculations.test.ts`.

## Desempate de categoria modal (`evaluate_mtss`)

`modal_teacher_category` (`fias_ed_engine.mtss.build_facts`) é a categoria
docente (1–7) com maior contagem de intervalos na aula; em caso de empate,
vence a categoria de menor número (`mtss.py`, comparação por
`(contagem, -categoria)`). O caso `mtss-lesson-tie-5-6` (`[5, 6, 8, 10]`)
exercita esse desempate: cat. 5 e cat. 6 empatam com 1 intervalo cada, o
desempate resolve para a categoria 5, e por isso dispara
`MTSS_EXPOSITIVE_PREDOMINANCE` (não `MTSS_INSTRUCTIONS_PREDOMINANCE`) — se o
desempate favorecesse a categoria maior, o resultado seria o oposto. O caso
`mtss-lesson-instructions-predominance` (`[6, 6, 6, 8, 10]`) garante que
`MTSS_INSTRUCTIONS_PREDOMINANCE` (categoria modal = 6, sem empate) também
tem um caso de conformidade que a exercita.
