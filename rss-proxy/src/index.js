// Hashnode GraphQL API endpoint - bypasses the Vercel Security Checkpoint
const HASHNODE_API = 'https://gql.hashnode.com';

// Your blog's Hashnode host (the subdomain or custom domain)
const BLOG_HOST = 'blog.mornati.net';

const GRAPHQL_QUERY = `
  query GetPosts($host: String!) {
    publication(host: $host) {
      title
      posts(first: 10) {
        edges {
          node {
            title
            brief
            slug
            publishedAt
            url
          }
        }
      }
    }
  }
`;

export default {
    async fetch(request, env, ctx) {
        try {
            // Fetch from Hashnode GraphQL API
            const response = await fetch(HASHNODE_API, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: GRAPHQL_QUERY,
                    variables: { host: BLOG_HOST }
                })
            });

            if (!response.ok) {
                return new Response(`Hashnode API error: ${response.status}`, { status: 500 });
            }

            const data = await response.json();

            if (data.errors) {
                return new Response(`GraphQL Error: ${JSON.stringify(data.errors)}`, { status: 500 });
            }

            const publication = data.data.publication;
            if (!publication) {
                return new Response('Blog not found', { status: 404 });
            }

            // Generate RSS XML from GraphQL response
            const rssXml = generateRSS(publication);

            return new Response(rssXml, {
                headers: {
                    'Content-Type': 'application/rss+xml',
                    'Cache-Control': 'public, max-age=3600',
                    'Access-Control-Allow-Origin': '*',
                }
            });

        } catch (error) {
            return new Response(`Error: ${error.message}`, { status: 500 });
        }
    },
};

function generateRSS(publication) {
    const posts = publication.posts.edges.map(e => e.node);

    const items = posts.map(post => `
    <item>
      <title><![CDATA[${post.title}]]></title>
      <link>${post.url}</link>
      <description><![CDATA[${post.brief || ''}]]></description>
      <pubDate>${new Date(post.publishedAt).toUTCString()}</pubDate>
      <guid>${post.url}</guid>
    </item>
  `).join('');

    return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>${publication.title}</title>
    <link>https://${BLOG_HOST}</link>
    <description>Latest posts from ${publication.title}</description>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    ${items}
  </channel>
</rss>`;
}