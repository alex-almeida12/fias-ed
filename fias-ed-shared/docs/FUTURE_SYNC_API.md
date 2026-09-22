# API de sincronização futura (proposta, não implementada)

Esboço de endpoints para a sincronização descrita em `FUTURE_SYNC.md`. **Tudo
neste documento é proposta de arquitetura** — nenhum endpoint existe hoje;
não há servidor, autenticação nem implementação. O formato de dados segue os
`schemas/entities/*.schema.json` já existentes, para que o cliente Android e
um futuro backend Web troquem exatamente as mesmas entidades usadas
localmente.

## `POST /sync/push`

Envia um lote de entidades alteradas localmente.

**Entrada proposta:**

```json
{
  "device_id": "string",
  "entities": [
    {
      "entity_type": "aula",
      "id": "uuid",
      "expected_version": 3,
      "data": { "...": "campos da entidade, formato do schema correspondente" }
    }
  ]
}
```

- `expected_version` é a `version` que o dispositivo acredita ser a mais
  recente no servidor para aquele `id` (normalmente `version - 1` do
  registro sendo enviado, já incrementado localmente). O servidor recusa a
  escrita com conflito se a `version` atual dele for diferente.

**Saída proposta:**

```json
{
  "results": [
    { "id": "uuid", "status": "SYNCED", "version": 4 },
    { "id": "uuid", "status": "CONFLICT", "server_version": 5, "server_data": { "...": "..." } }
  ]
}
```

## `GET /sync/pull?since=<timestamp|version_cursor>`

Retorna entidades alteradas no servidor desde o último ponto sincronizado
pelo dispositivo, no mesmo formato de entidade dos schemas locais, para que
o dispositivo aplique localmente (com a mesma lógica de detecção de conflito
por `version`).

## Formato

Todo corpo de entidade trafegado por `push`/`pull` deve validar contra o
schema correspondente em `schemas/entities/` — não há um formato de rede
separado do formato local. Isso evita ter dois contratos (um local, outro de
rede) para manter sincronizados manualmente.

## Autenticação

**A definir.** Nenhuma fonte deste subprojeto especifica um mecanismo de
autenticação para um futuro backend Web; qualquer decisão (token, sessão,
chave por dispositivo) fica para quando a sincronização for de fato
implementada, fora do escopo deste subprojeto.

## Áudio

Consistente com `FUTURE_SYNC.md`: a entidade `Audio` não deve ser incluída
nestes endpoints, nem no `push` nem no `pull`, sem uma decisão explícita e
separada sobre autorização de envio de áudio (CEP l.85).

## Status

Este documento é um esboço de proposta técnica para orientar o desenho de
um backend futuro, não uma especificação pronta para implementação. Nenhum
endpoint, biblioteca cliente ou schema de rede foi construído neste
subprojeto.
