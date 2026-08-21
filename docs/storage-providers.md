# Storage providers

## Princípio

`source_provider` descreve a origem técnica e pode ser mostrado quando útil.
`storage_provider`, IDs e URLs do provedor são privados. Eles nunca fazem
parte de APIs públicas nem do HTML público.

## Providers disponíveis

### Local persistente

Uploads aprovados são copiados para `TECHNICAL_LOCAL_STORAGE_DIR` usando SHA-256
como nome. No Render, a configuração aponta para o disco persistente:

```text
/opt/render/project/src/data/technical-files
```

O navegador recebe o arquivo por `send_file(..., conditional=True)`, que
preserva Range/retomada sem carregar o arquivo inteiro na memória.

### HTTP/MediaFire Premium

Links diretos existentes continuam cadastrados apenas em `TechnicalFile`.
`HttpStorageProvider` segue redirects manualmente, valida cada destino,
bloqueia IPs privados/reservados e transmite os bytes em chunks.

Não foi adicionada automação de tela ou scraping do MediaFire. Se o link
apontar para uma página HTML em vez do binário, ele será marcado como quebrado
e o admin deverá fornecer o link direto válido. Isso preserva os links atuais
sem depender de seletores frágeis ou violar políticas do provedor.

## Allowlist

`STORAGE_ALLOWED_HOSTS` vazio permite hosts HTTP(S) públicos, mantendo o
bloqueio SSRF. Em produção, prefira uma lista explícita:

```env
STORAGE_ALLOWED_HOSTS=mediafire.com,dl.dell.com,downloads.dell.com
```

Subdomínios desses domínios são aceitos. Redirecionamentos para domínios fora
da lista são recusados.

## Associação manual

No preview, o admin pode preencher **Link direto privado** e a política
`external_storage_allowed`/`remote_only`. Esse valor só é enviado à API admin.

## Políticas

- `local_allowed`: arquivo pode permanecer no storage local;
- `external_storage_allowed`: pode ser armazenado em provider externo;
- `remote_only`: bytes permanecem na origem autorizada;
- `metadata_only`: apenas metadados; não cria download até associar arquivo;
- `manual_review`: exige decisão humana;
- `unknown`: não distribui automaticamente.
