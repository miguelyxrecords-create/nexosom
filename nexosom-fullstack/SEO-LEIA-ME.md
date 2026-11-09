# SEO do NexoSom

A página inicial e os guias de divulgação, Smart Links e colaborações têm título, descrição, endereço canônico e conteúdo disponível no HTML. O sitemap lista essas quatro páginas.

Os Smart Links usam o título e o artista do lançamento quando a API responde. Como os dados da música são carregados por JavaScript, redes que leem só o HTML inicial exibem uma prévia genérica.

## Configuração no Netlify

O projeto fica em `nexosom-fullstack`. Na configuração do Netlify, use essa pasta como **Base directory**, `node scripts/build-netlify.mjs` como **Build command** e `frontend` como **Publish directory**, relativo à pasta base. O build prepara o proxy `/api/*` para a origem configurada em `NEXOSOM_API_ORIGIN`. Consulte `DEPLOY.md` para configurar a API.

## Conferência após o deploy

1. Abra a página inicial, os três guias, `/robots.txt` e `/sitemap.xml`.
2. Confira se um Smart Link existente mostra a música e suas plataformas. Uma URL comum que não existe deve responder com HTTP 404.
3. No Google Search Console da propriedade `https://nexosom.netlify.app/`, envie `sitemap.xml` e use a inspeção de URL para verificar a página inicial e os guias.

Se o site migrar para outro domínio, atualize os endereços em `robots.txt`, `sitemap.xml`, nos metadados HTML e em `setSmartLinkMetadata`.
