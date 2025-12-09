# Configuração do Render - Mundo da Informática

## Problemas Resolvidos

### 1. ✅ Banco de Dados não Persiste
**Problema:** Posts criados localmente não aparecem no Render após deploy.

**Causa:** SQLite não persiste sem disco montado - cada deploy recria o ambiente.

**Solução:** 
- Disco persistente de 3GB em `/opt/render/project/src/data`
- Banco em `/opt/render/project/src/data/site.db`
- Link simbólico `instance/` → `/data/`

**Migração:**
```bash
# No Render Shell
cd /opt/render/project/src/data
# Upload do arquivo instance/site.db local aqui
```

### 2. ✅ Imagens não Salvam
**Problema:** Imagens de perfil e posts desaparecem após redeploy.

**Causa:** Arquivos fora do disco persistente são perdidos.

**Solução:** 
Links simbólicos para diretório persistente:
```
static/images/  → /data/images/
static/uploads/ → /data/uploads/
```

**Estrutura:**
```
/opt/render/project/src/data/
├── site.db                    # Banco de dados
├── images/                    # Imagens do site
│   ├── posts/                 # Imagens de posts
│   ├── profiles/              # Imagens antigas
│   └── admin/                 # Imagens do admin
└── uploads/                   # Uploads de usuários
    └── profiles/              # Fotos de perfil
```

### 3. ✅ Botão Cancelar Invisível
**Problema:** Botão "Cancelar" só aparece ao passar o mouse.

**Solução:** CSS atualizado com `!important`:
```css
.btn-outline {
    color: var(--primary-color) !important;
}
```

## Configuração Atual (render.yaml)

```yaml
disk:
  name: persistent-data
  mountPath: /opt/render/project/src/data
  sizeGB: 3

buildCommand: |
  pip install -r requirements.txt && 
  mkdir -p /data/images/posts /data/images/profiles /data/uploads/profiles &&
  ln -sfn /data /instance &&
  ln -sfn /data/images /static/images &&
  ln -sfn /data/uploads /static/uploads &&
  python migrate_db.py
```

## Passo a Passo para Deploy

### Primeira Vez

1. **Faça o deploy no Render**
   - Conecte o repositório GitHub
   - O disco persistente será criado vazio
   - Links simbólicos são configurados automaticamente

2. **Migre o banco de dados**
   ```bash
   # No Render Shell
   cd /opt/render/project/src/data
   # Upload do instance/site.db local
   ```

3. **Migre as imagens**
   ```bash
   cd /opt/render/project/src/data/images
   # Upload das pastas: posts/, profiles/, admin/
   ```

### Próximos Deploys

✅ Dados persistem automaticamente
✅ Imagens mantidas
✅ Apenas código é atualizado

## Comandos Úteis

### Verificar estrutura
```bash
ls -la /opt/render/project/src/data/
ls -la /opt/render/project/src/static/images  # Link simbólico
readlink /opt/render/project/src/instance     # Deve apontar para /data
```

### Verificar espaço
```bash
df -h /opt/render/project/src/data
du -sh /opt/render/project/src/data/*
```

### Backup
```bash
# Baixe todo o diretório data/
cd /opt/render/project/src/data
tar -czf backup.tar.gz .
# Download backup.tar.gz
```

## Limitações do Render Free

| Recurso | Limite |
|---------|--------|
| Discos persistentes | 1 disco |
| Tamanho total | 3 GB |
| Sleep após inatividade | 15 minutos |
| Build time | 15 minutos |

## Troubleshooting

### Posts não aparecem
```bash
# Verifique se o banco existe
ls -lh /opt/render/project/src/data/site.db

# Verifique se o link está correto
readlink /opt/render/project/src/instance
```

### Imagens não carregam
```bash
# Verifique estrutura
ls -la /opt/render/project/src/data/images/posts/

# Verifique link simbólico
ls -la /opt/render/project/src/static/images
```

### Erro "no such column"
```bash
# Execute a migração
cd /opt/render/project/src
python migrate_db.py
```

## Checklist de Verificação

- [ ] Disco persistente montado em `/data`
- [ ] Link simbólico `instance/` → `/data/`
- [ ] Link simbólico `static/images/` → `/data/images/`
- [ ] Link simbólico `static/uploads/` → `/data/uploads/`
- [ ] Banco de dados existe em `/data/site.db`
- [ ] Pastas criadas: `/data/images/posts`, `/data/images/profiles`, `/data/uploads/profiles`
- [ ] Migração executada: `python migrate_db.py`
- [ ] Botão Cancelar visível nos modais

## Suporte

Se os problemas persistirem:
1. Verifique os logs no painel do Render
2. Acesse o Shell e execute os comandos de verificação
3. Confirme que o disco persistente está montado
4. Verifique se os links simbólicos estão corretos
