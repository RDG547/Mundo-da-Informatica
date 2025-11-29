# 🚀 Guia de Deploy - Mundo da Informática

Este guia contém instruções passo-a-passo para colocar seu projeto online de forma gratuita.

## 📦 Opção 1: Render.com (Recomendado)

### Por que Render?
- ✅ Totalmente gratuito
- ✅ Deploy automático do GitHub
- ✅ SSL/HTTPS automático
- ✅ Suporte nativo a Python e SQLite
- ✅ Disco persistente para o banco de dados

### Passo a Passo

#### 1. Preparar o Repositório GitHub
```bash
# Inicialize o git (se ainda não fez)
git init
git add .
git commit -m "Initial commit"

# Crie um repositório no GitHub e faça push
git remote add origin https://github.com/seu-usuario/mundodainformatica.git
git branch -M main
git push -u origin main
```

#### 2. Criar Conta no Render
1. Acesse: https://render.com
2. Clique em "Get Started for Free"
3. Faça login com sua conta GitHub

#### 3. Criar Novo Web Service
1. No dashboard, clique em **"New +"** → **"Web Service"**
2. Conecte seu repositório GitHub `mundodainformatica`
3. Preencha os campos:
   - **Name:** `mundodainformatica`
   - **Region:** `Frankfurt (EU Central)` ou `Oregon (US West)`
   - **Branch:** `main`
   - **Runtime:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn app:app`

#### 4. Configurar Variáveis de Ambiente
Na seção "Environment Variables", adicione:
```
SECRET_KEY=valor_aleatorio_seguro_aqui
DATABASE_URL=sqlite:///./instance/site.db
FLASK_ENV=production
```

#### 5. Adicionar Disco Persistente (IMPORTANTE!)
1. Role até a seção **"Disk"**
2. Clique em **"Add Disk"**
3. Configure:
   - **Name:** `data`
   - **Mount Path:** `/opt/render/project/src/instance`
   - **Size:** `1 GB` (gratuito)

#### 6. Deploy
1. Clique em **"Create Web Service"**
2. Aguarde 5-10 minutos enquanto o Render faz o build
3. Seu site estará disponível em: `https://mundodainformatica.onrender.com`

### ⚠️ Observações Importantes
- **Hibernação:** No plano gratuito, o app hiberna após 15 minutos de inatividade
- **Primeira requisição:** Pode demorar 30-60 segundos para "acordar"
- **Banco de dados:** Use o disco persistente para não perder dados

---

## 📦 Opção 2: Railway.app

### Passo a Passo

#### 1. Criar Conta
1. Acesse: https://railway.app
2. Faça login com GitHub

#### 2. Criar Novo Projeto
1. Clique em **"New Project"**
2. Selecione **"Deploy from GitHub repo"**
3. Escolha seu repositório `mundodainformatica`

#### 3. Configurações
Railway detecta automaticamente que é Python e configura sozinho!

#### 4. Adicionar Variáveis
No painel do projeto:
```
SECRET_KEY=valor_aleatorio_seguro
```

#### 5. Deploy
O deploy acontece automaticamente!

### 💰 Custo
- $5 de crédito gratuito por mês
- Aproximadamente 500 horas de execução

---

## 📦 Opção 3: Fly.io

### Passo a Passo

#### 1. Instalar CLI
```bash
curl -L https://fly.io/install.sh | sh
```

#### 2. Login
```bash
fly auth login
```

#### 3. Criar Aplicação
```bash
fly launch
```

#### 4. Deploy
```bash
fly deploy
```

---

## 📦 Opção 4: PythonAnywhere

### Passo a Passo

#### 1. Criar Conta
1. Acesse: https://www.pythonanywhere.com
2. Crie uma conta gratuita

#### 2. Upload do Projeto
1. Use o console bash ou Git para clonar seu repositório
2. Configure um virtualenv

#### 3. Configurar Web App
1. Vá em **"Web"** → **"Add a new web app"**
2. Escolha **"Manual configuration"** → **"Python 3.10"**
3. Configure o WSGI file para apontar para seu `app.py`

#### 4. Reload
Clique em **"Reload"** e seu site estará no ar!

---

## 🎯 Comparação Rápida

| Plataforma      | Facilidade | Performance | Limite Gratuito | Melhor Para |
|-----------------|------------|-------------|-----------------|-------------|
| **Render**      | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 750h/mês        | Iniciantes  |
| **Railway**     | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $5/mês          | Projetos médios |
| **Fly.io**      | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 3 VMs           | Performance |
| **PythonAnywhere** | ⭐⭐⭐ | ⭐⭐⭐ | Limitado        | Python puro |

---

## 🔧 Troubleshooting

### Erro: "Application failed to start"
- Verifique se `gunicorn` está no `requirements.txt` ✅
- Confirme que o arquivo principal se chama `app.py` ✅

### Erro: "Database is locked"
- Configure corretamente o disco persistente
- Ajuste as configurações SQLite no `app.py`

### Site muito lento na primeira visita
- Normal no plano gratuito (hibernação)
- Considere usar um cron job para manter ativo

---

## 📞 Suporte

Se tiver dúvidas:
1. Consulte a documentação oficial de cada plataforma
2. Verifique os logs de deploy
3. Teste localmente primeiro com `gunicorn app:app`

---

**Boa sorte com o deploy! 🚀**
