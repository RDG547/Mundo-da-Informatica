# Motor multi-fonte de datasheets

O motor cataloga componentes eletrônicos por `part number`, compara candidatos entre fontes e cria previews para revisão. Ele foi integrado ao motor técnico existente sem transformar respostas de terceiros em um espelho público por padrão.

## Princípios de segurança e licenciamento

- API é preferida a HTML.
- HTML discovery chega desativado e só funciona com autorização registrada, template de busca restrito, User-Agent descritivo e `robots.txt` permitido.
- CAPTCHA, challenge e HTTP 403 não são contornados.
- Respostas brutas não são persistidas. O banco guarda somente preview normalizado permitido, hashes de proveniência, eventos e decisões.
- Persistência de metadados, republicação pública, referência de PDF, proxy e espelhamento são permissões independentes.
- O download não redireciona o visitante ao storage: quando autorizado, o servidor valida e entrega o PDF pelo proxy interno.
- Autopublicação exige duas feature flags, provider em modo automático, autorização de republicação, confiança suficiente, campos obrigatórios e ausência de conflito/duplicata.

## Componentes implementados

- Providers: Source Parts API, AllDatasheet API configurável, Datasheets.com API, discovery HTML autorizado, feed de fabricante e feed licenciado.
- Resolver: fallback por prioridade e comparação paralela limitada.
- Limites: janelas independentes por minuto, hora, dia e mês, intervalo mínimo, retries curtos e circuit breaker.
- Normalização: part number, fabricante, aliases, specs PT-BR, deduplicação e consenso.
- Banco: componentes, aliases, proveniência por campo, documentos, relação com placas, fila, demandas e eventos de providers.
- Público: `/datasheets`, `/datasheet/<slug>`, busca global, sugestões e componentes vinculados em `/placa/<slug>`.
- Admin: `/admin/datasheets`, controles globais, fontes, permissões, limites, kill switch, fila, previews, métricas, teste isolado e benchmark.
- Jobs: `jobs.sync_datasheets`, `jobs.process_datasheet_queue`, `jobs.verify_datasheet_sources` e `jobs.verify_sources`.

## Credenciais

### Source Parts

1. Crie uma conta e uma API key em <https://source.parts/dashboard/api/keys>.
2. Configure `SOURCE_PARTS_API_KEY`.
3. Configure um `SOURCE_PARTS_USER_AGENT` descritivo com um contato real.
4. Mantenha `ENABLE_SOURCE_PARTS=true`.
5. No painel, abra **Motor de Datasheets > Fontes > Source Parts**, habilite a fonte e registre somente os direitos efetivamente concedidos.

A visão geral oficial (incluindo o acesso às chaves) está em
<https://source.parts/docs>; a referência atual da API está em
<https://source.parts/docs/api>.

### Datasheets.com

1. Gere a key em <https://www.datasheets.com/api-docs>.
2. Configure `DATASHEETS_COM_API_KEY`.
3. Defina `ENABLE_DATASHEETS_COM_API=true`.
4. Ative a fonte no painel.

Os termos padrão não devem ser interpretados como autorização para republicar ou espelhar o banco/PDFs. Leia <https://www.datasheets.com/terms> e registre permissão adicional antes de marcar esses direitos no painel.

### AllDatasheet

O AllDatasheet informa que a API depende de cadastro/aprovação, mas não publica um contrato REST universal. Solicite o acesso na página <https://www.alldatasheet.com/bottom_bar/alldatasheet_api.html> ou pelo contato informado pelo serviço.

Depois de receber o pacote oficial, configure exatamente os valores fornecidos:

- `ALLDATASHEET_API_KEY`
- `ALLDATASHEET_API_URL`
- `ALLDATASHEET_API_AUTH_HEADER`
- `ALLDATASHEET_API_QUERY_PARAMETER`
- `ENABLE_ALLDATASHEET_API=true`

A key sozinha não é suficiente. O adapter recusa a consulta se endpoint, header ou parâmetro estiverem ausentes, evitando inventar uma API.

### Feeds de fabricante ou licenciados

Um **feed licenciado** é um endpoint ou arquivo de dados entregue por um parceiro mediante contrato. Ele não é uma chave genérica disponível na internet. Use somente quando possuir acesso e permissões documentadas:

- `MANUFACTURER_DATASHEET_FEED_URL` e, se exigido, `MANUFACTURER_DATASHEET_FEED_TOKEN`
- `LICENSED_DATASHEET_FEED_URL` e, se exigido, `LICENSED_DATASHEET_FEED_TOKEN`

### HTML discovery

Não exige uma API key, mas exige autorização escrita, `robots.txt` permitido e um template de busca restrito que contenha `{part_number}`. Configure somente após obter essa permissão:

- `DATASHEET_DISCOVERY_USER_AGENT`
- `ALLDATASHEET_HTML_SEARCH_URL` ou `DATASHEETS_COM_HTML_SEARCH_URL`
- feature flag HTML correspondente
- permissões e referência da autorização no painel

## Onde colocar as secrets

- Local: no arquivo `.env`, que está ignorado pelo Git.
- Render: **Dashboard > serviço Mundo da Informática > Environment > Add Environment Variable**.
- `.env.example`: apenas nomes e placeholders; nunca coloque chaves reais.

Depois de alterar variáveis no Render, salve e faça um novo deploy. O painel mostra quais credenciais estão configuradas sem exibir seus valores.

## Ativação recomendada

1. Rode `python migrate_db.py`.
2. Configure uma fonte por vez, começando pela Source Parts.
3. Deixe `ENABLE_DATASHEET_AUTO_PUBLISH=false`.
4. No painel, registre a política da fonte e habilite somente **Persistir metadados** quando o contrato permitir.
5. Adicione part numbers, processe a fila e revise os previews.
6. Publique manualmente apenas se **Republicar publicamente** estiver documentado.
7. Libere proxy/espelhamento de PDF somente se o contrato permitir explicitamente.
8. Use o benchmark para medir cobertura antes de habilitar outro provider.

## Jobs e Render

Comandos:

```bash
python -m jobs.sync_datasheets
python -m jobs.process_datasheet_queue
python -m jobs.verify_datasheet_sources
```

O deploy atual usa SQLite em disco persistente. Um Render Cron Job separado não compartilha automaticamente o mesmo processo/disco do Web Service; por isso o `render.yaml` não cria cron services que escreveriam em outro banco. Para agenda externa, use PostgreSQL compartilhado ou execute o comando em um worker que aponte para a mesma `DATABASE_URL`.

`DATASHEET_SYNC_PROCESS` permanece `false` por padrão: o job de sync apenas enfileira itens e demandas. O processamento é uma etapa separada e auditável.
O job também enfileira part numbers já estruturados em `TechnicalResource` (incluindo o vínculo real com `HardwareBoard`), limitado por `DATASHEET_SYNC_RESOURCE_LIMIT`; ele não executa OCR nem tenta inferir componentes a partir de texto livre.

## Rollback

- Pausa no painel: marca `datasheet_automation_paused` sem apagar dados.
- Kill switch do ambiente: `DISABLE_ALL_DATASHEET_AUTOMATION=true`.
- Desativar motor: `ENABLE_DATASHEET_ENGINE=false`.
- Desativar um provider: botão **Desativar agora** no painel ou feature flag individual.

As migrações são aditivas. Desativar o motor não remove componentes já revisados nem altera os fluxos de BIOS/EC/BoardView existentes.
