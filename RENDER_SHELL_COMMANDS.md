# 🔧 Comandos para Executar no Shell do Render

## 1. Acessar o Shell

1. Entre no Dashboard do Render: https://dashboard.render.com
2. Selecione seu serviço "mundodainformatica"
3. Clique em **"Shell"** no menu lateral

## 2. Executar Migração do Banco de Dados

```bash
python migrate_db.py
```

**Saída esperada:**
```
Adding daily_downloads column...
✓ daily_downloads column added
Adding download_reset_date column...
✓ download_reset_date column added
Adding weekly_downloads column...
✓ weekly_downloads column added
Adding week_reset_date column...
✓ week_reset_date column added

✅ All migrations completed successfully!
```

## 3. Verificar se a migração funcionou

```bash
python -c "from app import app, db, User; app.app_context().push(); user = User.query.first(); print(f'User: {user.username}'); print(f'Daily downloads: {user.daily_downloads}'); print(f'Weekly downloads: {user.weekly_downloads}')"
```

## 4. Reiniciar a aplicação (opcional)

No dashboard do Render, clique em **"Manual Deploy"** → **"Deploy latest commit"** ou espere o deploy automático terminar.

## 5. Verificar logs

```bash
# No dashboard, vá em "Logs" para ver se não há mais erros
```

---

## ⚠️ Se houver problemas

### Erro: "Database not found"

O banco está no caminho correto do Render:
```bash
ls -la /opt/render/project/src/data/site.db
```

Se não existir, o caminho pode ser:
```bash
ls -la /opt/render/project/src/instance/site.db
```

### Reexecutar migração manualmente

```bash
cd /opt/render/project/src
python migrate_db.py
```

### Verificar estrutura da tabela

```bash
python -c "import sqlite3; conn = sqlite3.connect('instance/site.db'); cursor = conn.cursor(); cursor.execute('PRAGMA table_info(user)'); print([col[1] for col in cursor.fetchall()])"
```

---

## 📝 Colunas Adicionadas

1. **daily_downloads** (INTEGER, DEFAULT 0)
   - Contador de downloads do usuário no dia atual
   
2. **download_reset_date** (DATETIME)
   - Data/hora do próximo reset do contador diário

3. **weekly_downloads** (INTEGER, DEFAULT 0)
   - Contador de downloads do usuário na semana atual

4. **week_reset_date** (DATETIME)
   - Data/hora do próximo reset semanal (domingo 00:00)

---

## ✅ Após executar

- O erro `no such column: user.daily_downloads` será corrigido
- Os controles de download no painel admin funcionarão corretamente
- Os limites de download (Free: 1/dia, Premium: 15/semana, VIP: ilimitado) estarão operacionais
