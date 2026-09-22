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
Um motor só é conforme se passar em 100% dos casos.
Os casos QTI foram conferidos contra os testes de `avalie-seu-professor/tests/unit/qtiCalculations.test.ts`.
