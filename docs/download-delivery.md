# Entrega privada de downloads

## Fluxo

```text
botão público
  → /download/file/<id>
  → autenticação e plano
  → arquivo/post ativos
  → resolução privada do storage
  → abertura bem-sucedida do upstream
  → registro do download
  → streaming para o cliente
```

`/download/<post_id>?file=<n>` continua funcionando e vira wrapper de
compatibilidade. No primeiro uso de um arquivo legado, cria a associação
estruturada e entrega pela mesma camada.

## Range

O cabeçalho `Range: bytes=...` é encaminhado ao upstream. São preservados
status `206`, `Content-Range`, `Accept-Ranges`, `Content-Length`, `ETag` e
`Last-Modified`. `Content-Disposition` é sempre gerado pela plataforma com nome
sanitizado.

## Privacidade

Em `DOWNLOAD_DELIVERY_MODE=proxy`, respostas públicas não contêm URL, ID ou
nome do storage. Logs de atividade guardam apenas IDs internos e snapshot do
plano. O modo `redirect` é exclusivamente um rollback temporário e expõe a
origem; não deve ser usado em produção.

## Falhas

O limite do plano só é consumido depois de o arquivo local ser encontrado ou
o upstream retornar `200/206`. Falhas marcam `link_status=broken` e retornam uma
mensagem neutra. O job `jobs.check_download_links` revalida em lote.

## Segurança

- apenas HTTP(S) sem credenciais embutidas;
- resolução DNS e bloqueio de endereços não globais;
- validação de todos os redirects;
- timeout de conexão/leitura;
- no máximo cinco redirects;
- rejeição de resposta HTML;
- chunks de 128 KiB e fechamento ao cancelar;
- `Cache-Control: private, no-store` e `nosniff`.
