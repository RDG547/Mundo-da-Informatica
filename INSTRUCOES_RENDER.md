# 🚀 Instruções Completas - Deploy no Render

## ⚠️ IMPORTANTE: Problema com SQLite no Render

O SQLite **não funciona bem** em ambientes cloud como o Render devido a problemas com discos persistentes e permissões.

**SOLUÇÃO:** Use PostgreSQL (gratuito no Render!)

---

## 📋 **Passo a Passo Completo**

### **1. Criar Banco PostgreSQL no Render**

1. Acesse: https://dashboard.render.com
2. Clique em **"New +"** → **"PostgreSQL"**
3. Configure:
   - **Name:** `mundodainformatica-db`
   - **Database:** `mundodainformatica`
   - **User:** `mundodainformatica_user` (pode deixar o padrão)
   - **Region:** `Frankfurt (EU Central)` ou a mesma região que seu Web Service
   - **Plan:** **Free** (500MB)
4. Clique em **"Create Database"**
5. **Aguarde 2-3 minutos** enquanto o banco é criado

### **2. Copiar URL do Banco de Dados**

1. Após criado, clique no banco `mundodainformatica-db`
2. Na seção **"Connections"**, você verá:
   - **Internal Database URL** (use esta!)
   - External Database URL
3. **Copie a "Internal Database URL"**
   - Formato: `postgresql://user:password@hostname/database`
   - Exemplo: `postgresql://mundodainformatica_user:abc123...@dpg-xyz/mundodainformatica`

### **3. Criar/Atualizar Web Service**

#### Se ainda não criou o Web Service:

1. Clique em **"New +"** → **"Web Service"**
2. Conecte seu repositório `RDG547/mundodainformatica`
3. Configure:
   - **Name:** `mundodainformatica`
   - **Region:** **Mesma do banco PostgreSQL!**
   - **Branch:** `main`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`

#### Se já criou o Web Service:

1. Vá em **"Dashboard"** → clique no seu serviço `mundodainformatica`
2. Vá em **"Settings"**

### **4. Configurar Variáveis de Ambiente**

1. No Web Service, vá em **"Environment"** (barra lateral esquerda)
2. Clique em **"Add Environment Variable"**
3. Adicione as seguintes variáveis:

```
DATABASE_URL=<cole_aqui_a_internal_database_url_do_passo_2>
```

**Exemplo:**
```
DATABASE_URL=postgresql://mundodainformatica_user:abc123def456...@dpg-xyz123.frankfurt-postgres.render.com/mundodainformatica
```

4. **OPCIONAL:** Adicione uma SECRET_KEY personalizada:
```
SECRET_KEY=<sua_chave_aleatoria>
```

Para gerar uma chave aleatória, use:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

5. Clique em **"Save Changes"**

### **5. Deploy Manual (se necessário)**

1. Vá na aba **"Manual Deploy"** (barra lateral esquerda)
2. Clique em **"Deploy latest commit"**
3. Aguarde 5-10 minutos

### **6. Inicializar o Banco de Dados**

**IMPORTANTE:** O banco PostgreSQL está vazio! Você precisa criar as tabelas.

#### **Opção A: Via código Python (Recomendado)**

Adicione este código temporário no final do seu `app.py`:

```python
# Código temporário para criar tabelas - REMOVER APÓS USO
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ Tabelas criadas com sucesso!")
    app.run(debug=False)
```

Depois faça commit e push.

#### **Opção B: Via Shell do Render**

1. No Web Service, vá em **"Shell"** (barra lateral)
2. Execute:
```bash
python3
```

3. Dentro do Python:
```python
from app import app, db
with app.app_context():
    db.create_all()
print("✅ Tabelas criadas!")
exit()
```

### **7. Verificar se Funcionou**

1. Acesse: `https://mundodainformatica.onrender.com`
2. Você deve ver seu site funcionando!

Se der erro 500, veja os logs em **"Logs"** no dashboard.

---

## 🔍 **Verificar Configuração**

### **Confirmar que está usando PostgreSQL:**

Nos logs do Render, você deve ver:
```
Banco de dados: PostgreSQL
```

NÃO deve aparecer:
```
Banco SQLite
```

### **Comandos úteis no Shell:**

```bash
# Ver variáveis de ambiente
env | grep DATABASE_URL

# Testar conexão com banco
python3 -c "from app import db; print(db.engine.url)"
```

---

## ⚙️ **Remover Configuração do Disco (não é mais necessário)**

Se você tinha configurado um disco persistente antes:

1. Vá em **"Settings"** → **"Disks"**
2. Delete o disco `data` (não é mais necessário com PostgreSQL)

---

## 🐛 **Troubleshooting**

### **Erro: "relation does not exist"**
- **Problema:** Tabelas não foram criadas
- **Solução:** Execute o passo 6 (Inicializar o Banco)

### **Erro: "could not connect to server"**
- **Problema:** DATABASE_URL incorreta
- **Solução:** Verifique se copiou a "Internal Database URL" corretamente

### **Erro: "no pg_hba.conf entry"**
- **Problema:** Tentando usar External URL
- **Solução:** Use a **Internal Database URL**

### **Site demora muito para carregar**
- **Problema:** Plano gratuito hiberna após 15 min
- **Solução:** Normal no free tier, primeira requisição demora ~30s

---

## 📦 **Migrar Dados do SQLite Local para PostgreSQL**

Se você já tem dados no SQLite local e quer migrar:

1. **Exportar dados do SQLite:**
```bash
sqlite3 instance/site.db .dump > backup.sql
```

2. **Adaptar o SQL para PostgreSQL** (remover comandos incompatíveis)

3. **Importar no PostgreSQL** via Shell do Render

**OU** use ferramentas como `pgloader` para conversão automática.

---

## ✅ **Checklist Final**

- [ ] Banco PostgreSQL criado no Render
- [ ] Internal Database URL copiada
- [ ] Web Service criado/atualizado
- [ ] DATABASE_URL configurada nas variáveis de ambiente
- [ ] Deploy realizado
- [ ] Tabelas criadas no banco (passo 6)
- [ ] Site acessível e funcionando

---

**Tudo pronto! Seu site está online com PostgreSQL! 🎉**
