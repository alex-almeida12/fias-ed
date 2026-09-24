# Prompt mestre — FIAS-ED

Texto original fornecido pelo pesquisador (Alex Almeida do Amaral) em
2026-09-21, salvo aqui como fonte versionada dos requisitos dos três
subprojetos. As referências "prompt §N" nos specs e planos apontam para as
seções numeradas abaixo. Não editar o conteúdo; correções de requisitos vão
para os specs.

```text
# ============================================================
# PROMPT MESTRE — FIAS-ED
# ============================================================

Quero que você desenvolva o sistema completo FIAS-ED.

O FIAS-ED é uma plataforma para professores enviarem o áudio de uma aula,
compreenderem os padrões de interação que ocorreram em sala,
integrarem essas informações à percepção dos estudantes,
refletirem sobre sua prática e receberem sugestões pedagógicas
para suas próximas aulas.

A mensagem principal do produto será:

"Grave sua aula. Melhore sua prática docente."

IMPORTANTE:

Na interface do professor NÃO apresentar o FIAS-ED como:

- sistema de avaliação docente;
- sistema de fiscalização;
- ferramenta para julgar professores;
- sistema de classificação de desempenho;
- ranking de professores;
- ferramenta punitiva.

A interface deve utilizar linguagem como:

- "Adicionar aula"
- "Enviar áudio da aula"
- "Analisar minha aula"
- "Entender minha aula"
- "Ver padrões de interação"
- "Conhecer a percepção dos estudantes"
- "Pontos para reflexão"
- "Sugestões para próximas aulas"
- "Melhorar minha prática"

Evitar:

- "Iniciar avaliação"
- "Avaliar professor"
- "Professor inadequado"
- "Desempenho ruim"
- "Nota do professor"

O professor deve perceber o FIAS-ED como uma ferramenta de:

- reflexão;
- feedback formativo;
- desenvolvimento profissional;
- apoio pedagógico;
- melhoria contínua da prática docente.

# ============================================================
# 1. DIRETÓRIOS OBRIGATÓRIOS
# ============================================================

Toda a pesquisa, artigos, experimentos, documentos, referências
e materiais científicos estão localizados em:

C:\Users\Alex Almeida\Documents\mestrado\artigos selecionados

Essa pasta deve ser tratada como a principal base científica do projeto.

Os experimentos estão especialmente em:

C:\Users\Alex Almeida\Documents\mestrado\artigos selecionados\experimentos

NÃO modificar os experimentos originais.

Usar essa pasta como fonte de:

- modelos;
- checkpoints;
- scripts;
- notebooks;
- datasets;
- métricas;
- código;
- resultados;
- configurações.

Todos os sistemas deverão ser criados dentro de:

C:\Users\Alex Almeida\Documents\mestrado\sistemas

Estrutura esperada:

C:\Users\Alex Almeida\Documents\mestrado\sistemas
│
├── fias-ed-web
│
├── fias-ed-android
│
└── fias-ed-shared
    ├── rules
    ├── schemas
    ├── docs
    └── scientific-config

Antes de criar qualquer coisa:

1. verificar se os diretórios já existem;
2. analisar conteúdo existente;
3. não apagar arquivos automaticamente;
4. não sobrescrever trabalho existente sem análise;
5. inicializar Git;
6. manter os experimentos originais intactos.

# ============================================================
# 2. SKILLS OBRIGATÓRIAS
# ============================================================

Antes do desenvolvimento:

1. executar /superpowers
2. executar /impeccable init
3. usar /Impeccable durante o desenvolvimento

Usar /superpowers para:

- planejamento;
- arquitetura;
- decomposição de problemas;
- depuração;
- revisão estrutural;
- decisões complexas.

Usar /Impeccable para:

- direção visual;
- hierarquia;
- espaçamento;
- tipografia;
- composição;
- responsividade;
- consistência;
- refinamento;
- qualidade final.

Não utilizar /Impeccable apenas uma vez.

Aplicar revisão em:

- Home;
- Dashboard;
- Nova Aula;
- Upload;
- Processamento;
- Transcrição;
- FIAS;
- QTI;
- MTSS;
- Recomendações;
- Relatório;
- Web responsiva;
- Android.

Fluxo:

implementar
→ revisar com /Impeccable
→ corrigir
→ testar
→ revisar novamente

# ============================================================
# 3. PESQUISA DE INTERFACES
# ============================================================

Antes de implementar o frontend definitivo, pesquisar referências reais.

Pesquisar em:

- Mobbin
- Refero
- Figma Community
- Behance
- Dribbble
- SaaSFrame
- Land-book
- Awwwards

Priorizar interfaces de:

- educação;
- saúde;
- produtividade;
- software científico;
- ferramentas acadêmicas;
- sistemas institucionais;
- dashboards de dados;
- sistemas B2B maduros.

Pesquisar pelo menos 10 referências relevantes.

Não copiar interfaces integralmente.

Criar:

docs/UI_REFERENCES.md

Para cada referência registrar:

- nome;
- URL;
- tela analisada;
- elemento relevante;
- como pode inspirar o FIAS-ED;
- o que não deve ser copiado.

# ============================================================
# 4. IDENTIDADE VISUAL
# ============================================================

A identidade deve ser:

- profissional;
- acadêmica;
- contemporânea;
- humana;
- simples;
- sóbria;
- confiável;
- institucional;
- baseada em dados.

Evitar aparência de:

- chatbot;
- IA generativa;
- SaaS genérico;
- template automático;
- dashboard futurista.

# ============================================================
# 5. PALETA OFICIAL
# ============================================================

Utilizar exatamente esta paleta como base:

Navy
#2F4156

Teal
#567C8D

Sky Blue
#C8D9E6

Beige
#F5EFEB

White
#FFFFFF

Essa será a identidade principal do Web e Android.

Uso:

Navy #2F4156
- títulos;
- texto principal;
- navegação;
- botões principais;
- cabeçalhos;
- ícones importantes.

Teal #567C8D
- ações secundárias;
- seleção;
- destaques;
- links;
- gráficos.

Sky Blue #C8D9E6
- superfícies informativas;
- seleção;
- gráficos;
- fundos suaves.

Beige #F5EFEB
- fundo secundário;
- áreas pedagógicas;
- recomendações;
- pontos para reflexão.

White #FFFFFF
- fundo principal;
- formulários;
- relatórios;
- áreas de conteúdo.

A interface deve ser predominantemente clara.

Sugestão aproximada:

White + Beige: 65–75%
Navy: 10–15%
Teal: 8–12%
Sky Blue: 5–10%

Não usar gradientes decorativos.

Não usar glow.

Não criar cores aleatórias fora da identidade, exceto cores semânticas
de erro, sucesso, atenção e informação.

# ============================================================
# 6. TIPOGRAFIA OFICIAL
# ============================================================

Utilizar como principais famílias tipográficas:

Ubuntu
e
Rokkitt

A tipografia deve contribuir para uma identidade acadêmica,
contemporânea e humana.

============================================================
UBUNTU
============================================================

Utilizar Ubuntu como fonte principal de interface.

Aplicar em:

- menus;
- sidebar;
- botões;
- inputs;
- labels;
- tabelas;
- filtros;
- números;
- indicadores;
- navegação;
- textos funcionais;
- mensagens de sistema;
- corpo de texto curto.

Pesos preferidos:

Ubuntu Regular — 400
Ubuntu Medium — 500
Ubuntu Bold — 700

Evitar excesso de Bold.

============================================================
ROKKITT
============================================================

Utilizar Rokkitt principalmente como fonte editorial.

Aplicar em:

- títulos principais;
- grandes chamadas;
- cabeçalhos de relatórios;
- frases pedagógicas;
- destaques editoriais;
- sessões de reflexão;
- títulos especiais.

Exemplo:

FIAS-ED

"Grave sua aula.
Melhore sua prática docente."

pode utilizar Rokkitt.

Usar Ubuntu no restante da interface.

============================================================
HIERARQUIA SUGERIDA
============================================================

Display grande:
Rokkitt

H1:
Rokkitt SemiBold ou Bold

H2:
Rokkitt SemiBold

H3:
Ubuntu Bold ou Rokkitt Medium conforme contexto

Body:
Ubuntu Regular

Label:
Ubuntu Medium

Button:
Ubuntu Medium

Table:
Ubuntu Regular / Medium

Caption:
Ubuntu Regular

============================================================
WEB
============================================================

Centralizar fontes no design system.

Não definir fontes individualmente em cada componente.

Criar tokens:

--font-interface: 'Ubuntu', sans-serif;
--font-editorial: 'Rokkitt', serif;

Nunca depender obrigatoriamente de Google Fonts em runtime.

O sistema deve poder funcionar localmente/offline.

Preferir fontes empacotadas localmente ou alternativas instaladas
de forma compatível com o projeto.

============================================================
ANDROID
============================================================

Definir Typography no Jetpack Compose.

Criar:

FIASTypography

Usar:

Ubuntu para interface.

Rokkitt para títulos/editorial.

Não usar Roboto como fonte predominante apenas por ser padrão Android.

============================================================
LEGIBILIDADE
============================================================

Não utilizar Rokkitt em:

- tabelas extensas;
- campos de formulário;
- textos técnicos longos;
- números pequenos;
- labels muito pequenos.

Rokkitt deve criar personalidade.

Ubuntu deve garantir legibilidade.

# ============================================================
# 7. REMOVER "CARA DE IA"
# ============================================================

Evitar:

- gradientes;
- glassmorphism;
- glow;
- blobs;
- cards excessivos;
- border-radius exagerado;
- ícones de estrela;
- cérebro de IA;
- robôs;
- sparkles;
- ilustrações genéricas;
- gráficos desnecessários.

Não usar textos como:

"AI powered"
"Insights inteligentes"
"Assistente inteligente"
"Transforme sua jornada"
"Potencialize sua experiência"
"Desbloqueie seu potencial"

A tecnologia deve ficar em segundo plano.

# ============================================================
# 8. DESIGN SYSTEM
# ============================================================

Criar:

docs/DESIGN_SYSTEM.md

Definir:

- cores;
- tipografia;
- spacing;
- grid;
- radius;
- borders;
- shadows;
- botões;
- inputs;
- tabelas;
- cards;
- dialogs;
- tabs;
- badges;
- gráficos;
- loading;
- empty states;
- error states;
- breakpoints.

Web e Android devem compartilhar a mesma identidade.

# ============================================================
# 9. DOIS PRODUTOS
# ============================================================

Criar:

1. FIAS-ED WEB
2. FIAS-ED ANDROID

Ambos compartilham:

- modelo conceitual;
- FIAS;
- QTI;
- MTSS;
- regras;
- schemas;
- UUIDs;
- identidade visual;
- versionamento científico.

# ============================================================
# 10. WEB
# ============================================================

Diretório:

C:\Users\Alex Almeida\Documents\mestrado\sistemas\fias-ed-web

Stack:

Frontend:
React
TypeScript
Vite

Backend:
Python 3.11+
FastAPI
Pydantic
SQLAlchemy
Alembic

Banco:
PostgreSQL 16

Infraestrutura:
Docker
Docker Compose

Arquitetura:

Browser
↓
React
↓
FastAPI
↓
PostgreSQL
↓
Pipeline local

# ============================================================
# 11. ANDROID
# ============================================================

Diretório:

C:\Users\Alex Almeida\Documents\mestrado\sistemas\fias-ed-android

Usar preferencialmente:

Kotlin
Jetpack Compose
Room
SQLite
Coroutines
Flow
WorkManager
Navigation Compose
Storage Access Framework

O aplicativo deve funcionar:

SEM INTERNET
SEM SERVIDOR
SEM COMPUTADOR
SEM API EXTERNA

Não utilizar WebView como interface principal.

# ============================================================
# 12. ENTRADA PRINCIPAL
# ============================================================

O fluxo principal do sistema é:

IMPORTAR / ENVIAR O ARQUIVO DE ÁUDIO DE UMA AULA.

O professor pode gravar usando qualquer equipamento.

Depois envia o áudio para o FIAS-ED.

Não obrigar o usuário a gravar dentro do app.

A gravação interna pode existir futuramente como:

OPTIONAL_FEATURE

Suportar inicialmente:

MP3
WAV
M4A
AAC
FLAC

# ============================================================
# 13. FLUXO DO PROFESSOR
# ============================================================

INÍCIO
↓
NOVA AULA
↓
TURMA
↓
DISCIPLINA
↓
ENVIAR ÁUDIO
↓
VALIDAÇÃO
↓
PROCESSAMENTO
↓
TRANSCRIÇÃO
↓
IDENTIFICAÇÃO DAS FALAS
↓
REVISÃO
↓
FIAS
↓
QTI
↓
TRIANGULAÇÃO
↓
MTSS
↓
SUGESTÕES
↓
RELATÓRIO
↓
MELHORIA DA PRÁTICA

# ============================================================
# 14. HOME
# ============================================================

FIAS-ED

Título:

"Grave sua aula.
Melhore sua prática docente."

Usar Rokkitt no título principal.

Descrição:

"Envie o áudio de uma aula e conheça melhor os padrões de interação
que acontecem em sala."

Usar Ubuntu no texto.

Botão:

[ Adicionar aula ]

# ============================================================
# 15. NOVA AULA
# ============================================================

Campos:

Turma
Disciplina
Data
Observação opcional

Área:

Adicionar áudio da aula

Texto:

"Selecione o arquivo de áudio gravado durante sua aula."

Botão:

[ Selecionar áudio ]

Depois:

[ Processar aula ]

# ============================================================
# 16. VALIDAÇÃO DO ÁUDIO
# ============================================================

Validar:

- formato;
- MIME;
- extensão;
- tamanho;
- duração;
- canais;
- sample rate.

Não confiar apenas na extensão.

Registrar:

audio_id
original_filename
internal_filename
mime_type
size
duration
sha256
created_at

Usar UUID para nome interno.

# ============================================================
# 17. PRESERVAR ORIGINAL
# ============================================================

Nunca modificar o áudio original.

Pipeline:

ORIGINAL
↓
CÓPIA DE TRABALHO
↓
NORMALIZAÇÃO
↓
PROCESSAMENTO

Registrar SHA-256.

# ============================================================
# 18. ÁUDIOS LONGOS
# ============================================================

Testar:

10 min
30 min
50 min
60 min
90 min

Se necessário, processar em chunks.

Preservar timestamps globais.

# ============================================================
# 19. BASE CIENTÍFICA
# ============================================================

Antes de implementar regras científicas pesquisar:

C:\Users\Alex Almeida\Documents\mestrado\artigos selecionados

Pesquisar:

FIAS
QTI
MTSS
AIED Unplugged
ASR
diarização
classificação
métricas
thresholds

Não inventar informação.

Quando faltar fundamentação:

PENDING_SCIENTIFIC_VALIDATION

Criar:

RESEARCH_INVENTORY.md

# ============================================================
# 20. EXPERIMENTOS
# ============================================================

Analisar:

C:\Users\Alex Almeida\Documents\mestrado\artigos selecionados\experimentos

Localizar:

*.py
*.ipynb
*.json
*.csv
*.safetensors
*.bin
*.pt
*.pth
*.pkl
*.joblib

Identificar:

- BERTimbau;
- tokenizer;
- checkpoint;
- classes;
- datasets;
- preprocessing;
- max_length;
- métricas;
- F1;
- acurácia;
- seed.

Criar:

ANALISE_MODELOS_EXISTENTES.md

Não treinar outro modelo antes de analisar o existente.

# ============================================================
# 21. ASR
# ============================================================

WEB:

avaliar faster-whisper.

ANDROID:

avaliar whisper.cpp.

Comparar:

tiny
base
small

Métricas:

WER
tempo
RAM
tamanho
CPU
bateria
temperatura

# ============================================================
# 22. DIARIZAÇÃO
# ============================================================

WEB:

avaliar pyannote.audio local.

ANDROID:

não assumir que pyannote será viável.

Pesquisar:

- modelos leves;
- ONNX;
- VAD;
- clustering;
- segmentação.

Criar:

ANDROID_DIARIZATION_FEASIBILITY.md

Se não for viável:

documentar alternativa.

# ============================================================
# 23. PROFESSOR
# ============================================================

Nunca assumir:

SPEAKER_00 = PROFESSOR

Mostrar amostras e perguntar:

"Qual destas vozes é você?"

Mapear:

SPEAKER_X → PROFESSOR

Outras falas:

ALUNO

Não fazer biometria de voz.

# ============================================================
# 24. TRANSCRIÇÃO
# ============================================================

Mostrar:

timestamp
falante
texto

Permitir correção.

Guardar:

texto_original_asr
texto_revisado
revisado

Registrar:

ASR_ORIGINAL

ou

TRANSCRICAO_REVISADA

como fonte usada pelo classificador.

# ============================================================
# 25. BERTIMBAU
# ============================================================

Usar BERTimbau existente.

Não chamar de LLM generativo.

Criar:

FIASClassifier

Entrada:

texto

Saída:

fias_category
label
confidence
model_version

Não inventar classes.

# ============================================================
# 26. ANDROID + BERTIMBAU
# ============================================================

Avaliar:

ONNX

Executar com:

ONNX Runtime Mobile

Comparar:

FP32
FP16
INT8

Registrar:

F1
latência
RAM
tamanho

# ============================================================
# 27. FIAS
# ============================================================

Calcular apenas métricas fundamentadas.

Exemplos:

- categorias;
- fala docente;
- fala discente;
- perguntas;
- respostas;
- iniciativa;
- influência direta;
- influência indireta;
- participação;
- silêncio/confusão.

Não inventar fórmulas.

# ============================================================
# 28. QTI
# ============================================================

Permitir:

- entrada manual;
- formulário;
- importação;
- fotografia.

QTI deve ser determinístico.

Não usar LLM para pontuação.

# ============================================================
# 29. OCR
# ============================================================

Fluxo:

IMAGEM
↓
OCR LOCAL
↓
DADOS
↓
CONFIRMAÇÃO
↓
QTI

Considerar:

Tesseract
ou equivalente offline.

# ============================================================
# 30. TRIANGULAÇÃO
# ============================================================

Entrada:

FIAS
+
QTI

Saída:

achados pedagógicos.

Toda interpretação deve possuir evidências.

# ============================================================
# 31. MTSS TIER 1
# ============================================================

MTSS é obrigatório.

Fluxo:

FIAS + QTI
↓
TRIANGULAÇÃO
↓
MTSS TIER 1
↓
INTERPRETAÇÃO
↓
RECOMENDAÇÕES

Não produzir diagnóstico clínico.

Não classificar professor como bom ou ruim.

# ============================================================
# 32. REGRAS MTSS
# ============================================================

Criar:

fias-ed-shared/rules/mtss_rules.json

Cada regra:

rule_id
conditions
evidence
interpretation
recommendation
source_reference
rules_version
validation_status

Se faltarem evidências:

threshold_pending_validation

# ============================================================
# 33. RECOMENDAÇÕES
# ============================================================

Usar inicialmente motor de regras.

Não usar LLM externo.

Preferir:

"Considere..."
"Você pode experimentar..."
"Uma possibilidade é..."
"Este padrão pode indicar..."

Não usar:

"Você fez errado"
"Seu desempenho foi ruim"

# ============================================================
# 34. RELATÓRIO
# ============================================================

Nome:

Relatório da Aula

Estrutura:

IDENTIFICAÇÃO

RESUMO

PADRÕES DE INTERAÇÃO

PERCEPÇÃO DOS ESTUDANTES

TRIANGULAÇÃO

INTERPRETAÇÃO MTSS

PONTOS PARA REFLEXÃO

SUGESTÕES PARA PRÓXIMAS AULAS

EVIDÊNCIAS

INFORMAÇÕES TÉCNICAS

Usar Rokkitt nos grandes títulos do relatório.

Usar Ubuntu no corpo e dados.

# ============================================================
# 35. STATUS
# ============================================================

DRAFT
AUDIO_IMPORTED
AUDIO_VALIDATED
PREPROCESSING
TRANSCRIBING
TRANSCRIBED
DIARIZING
READY_FOR_SPEAKER_REVIEW
READY_FOR_TRANSCRIPT_REVIEW
READY_FOR_FIAS
FIAS_COMPLETED
WAITING_QTI
QTI_COMPLETED
TRIANGULATED
MTSS_INTERPRETED
REPORT_READY
ERROR

# ============================================================
# 36. MENSAGENS PARA O USUÁRIO
# ============================================================

Mostrar:

Preparando sua aula...
Transformando áudio em texto...
Identificando os momentos de fala...
Organizando as interações...
Analisando padrões da aula...
Integrando as respostas dos estudantes...
Preparando a interpretação pedagógica...
Gerando sugestões...
Preparando seu relatório...

Não exibir termos técnicos desnecessários.

# ============================================================
# 37. MODELO DE DADOS
# ============================================================

WEB:

PostgreSQL

ANDROID:

Room / SQLite

Mesmo modelo lógico.

Entidades:

Professor
Escola
Turma
Disciplina
Aula
Audio
Transcricao
Segmento
Falante
ClassificacaoFIAS
IndicadorFIAS
QuestionarioQTI
RespostaQTI
ResultadoQTI
Triangulacao
ResultadoMTSS
Recomendacao
Relatorio
Processamento
ModeloIA

# ============================================================
# 38. UUID E FUTURA SINCRONIZAÇÃO
# ============================================================

Usar UUID.

Campos:

id
created_at
updated_at
deleted_at
version
sync_status
device_id

Estados:

LOCAL_ONLY
PENDING_SYNC
SYNCED
CONFLICT

Não implementar sincronização agora.

Preparar arquitetura.

# ============================================================
# 39. FUTURA INTERLIGAÇÃO
# ============================================================

Futuro:

ANDROID
↓
API
↓
POSTGRESQL
↓
WEB

Criar:

FUTURE_SYNC.md
FUTURE_SYNC_API.md

# ============================================================
# 40. NÃO USAR BLOB PARA ÁUDIO
# ============================================================

Guardar:

id
path
hash
size
duration
mime_type

Arquivo no filesystem privado.

# ============================================================
# 41. ANDROID OFFLINE
# ============================================================

O aplicativo deve funcionar em:

modo avião
Wi-Fi desligado
dados móveis desligados

Permitir:

importar áudio
processar
transcrever
separar falas
identificar professor
revisar
FIAS
QTI
MTSS
recomendações
PDF

# ============================================================
# 42. PERMISSÃO INTERNET
# ============================================================

Avaliar remover:

android.permission.INTERNET

Se não houver função atual de rede:

não declarar.

# ============================================================
# 43. BACKGROUND
# ============================================================

Android:

WorkManager
Coroutines

Áudio longo não pode travar a interface.

# ============================================================
# 44. REPRODUTIBILIDADE
# ============================================================

Registrar:

app_version
rules_version
asr_model
asr_model_hash
diarization_model
fias_model
fias_model_hash
parameters
hardware
device
audio_duration
processing_time
created_at
transcript_source

# ============================================================
# 45. MÉTRICAS
# ============================================================

Preparar para:

WER
DER
F1
Cohen's Kappa
tempo
memória
pipeline completion rate

# ============================================================
# 46. BENCHMARK ANDROID
# ============================================================

Registrar:

modelo
Android
RAM
SoC
áudio
duração
ASR
tempo
FIAS
tempo total
memória
temperatura
falhas

Criar:

ANDROID_BENCHMARK.md

# ============================================================
# 47. PRIVACY BY DESIGN
# ============================================================

Aplicar:

privacy by design
security by design
least privilege
data minimization
secure defaults
defense in depth

Tratar como dados sensíveis:

áudio
transcrições
QTI
relatórios
dados do professor
dados da turma

# ============================================================
# 48. PRIVACIDADE DE ALUNOS
# ============================================================

Não armazenar nomes sem necessidade.

Não usar:

reconhecimento facial
biometria de voz
identificação individual pela voz

Preferir:

ALUNO

# ============================================================
# 49. LGPD
# ============================================================

Criar:

PRIVACY.md

Documentar:

- dados coletados;
- finalidade;
- localização;
- retenção;
- acesso;
- exclusão;
- anonimização;
- pseudonimização;
- exportação.

Não inventar base legal.

# ============================================================
# 50. SEGURANÇA POSTGRESQL
# ============================================================

PostgreSQL não deve ser acessível diretamente pelo frontend.

Arquitetura correta:

Frontend
↓
FastAPI
↓
PostgreSQL

Preferir banco em rede interna Docker.

Se precisar expor:

127.0.0.1

Evitar:

0.0.0.0

# ============================================================
# 51. USUÁRIO DO BANCO
# ============================================================

Criar usuário específico:

fias_ed_app

Privilégios mínimos.

Não usar usuário administrador.

# ============================================================
# 52. SEGREDOS
# ============================================================

Nunca colocar senha no código.

Usar:

.env

Versionar apenas:

.env.example

Adicionar .env ao .gitignore.

# ============================================================
# 53. AUTENTICAÇÃO WEB
# ============================================================

Usar:

usuário
senha
sessão segura

Hash:

Argon2id

Não usar:

MD5
SHA1
SHA256 simples

# ============================================================
# 54. AUTORIZAÇÃO
# ============================================================

Perfis:

ADMIN_LOCAL
PROFESSOR

Aplicar ownership.

# ============================================================
# 55. API SECURITY
# ============================================================

Usar Pydantic.

Validar:

tipo
tamanho
formato
limite
permissões

Não retornar stack traces.

# ============================================================
# 56. UPLOAD SECURITY
# ============================================================

Validar:

extensão
MIME
estrutura real
tamanho
duração

Renomear por UUID.

Bloquear:

../
..\

Proteger contra path traversal.

# ============================================================
# 57. COMMAND INJECTION
# ============================================================

Para:

FFmpeg
Tesseract

não usar:

shell=True
os.system

Usar argumentos estruturados.

# ============================================================
# 58. SQL INJECTION
# ============================================================

Nunca concatenar SQL.

Usar:

SQLAlchemy
queries parametrizadas.

# ============================================================
# 59. XSS
# ============================================================

Não usar dangerouslySetInnerHTML sem sanitização rigorosa.

Escapar:

transcrição
comentários
turma
disciplina
campos importados

# ============================================================
# 60. CORS
# ============================================================

Não utilizar:

allow_origins=["*"]

Configurar origens conhecidas.

# ============================================================
# 61. CSRF
# ============================================================

Aplicar proteção conforme estratégia de autenticação.

# ============================================================
# 62. ANDROID SECURITY
# ============================================================

Usar armazenamento privado.

Usar Android Keystore quando necessário.

Não guardar segredos em SharedPreferences simples.

# ============================================================
# 63. BACKUP ANDROID
# ============================================================

Revisar:

android:allowBackup
Data Extraction Rules

Evitar envio automático de dados da pesquisa para nuvem.

# ============================================================
# 64. PERMISSÕES ANDROID
# ============================================================

Solicitar somente o necessário.

Para selecionar áudio:

Storage Access Framework.

Se o app não grava:

não solicitar RECORD_AUDIO.

CAMERA somente se OCR existir.

# ============================================================
# 65. LOGS
# ============================================================

Não registrar:

senha
token
transcrição completa
QTI completo
dados pessoais

Registrar:

aula_id
processamento_id
status
tempo
erro técnico

# ============================================================
# 66. MODELOS DE IA
# ============================================================

Registrar:

nome
versão
hash SHA-256
origem
tamanho
parâmetros

Não baixar silenciosamente.

# ============================================================
# 67. SEGURANÇA DOS MODELOS
# ============================================================

Cuidado com:

.pkl
.pickle
.joblib
.pt
.pth

Verificar origem.

Preferir safetensors quando possível.

# ============================================================
# 68. DEPENDÊNCIAS
# ============================================================

Antes de instalar:

verificar manutenção
licença
vulnerabilidades
telemetria
necessidade real

# ============================================================
# 69. AUDITORIA PYTHON
# ============================================================

Executar:

pytest
bandit
pip-audit

# ============================================================
# 70. AUDITORIA WEB
# ============================================================

Executar:

npm test
npm run lint
npm audit

# ============================================================
# 71. AUDITORIA ANDROID
# ============================================================

Executar:

Android Lint
Detekt

Verificar:

permissões
storage
backup
logs
exported components
network security
SDKs externos

# ============================================================
# 72. SCAN DE SEGREDOS
# ============================================================

Executar:

gitleaks

ou equivalente.

# ============================================================
# 73. DOCKER SECURITY
# ============================================================

Não usar:

privileged: true

Evitar root.

Não montar diretórios amplos do Windows.

Usar healthchecks.

# ============================================================
# 74. HEADERS WEB
# ============================================================

Avaliar:

Content-Security-Policy
X-Content-Type-Options
Referrer-Policy
Permissions-Policy
frame-ancestors

# ============================================================
# 75. OWASP
# ============================================================

Verificar:

Broken Access Control
Cryptographic Failures
Injection
Insecure Design
Security Misconfiguration
Vulnerable Components
Authentication Failures
Integrity Failures
Logging Failures
SSRF quando aplicável

# ============================================================
# 76. TESTES DE SEGURANÇA
# ============================================================

Criar testes para:

login inválido
acesso sem autenticação
acesso de outro usuário
SQL injection
XSS
path traversal
upload malformado
arquivo grande demais
extensão falsa
sessão inválida
endpoint administrativo

# ============================================================
# 77. AUDITORIA FINAL
# ============================================================

Criar:

SECURITY_AUDIT.md

Classificar:

CRITICAL
HIGH
MEDIUM
LOW
INFO

Não finalizar com vulnerabilidade:

CRITICAL
ou
HIGH

sem tratamento.

# ============================================================
# 78. TESTE OFFLINE ANDROID
# ============================================================

Criar:

AIRPLANE_MODE_TEST

Etapas:

modo avião
Wi-Fi desligado
dados móveis desligados
abrir app
criar aula
selecionar áudio
processar
transcrever
diarizar
identificar professor
revisar transcrição
FIAS
QTI
triangulação
MTSS
recomendações
PDF

Se precisar de Internet:

TESTE FALHOU.

# ============================================================
# 79. COMPATIBILIDADE WEB/ANDROID
# ============================================================

Criar:

schema_compatibility_test

Testar:

Aula
FIAS
QTI
MTSS
Relatório

# ============================================================
# 80. REGRAS COMPARTILHADAS
# ============================================================

fias-ed-shared/rules/

fias_rules.json
qti_config.json
mtss_rules.json
pedagogical_rules.json

Adicionar:

rules_version

Decisão de 2026-09-24 — concordância FIAS × QTI (fundamentação completa na
seção 4.4 de docs/ESTADO_DE_VALIDACAO.md):

O MTSS é a ferramenta pedagógica do estudo e considera as duas medidas. As
regras continuam sendo DISPARADAS PELO FIAS; o resultado do QTI entra depois,
qualificando a recomendação como concordante, discordante ou inconclusiva.

Sem faixas no lado FIAS. As regras já classificam por presença, ausência e
ID_RATIO < 1, com referência à literatura. Terços na proporção foram
rejeitados: elogio ocupa 1 a 5% de uma aula real e nunca cairia numa faixa
"alta" de 66,7%.

Faixas só no lado QTI, sobre o intervalo teórico da Likert 1 a 5:
  baixa  < 2,33
  média    2,33 a 3,67
  alta   > 3,67
É o único corte inventado do sistema. Gravar como engineering_decision.

Faixa média, ou coleta não exibível, o sistema NÃO conclui nada.
Em discordância, mostra as duas medidas e faz a pergunta. Nunca apresenta como
contradição nem como erro do professor.

NÃO MUDAR SEM NOVA DECISÃO DO ALEX:
  - os cortes 2,33 e 3,67
  - a natureza presença/ausência das regras (não transformar em proporção)
  - a exclusão de oc1 Liderança da regra de TRI_INFLUENCE (efeito de teto)
  - o QTI permanecer fora das CONDIÇÕES das regras

Esta é a única autorização para escrever em fias-ed-shared. Fora dela, o motor
continua somente leitura.

# ============================================================
# 81. RASTREABILIDADE
# ============================================================

Toda regra científica deve possuir:

source_reference

Exemplo:

{
  "rule_id": "MTSS_001",
  "rules_version": "1.0.0",
  "source_reference": "...",
  "validation_status": "validated"
}

Quando não validado:

PENDING_SCIENTIFIC_VALIDATION

# ============================================================
# 82. DOCUMENTAÇÃO
# ============================================================

Criar:

README.md
ARCHITECTURE.md
RESEARCH_INVENTORY.md
ANALISE_MODELOS_EXISTENTES.md
MODELS.md
FIAS.md
QTI.md
MTSS.md
PIPELINE.md
DATABASE_MODEL.md
ENTITY_DICTIONARY.md
OFFLINE_FIRST.md
ANDROID_DIARIZATION_FEASIBILITY.md
ANDROID_BENCHMARK.md
UI_REFERENCES.md
DESIGN_SYSTEM.md
PRIVACY.md
SECURITY_AUDIT.md
FINAL_SECURITY_CHECK.md
SCIENTIFIC_TRACEABILITY.md
SCIENTIFIC_REPRODUCIBILITY.md
FUTURE_SYNC.md
FUTURE_SYNC_API.md

# ============================================================
# 83. ORDEM DE IMPLEMENTAÇÃO
# ============================================================

FASE 01
/superpowers

FASE 02
/impeccable init

FASE 03
Analisar toda a pesquisa.

FASE 04
Gerar RESEARCH_INVENTORY.md.

FASE 05
Analisar experimentos.

FASE 06
Gerar ANALISE_MODELOS_EXISTENTES.md.

FASE 07
Identificar BERTimbau.

FASE 08
Criar arquitetura.

FASE 09
Criar modelo compartilhado.

FASE 10
Criar regras e schemas.

FASE 11
Pesquisar referências visuais.

FASE 12
Criar UI_REFERENCES.md.

FASE 13
Criar DESIGN_SYSTEM.md.

FASE 14
Aplicar paleta oficial.

FASE 15
Configurar Ubuntu + Rokkitt.

FASE 16
Revisar com /Impeccable.

FASE 17
Implementar Web.

FASE 18
Implementar pipeline de áudio.

FASE 19
Implementar FIAS.

FASE 20
Implementar QTI.

FASE 21
Implementar triangulação.

FASE 22
Implementar MTSS.

FASE 23
Implementar recomendações.

FASE 24
Implementar relatório.

FASE 25
Implementar Android.

FASE 26
Converter/testar modelos Android.

FASE 27
Benchmark.

FASE 28
AIRPLANE_MODE_TEST.

FASE 29
Compatibilidade Web/Android.

FASE 30
Auditoria visual com /Impeccable.

FASE 31
Auditoria de segurança.

FASE 32
Correções.

FASE 33
Testes novamente.

FASE 34
Documentação final.

# ============================================================
# 84. CRITÉRIO VISUAL FINAL
# ============================================================

Antes de considerar o frontend concluído, perguntar:

"Esta interface parece um produto criado especificamente para
professores ou parece um template gerado por IA?"

Se parecer template:

refatorar.

Verificar:

- hierarquia;
- espaçamento;
- tipografia;
- contraste;
- consistência;
- uso da paleta;
- uso correto de Ubuntu;
- uso editorial de Rokkitt;
- responsividade;
- densidade;
- legibilidade;
- ausência de gradientes;
- ausência de componentes decorativos desnecessários.

# ============================================================
# 85. CRITÉRIO DE PRODUTO
# ============================================================

Ao abrir o FIAS-ED, o professor deve pensar:

"Posso enviar o áudio da minha aula e compreender melhor como ela
aconteceu."

Ele NÃO deve sentir:

"Estão me avaliando."

A experiência deve comunicar:

AULA
↓
EVIDÊNCIAS
↓
COMPREENSÃO
↓
REFLEXÃO
↓
SUGESTÕES
↓
MELHORIA

# ============================================================
# 86. PRINCÍPIO FINAL
# ============================================================

O professor é o protagonista.

A tecnologia fica nos bastidores.

FIAS, QTI, IA e MTSS existem para transformar dados da aula em
informações pedagógicas compreensíveis.

O produto final deve permitir:

ENVIAR O ÁUDIO
↓
COMPREENDER AS INTERAÇÕES
↓
CONHECER A PERCEPÇÃO DOS ESTUDANTES
↓
REFLETIR
↓
EXPERIMENTAR NOVAS ESTRATÉGIAS
↓
MELHORAR A PRÁTICA DOCENTE

O FIAS-ED deve parecer:

profissional,
acadêmico,
humano,
confiável,
simples,
seguro,
cientificamente rastreável.

Não deve parecer:

chatbot,
dashboard genérico,
produto de IA,
sistema punitivo,
plataforma de ranking.
```
