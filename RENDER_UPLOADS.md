# 📦 Persistência de Uploads no Render

## ⚠️ Problema
Por padrão, o Render reinicia o container a cada deploy, **apagando todos os arquivos** que não estão no código-fonte (fotos de perfil, imagens de posts, etc).

## ✅ Solução Implementada

### 1. Disco Persistente (Persistent Disk)
Configurado em `render.yaml`:
```yaml
disk:
  name: persistent-data
  mountPath: /opt/render/project/src/data
  sizeGB: 3
```

Este disco **NÃO É APAGADO** entre deploys!

### 2. Estrutura de Diretórios
```
/opt/render/project/src/
├── data/                           # 💾 PERSISTENTE (disco)
│   ├── site.db                    # Banco de dados
│   ├── images/
│   │   ├── posts/                 # Imagens dos posts
│   │   ├── profiles/              # Fotos de perfil
│   │   └── admin/                 # Imagens admin
│   └── uploads/
│       └── profiles/              # Uploads de perfis
├── instance -> data/               # 🔗 Symlink
├── static/
│   ├── images -> data/images/     # 🔗 Symlink
│   └── uploads -> data/uploads/   # 🔗 Symlink
```

### 3. Build Command
O comando de build cria os symlinks automaticamente:
```bash
pip install -r requirements.txt &&
mkdir -p /opt/render/project/src/data/images/posts \
         /opt/render/project/src/data/images/profiles \
         /opt/render/project/src/data/images/admin \
         /opt/render/project/src/data/uploads/profiles &&
([ -L /opt/render/project/src/instance ] && rm -f /opt/render/project/src/instance || true) &&
([ -L /opt/render/project/src/static/images ] && rm -f /opt/render/project/src/static/images || true) &&
([ -L /opt/render/project/src/static/uploads ] && rm -f /opt/render/project/src/static/uploads || true) &&
ln -sfn /opt/render/project/src/data /opt/render/project/src/instance &&
ln -sfn /opt/render/project/src/data/images /opt/render/project/src/static/images &&
ln -sfn /opt/render/project/src/data/uploads /opt/render/project/src/static/uploads &&
python migrate_db.py
```

**Explicação:**
- `[ -L path ]`: Verifica se é um symlink
- `rm -f`: Remove apenas o symlink (não o conteúdo)
- `|| true`: Ignora erros se o symlink não existir

## 🔍 Como Verificar se Está Funcionando

### No Render Dashboard:
1. Acesse seu serviço
2. Vá em "Shell" (terminal)
3. Execute:
```bash
ls -la /opt/render/project/src/static/
ls -la /opt/render/project/src/data/images/
```

Você deve ver os symlinks (`->`) apontando para `/opt/render/project/src/data/`

### Teste de Persistência:
1. Faça upload de uma foto de perfil
2. Faça um novo deploy (git push)
3. A foto deve continuar lá! ✅

## 📌 Importante

- **Disco persistente custa $**: Verifique o plano do Render
- **Backup regular**: O disco é persistente, mas faça backups!
- **Migrations**: Use `python migrate_db.py` para atualizar o schema do banco

## 🐛 Troubleshooting

### Fotos somem após deploy?
```bash
# Verifique os symlinks no Shell do Render
ls -la /opt/render/project/src/static/images
ls -la /opt/render/project/src/static/uploads

# Devem mostrar algo como:
# images -> /opt/render/project/src/data/images
# uploads -> /opt/render/project/src/data/uploads
```

### Erro "Permission denied"?
```bash
# Verifique permissões
ls -la /opt/render/project/src/data/
chmod -R 755 /opt/render/project/src/data/
```

## 📚 Referências
- [Render Persistent Disks](https://render.com/docs/disks)
- [Flask File Uploads](https://flask.palletsprojects.com/en/2.3.x/patterns/fileuploads/)
