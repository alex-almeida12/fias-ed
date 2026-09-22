# Sincronização futura (não implementada nesta fase)

O modelo de dados do FIAS-ED já reserva os campos necessários para
sincronizar dados entre o app Android (offline-first) e um futuro backend
Web, mas **a sincronização em si não está implementada** neste subprojeto
(spec §9: "Sincronização não implementada; apenas preparada"). Este
documento descreve a estratégia proposta para quando ela for construída.

## Estados

Todo registro tem `sync_status` (`schemas/entities/_base.schema.json`), com
quatro estados:

```
LOCAL_ONLY ──(tentativa de envio)──> PENDING_SYNC ──(aceito pelo servidor)──> SYNCED
                                            │
                                            └──(conflito de versão)──> CONFLICT
```

- `LOCAL_ONLY`: criado ou alterado localmente, ainda não houve tentativa de
  sincronizar.
- `PENDING_SYNC`: enviado para sincronização, aguardando confirmação do
  servidor.
- `SYNCED`: confirmado pelo servidor, sem conflito.
- `CONFLICT`: o servidor detectou uma versão diferente da esperada para o
  mesmo `id`; requer resolução manual (ver abaixo).

## `version`

Cada entidade tem um campo inteiro `version`, começando em 1 e incrementado a
cada alteração local. É a base da detecção de conflito: ao enviar uma
alteração, o dispositivo informa a `version` que ele acredita ser a atual no
servidor; se o servidor já tiver uma `version` maior para aquele `id`, a
sincronização daquele registro entra em `CONFLICT` em vez de sobrescrever
silenciosamente.

## `device_id`

Cada entidade registra o `device_id` do dispositivo que fez a última
alteração — necessário tanto para diagnosticar conflitos (de onde veio cada
versão) quanto para a estratégia de resolução abaixo.

## Estratégia proposta

- **Last-writer-wins por entidade**, usando `updated_at` como critério de
  desempate, **combinado com detecção de conflito por `version`**: uma
  alteração só é aceita automaticamente se a `version` enviada bater com a
  `version` mais recente do servidor. Quando não bate, o registro fica
  `CONFLICT` em vez de ser resolvido automaticamente.
- **Resolução manual para `CONFLICT`**: cabe a uma tela futura (fora deste
  subprojeto) apresentar as duas versões divergentes ao usuário (ou ao
  pesquisador, para entidades administrativas) para escolha explícita. Esta
  estratégia é uma proposta de arquitetura, ainda não implementada nem
  testada.

## Áudio nunca sincroniza sem autorização explícita

Alinhado a CEP l.85 ("o áudio original permanece restrito ao dispositivo do
professor"): a entidade `Audio` não deve ser incluída em nenhuma
sincronização automática. Qualquer envio de áudio para fora do dispositivo
de origem exige autorização explícita e separada do professor — este
documento não define esse fluxo, apenas registra a restrição.

## Escopo desta fase

Nada neste documento está implementado em código. `sync_status`, `version` e
`device_id` existem nos schemas de entidade e são preenchidos (com
`LOCAL_ONLY` por padrão) pelo motor de referência, mas não há endpoint, fila
de sincronização, nem lógica de merge — ver `FUTURE_SYNC_API.md` para o
esboço de API, também não implementado.
