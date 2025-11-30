# 🚀 Guia de Deploy - Render com SQLite e Disco Persistente

## 📋 Pré-requisitos
- Conta no GitHub
- Conta no Render (https://render.com)
- Código já no GitHub

## 🎯 Passo a Passo Completo

### **1. Configurar Variáveis de Ambiente no Render**

1. Acesse: https://dashboard.render.com
2. Vá no seu Web Service `mundodainformatica`
3. Clique em **"Environment"** (barra lateral esquerda)
4. Adicione/verifique as seguintes variáveis:

```
DATABASE_URL=sqlite:////opt/render/project/src/instance/site.db
SECRET_KEY=<gere_uma_chave_aleatoria>
```

Para gerar uma SECRET_KEY segura:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### **2. Configurar Disco Persistente**

> **IMPORTANTE:** Sem o disco persistente, seus dados serão perdidos a cada deploy!

1. No Web Service, vá em **"Settings"** → **"Disks"**
2. Clique em **"Add Disk"**
3. Configure:
   - **Name:** `data`
   - **Mount Path:** `/opt/render/project/src/instance`
   - **Size:** `1 GB` (gratuito)
4. Clique em **"Save"**

### **3. Fazer Deploy**

1. Vá em **"Manual Deploy"**
2. Clique em **"Deploy latest commit"**
3. Aguarde 5-10 minutos

### **4. Verificar nos Logs**

Quando o deploy terminar, nos logs você deve ver:
```
📁 Banco SQLite: Será criado em sqlite:////opt/render/project/src/instance/site.db
```

### **5. Inicializar o Banco de Dados**

O banco estará vazio na primeira vez. Para criar as tabelas:

#### **Opção A: Via Shell do Render**

1. No Web Service, clique em **"Shell"** (barra lateral)
2. Execute:
```bash
python3
```

3. No prompt do Python:
```python
from app import app, db
with app.app_context():
    db.create_all()
    print("✅ Tabelas criadas com sucesso!")
exit()
```

#### **Opção B: Adicionar código temporário**

No `app.py`, adicione no final (depois de `if __name__ == '__main__':`):

```python
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ Banco inicializado!")
    app.run(debug=False)
```

Depois de fazer deploy uma vez, **remova esse código**.

### **6. Acessar o Site**

Seu site estará disponível em:
```
https://mundodainformatica.onrender.com
```

## ⚠️ Problemas Comuns e Soluções

### **Erro: "unable to open database file"**

**Causa:** Disco persistente não configurado ou caminho errado

**Solução:**
1. Verifique se o disco foi criado corretamente
2. Confirme que o mount path é: `/opt/render/project/src/instance`
3. Verifique se DATABASE_URL está: `sqlite:////opt/render/project/src/instance/site.db`
   - **Atenção:** São 4 barras `////` no caminho!

### **Erro: "No such table"**

**Causa:** Banco criado mas tabelas não foram inicializadas

**Solução:** Execute o passo 5 (Inicializar o Banco de Dados)

### **Site muito lento na primeira visita**

**Causa:** Plano gratuito hiberna após 15 minutos de inatividade

**Solução:**
- É normal, a primeira requisição demora ~30-60 segundos
- Considere usar um serviço de "ping" para manter o site ativo:
  - https://uptimerobot.com (gratuito)
  - Configure para fazer ping a cada 5 minutos

### **Dados sumindo após deploy**

**Causa:** Disco persistente não está configurado ou está com problemas

**Solução:**
1. Verifique se o disco aparece em Settings → Disks
2. Confirme que o tamanho não está cheio
3. Reinstale o disco se necessário (seus dados serão perdidos)

### **Erro 500 ao acessar**

**Causa:** Várias possíveis

**Solução:**
1. Veja os logs detalhados em "Logs"
2. Procure por erros Python
3. Verifique se todas as dependências foram instaladas

## 📊 Verificar Se Está Funcionando

### **Checklist:**

- [ ] Disco persistente criado (1GB em `/opt/render/project/src/instance`)
- [ ] DATABASE_URL configurada com 4 barras
- [ ] SECRET_KEY configurada
- [ ] Deploy concluído sem erros
- [ ] Logs mostram "📁 Banco SQLite"
- [ ] Tabelas criadas com `db.create_all()`
- [ ] Site acessível em https://mundodainformatica.onrender.com

## 🔧 Comandos Úteis no Shell

```bash
# Ver variáveis de ambiente
env | grep DATABASE_URL

# Verificar se o diretório instance existe
ls -la /opt/render/project/src/instance/

# Ver tamanho do banco de dados
du -h /opt/render/project/src/instance/site.db

# Testar conexão com o banco
python3 -c "from app import db; print(db.engine.url)"
```

## 💾 Backup do Banco de Dados

Para fazer backup do seu banco SQLite no Render:

1. Acesse o Shell
2. Execute:
```bash
cat /opt/render/project/src/instance/site.db | base64
```

3. Copie a saída e salve num arquivo local
4. Para restaurar, use:
```bash
echo "<conteudo_base64>" | base64 -d > site.db
```

## 🎉 Pronto!

Seu site está no ar com SQLite e disco persistente!

---

## 📝 Notas Importantes

- **Plano Free:** 750 horas/mês, hiberna após 15min
- **Disco:** 1GB gratuito, suficiente para a maioria dos projetos
- **Backups:** Faça backups regulares do banco de dados
- **Alternativa:** Para produção séria, considere migrar para PostgreSQL no futuro
