# Connecting Claude to this site's MCP server

The site runs the **MCP Adapter** with the **Abilities API** — the current
WordPress path, not the archived `wordpress-mcp` plugin. Two endpoints exist
and both are live:

    POST/GET/DELETE  /wp-json/mcp/mcp-adapter-default-server
    GET              /wp-json/wp-abilities/v1/abilities

## Why there is no OAuth connector

MCP Adapter authenticates with WordPress **application passwords over HTTP
Basic**. It issues no OAuth challenge:

    $ curl -i -X POST .../wp-json/mcp/mcp-adapter-default-server -d '{...}'
    HTTP/2 401
    {"code":"rest_forbidden","message":"Sorry, you are not allowed to do that."}

with no `WWW-Authenticate` header, and all three discovery documents absent:

    /.well-known/oauth-protected-resource     404
    /.well-known/oauth-authorization-server   404
    /.well-known/mcp                          404

claude.ai custom connectors authenticate over OAuth only, so this server
cannot be added there. That is a property of the architecture, not a
misconfiguration — and this architecture is the right one. Do not install
`wordpress-mcp.zip` to get an OAuth endpoint; that implementation is archived.

Claude Code does not need OAuth. It can send the Basic credential itself,
which is what `.mcp.json` in this repository does.

## Setup

1. **Make a dedicated WordPress user for it.** Not your admin account. Give it
   the least role that can do what you want Claude to do — Editor is usually
   enough for content work, and the abilities the adapter exposes are filtered
   by that user's capabilities. This is the whole point of a separate user:
   the blast radius of a leaked credential is that role, nothing more.

2. **Generate an application password** for that user: Users -> Profile ->
   Application Passwords. WordPress shows it once, in `xxxx xxxx xxxx xxxx
   xxxx xxxx` form.

3. **Build the Basic credential.** It is base64 of `username:password`,
   spaces in the password included:

       printf '%s' 'mcp-bot:xxxx xxxx xxxx xxxx xxxx xxxx' | base64 -w0

4. **Put it in the environment** as `WP_MCP_BASIC`. Never in this file, never
   in a commit — `.mcp.json` references the variable, it does not contain the
   value.

5. Start a Claude Code session in this repository. It reads `.mcp.json`,
   expands `${WP_MCP_BASIC}`, and the server's tools load.

## Checking it works

    curl -s -X POST https://www.avoltium.in/wp-json/mcp/mcp-adapter-default-server \
      -H "Authorization: Basic $WP_MCP_BASIC" \
      -H "Content-Type: application/json" \
      -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

A tool list means it is working. A `rest_forbidden` 401 means the credential
is wrong or the user lacks the capability. The adapter also ships a self test
at `/wp-json/mwai/v1/mcp/self_test`, and the abilities the server is exposing
can be listed at `/wp-json/wp-abilities/v1/abilities`.

## Abilities

The adapter exposes whatever abilities are registered, so a small set of
purpose-built ones beats handing over a generic write-anything tool. Register
them with `wp_register_ability()` against the capability the dedicated user
actually holds.

## Note on the separate deploy path

`deploy_readability_css.py` does not use any of this. It talks to the Code
Snippets REST API with `WP_USERNAME` / `WP_APP_PASSWORD`, which are the
GitHub Actions secrets. Those stay as they are; MCP is for interactive work,
not for shipping the stylesheet.
