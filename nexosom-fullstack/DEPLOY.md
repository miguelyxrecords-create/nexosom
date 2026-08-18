# Deploy do NexoSom

## 1. GitHub

Envie esta pasta para um repositório privado.

Antes do push, confira:

```powershell
git status
```

`backend/.env` NÃO deve aparecer. Este pacote já vem sem o arquivo real `.env`.

## 2. Backend no Render

O projeto já contém `render.yaml`.

No Render, conecte o repositório privado e use o Blueprint/configuração do repositório.

O Render pedirá os valores marcados como secretos:

- `MONGODB_URI`
- `ADMIN_EMAIL`

O `JWT_SECRET` é gerado automaticamente pelo próprio Render.

As demais variáveis já estão descritas no `render.yaml`.

Depois do deploy, copie a URL pública do backend, por exemplo:

```text
https://nexosom-api.onrender.com
```

Teste no navegador:

```text
https://SEU-BACKEND.onrender.com/api/health
```

Resultado esperado:

```json
{"ok":true}
```

## 3. MongoDB Atlas

O Render precisa conseguir acessar o MongoDB Atlas.

Se o deploy falhar na inicialização por conexão com MongoDB, ajuste a IP Access List do Atlas para permitir os IPs de saída do seu serviço Render ou a configuração de rede que você estiver usando.

## 4. Frontend no Netlify

Conecte o MESMO repositório privado ao Netlify.

O `netlify.toml` já define:

- pasta publicada: `frontend`
- comando de build
- rotas SPA/Smart Link
- cabeçalhos de segurança

No Netlify, adicione uma variável de ambiente:

```text
NEXOSOM_API_ORIGIN=https://SEU-BACKEND.onrender.com
```

Use a URL real que o Render criou, SEM `/api` no final.

Opcionalmente, se algum dia trocar o Google Client ID, adicione:

```text
NEXOSOM_GOOGLE_CLIENT_ID=SEU_CLIENT_ID.apps.googleusercontent.com
```

Durante o build, o script gera automaticamente:

- `API_URL: "/api"`
- proxy `/api/*` do Netlify para o Render
- fallback `/s/*` para o Smart Link

Isso mantém o frontend usando a mesma origem e evita depender de CORS entre Netlify e Render em produção.

## 5. Google Cloud

Depois que o Netlify gerar a URL do site, adicione em **Authorized JavaScript origins** do seu cliente OAuth Web:

```text
https://SEU-SITE.netlify.app
```

Mantenha também o ambiente local:

```text
http://localhost:5500
```

Se usar domínio próprio, adicione também o domínio HTTPS dele.

## 6. Teste final

Teste nesta ordem:

1. página inicial abre
2. login Google funciona
3. conta comum não vê Admin
4. conta admin vê Admin
5. publicar música funciona
6. capa abre normalmente
7. Smart Link `/s/...` abre ao atualizar a página
8. Spotify/YouTube/Deezer/Apple Music abrem
9. curtida funciona após login
10. sair da conta funciona

## Observação sobre plano do Render

Para teste inicial você pode usar a opção disponível no seu painel. Para tráfego real e disponibilidade contínua, escolha uma instância adequada ao uso do site.
