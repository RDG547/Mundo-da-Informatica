# Motor de conteúdo técnico

## Visão geral

O motor foi adicionado de forma incremental ao fluxo de `Post`. Posts, URLs
antigas, categorias, planos e o painel continuam válidos. As novas entidades
estruturam o acervo sem transformar o `Post` legado em um objeto incompatível:

- `HardwareBoard`: identidade normalizada da placa;
- `TechnicalResource`: recurso técnico e sua política/origem;
- `TechnicalFile`: arquivo e storage privado;
- `ImportJob` e `ImportItem`: execução, preview e auditoria;
- `ContentSource`: confiança e permissões da fonte;
- `FileContribution`: envio de usuário sempre sujeito a revisão.

## Central administrativa

Acesse **Painel Admin → Conteúdo Técnico** (`/admin/tools/import`). A Central
aceita arquivos individuais, múltiplos arquivos, ZIP, CSV, lista de part
numbers e links diretos de storage.

Cada entrada gera preview com título, categoria, fabricante, modelo, placa,
revisão, tipo, chip, SHA-256, fonte, storage e confiança. O admin pode editar,
aprovar ou rejeitar. Duplicados por SHA-256 não são republicados.
Arquivos do mesmo job com a mesma placa (por exemplo BIOS U3, EC U9,
BoardView e esquema extraídos de um ZIP) são publicados no mesmo post/recurso,
com botões de download individuais.

## Automação

Há três modos:

1. `off`: desativa jobs automáticos e sincronizações; importações manuais
   ainda podem gerar previews. A feature flag de ambiente pode bloquear todo
   o motor.
2. `semi`: tudo passa por aprovação do admin.
3. `full`: somente itens que cumprem confiança mínima, rollout percentual,
   política da fonte e storage pronto são publicados.

O percentual é determinístico pelo SHA-256/ID. Um mesmo item não alterna de
grupo entre execuções. Fontes nível D (usuários) nunca são autopublicadas.
Mesmo no modo completo, a fonte precisa autorizar separadamente metadados e
distribuição. O admin pode ligar/desligar cada fonte, ajustar a confiança,
definir os part numbers monitorados e disparar uma sincronização pela Central.

## Fontes

Mouser e DigiKey usam APIs oficiais e são opcionais. Dell, HP, Lenovo e feeds
licenciados ficam preparados como fontes opt-in; não há scraping nem browser
automation.

- Mouser: crie uma conta, solicite a Search API e configure
  `MOUSER_API_KEY`. A API oficial documenta até 30 chamadas/minuto e 1.000/dia.
- DigiKey: crie uma Organization App no Developer Portal e configure
  `DIGIKEY_CLIENT_ID`, `DIGIKEY_CLIENT_SECRET` e, se aplicável,
  `DIGIKEY_ACCOUNT_ID`.
- Dell: os catálogos oficiais são CABs assinados. A ingestão em lote requer um
  extrator CAB no worker ou conversão autorizada para feed JSON.
- HP: use HPIA/CMSL ou um feed oficialmente licenciado.
- Lenovo: use Update Retriever/repositório oficialmente gerenciado ou feed
  licenciado.

Credenciais ficam somente em secrets do ambiente. O painel grava apenas a
lista de part numbers e as políticas da fonte. Para Dell/HP/Lenovo, os jobs
aceitam um feed JSON normalizado autorizado; o CAB oficial da Dell é detectado
e recusado pelo conector JSON até existir um worker com extrator CAB.

Referências oficiais:

- https://www.mouser.com/api-search/
- https://developer.digikey.com/products/product-information-v4/productsearch/productdetails
- https://www.dell.com/support/kbdoc/en-us/000122176/driver-pack-catalog
- https://support.hp.com/gb-en/document/ish_7636709-7636753-16

## ZIP e segurança

Antes de extrair, o parser limita quantidade, tamanho individual, tamanho
total e taxa de compressão; rejeita traversal e symlinks. HTML, SVG, scripts e
extensões ativas não entram no acervo. Arquivos finais recebem SHA-256 em
streaming, sem leitura integral em RAM.

## CSV

Cabeçalhos úteis: `filename`, `title`, `manufacturer`, `model`, `board_code`,
`board_revision`, `file_type`, `version`, `provider_url`, `source_provider`,
`distribution_policy`. Campos ausentes permanecem ausentes; o sistema não
inventa metadados.

## Jobs

```bash
python -m jobs.seed_content_sources
python -m jobs.sync_dell
python -m jobs.sync_hp
python -m jobs.sync_lenovo
python -m jobs.sync_datasheets
python -m jobs.process_import_queue
python -m jobs.check_download_links
python -m jobs.sync_configured_sources
```

Em produção, execute os jobs em Cron Jobs separados, com lotes pequenos. Não
rode duas instâncias do mesmo job simultaneamente até adicionar um lock
distribuído (Redis/PostgreSQL advisory lock).

Sugestão de agendamento no Render: sincronizações uma vez por dia,
`process_import_queue` a cada 15 minutos e `check_download_links` a cada 6
horas. Sincronização e publicação respeitam o botão de ativação e o modo do
painel. A checagem de links permanece operacional para monitorar o acervo já
publicado mesmo com a importação pausada.

O `render.yaml` atual usa SQLite em disco persistente. Como um Cron Job do
Render é outro serviço e não compartilha esse disco, mantenha o disparo manual
pela Central enquanto estiver em SQLite. Para cron automático, use PostgreSQL
compartilhado como `DATABASE_URL` no web service e nos Cron Jobs; não crie uma
segunda cópia do banco SQLite.

## Rollback

Desative `TECHNICAL_IMPORT_ENABLED`; os posts legados continuam funcionando.
Itens e jobs ficam preservados para auditoria. As migrations são aditivas e
não removem colunas/tabelas antigas.
