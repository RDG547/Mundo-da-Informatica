# Guia de Deploy - Mundo da Informática

## 🚀 Deploy no Render.com

### Pré-requisitos
- Conta no GitHub
- Repositório Git configurado
- Conta no Render.com (gratuita ou paga)

### Passos para Deploy

#### 1. Preparar o Repositório

```bash
# Certifique-se de que todas as alterações estão commitadas
git add .
git commit -m "feat: Adicionar controles de download no admin e atualização dinâmica de perfil"
git push origin main
```

#### 2. Configurar no Render.com

1. Acesse [Render.com](https://render.com) e faça login
2. Clique em "New +" → "Web Service"
3. Conecte seu repositório GitHub
4. Configure o serviço:

**Configurações Básicas:**
- **Name:** mundodainformatica
- **Region:** Oregon (US West) ou mais próximo
- **Branch:** main
- **Runtime:** Python 3
- **Build Command:** 
  ```bash
  pip install -r requirements.txt && mkdir -p /opt/render/project/src/data/images/posts /opt/render/project/src/data/images/profiles /opt/render/project/src/data/images/admin /opt/render/project/src/data/uploads/profiles && ln -sfn /opt/render/project/src/data /opt/render/project/src/instance && ln -sfn /opt/render/project/src/data/images /opt/render/project/src/static/images && ln -sfn /opt/render/project/src/data/uploads /opt/render/project/src/static/uploads && python migrate_db.py
  ```
- **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`

**Variáveis de Ambiente:**
- `SECRET_KEY`: (Gerar um valor aleatório seguro)
- `DATABASE_URL`: `sqlite:////opt/render/project/src/data/site.db`
- `PYTHON_VERSION`: `3.11.0`
- `FLASK_ENV`: `production`

**Disco Persistente:**
- **Name:** persistent-data
- **Mount Path:** `/opt/render/project/src/data`
- **Size:** 3 GB (ou mais se necessário)

#### 3. Deploy Automático

O Render detectará automaticamente o arquivo `render.yaml` e configurará o serviço.

Alternativamente, use o método manual acima.

#### 4. Criar Usuário Admin

Após o primeiro deploy, execute via shell do Render:

```bash
python create_admin.py
```

Isso criará um usuário admin padrão:
- **Username:** admin
- **Password:** admin123
- **Email:** admin@mundodainformatica.com

**IMPORTANTE:** Altere a senha imediatamente após o primeiro login!

### 📦 Arquivos de Configuração

#### render.yaml
```yaml
services:
  - type: web
    name: mundodainformatica
    runtime: python
    buildCommand: |
      pip install -r requirements.txt &&
      mkdir -p /opt/render/project/src/data/images/posts /opt/render/project/src/data/images/profiles /opt/render/project/src/data/images/admin /opt/render/project/src/data/uploads/profiles &&
      ln -sfn /opt/render/project/src/data /opt/render/project/src/instance &&
      ln -sfn /opt/render/project/src/data/images /opt/render/project/src/static/images &&
      ln -sfn /opt/render/project/src/data/uploads /opt/render/project/src/static/uploads &&
      python migrate_db.py
    startCommand: gunicorn app:app --bind 0.0.0.0:$PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        value: sqlite:////opt/render/project/src/data/site.db
    disk:
      name: persistent-data
      mountPath: /opt/render/project/src/data
      sizeGB: 3
```

#### Procfile
```
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

#### runtime.txt
```
python-3.11.0
```

### 🔧 Manutenção e Atualizações

#### Deploy de Atualizações
```bash
git add .
git commit -m "Descrição das alterações"
git push origin main
```

O Render fará o deploy automático após cada push para a branch main.

#### Rollback para Versão Anterior
No dashboard do Render:
1. Acesse seu serviço
2. Vá em "Manual Deploy"
3. Selecione um commit anterior
4. Clique em "Deploy"

#### Logs e Monitoramento
- Acesse o dashboard do Render
- Clique em "Logs" para ver os logs em tempo real
- Use "Events" para ver o histórico de deploys

### ⚠️ Troubleshooting

#### Erro de Banco de Dados
```bash
# Via shell do Render
python migrate_db.py
```

#### Limpar Cache
```bash
# Via shell do Render
rm -rf __pycache__
rm -rf instance/*.pyc
```

#### Reinstalar Dependências
```bash
pip install --upgrade -r requirements.txt
```

### 🔐 Segurança

1. **Sempre use HTTPS** (Render fornece SSL grátis)
2. **Altere a SECRET_KEY** regularmente
3. **Mantenha as dependências atualizadas**
4. **Faça backup do banco de dados** regularmente
5. **Configure variáveis de ambiente** para dados sensíveis

### 📊 Monitoramento

- **Health Check:** Render verifica automaticamente se a aplicação está respondendo
- **Uptime:** Monitore no dashboard do Render
- **Performance:** Use as métricas do Render ou integre com ferramentas como New Relic

### 🎯 Novas Funcionalidades Implementadas

#### 1. Controles de Download no Admin
- Resetar contadores de download (diário/semanal)
- Aumentar/diminuir contadores
- Definir valores exatos
- Visualizar limites baseados no plano do usuário

#### 2. Atualização Dinâmica de Perfil
- Edições aparecem imediatamente sem F5
- Atualização de nome, username, bio, localização
- Atualização de links sociais
- Atualização de imagem de perfil em tempo real

### 📝 Checklist Pré-Deploy

- [ ] Todos os testes passaram
- [ ] Dependências atualizadas no requirements.txt
- [ ] Variáveis de ambiente configuradas
- [ ] Banco de dados migrado (migrate_db.py)
- [ ] Arquivos estáticos otimizados
- [ ] Logs de debug removidos/reduzidos
- [ ] SECRET_KEY segura configurada
- [ ] Backup do banco atual (se houver)

### 🌐 URLs Úteis

- **Dashboard Render:** https://dashboard.render.com
- **Documentação Render:** https://render.com/docs
- **Suporte Render:** https://render.com/support

---

## 📞 Suporte

Em caso de problemas durante o deploy:
1. Verifique os logs no dashboard do Render
2. Consulte a documentação oficial
3. Revise as configurações de variáveis de ambiente
4. Certifique-se de que o disco persistente está montado corretamente
