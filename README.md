# TimeLog developer portal — Mintlify

The TimeLog REST API reference. Twelve Organization endpoints, each as a hand-written page
with the generated playground alongside it.

Mintlify project `6aaaecf674471f0ba1b1489a`.

```
docs.json                          site config, navigation, branding, RBAC tiers
index.mdx                          introduction
api-reference/*.mdx                written pages, one per operation
api-reference/organization.json    the OpenAPI spec the playground is built from
logo/, favicon.svg                 TimeLog brand assets
script.js                          base-URL builder, mounted on the authentication page
```

## Local preview

```bash
npx mint@latest dev
```

> `npx mint broken-links` currently reports ~34 false positives on this repo — every link
> to a page nested two directories deep (`/api-reference/users/list`). All of them serve
> `200` under `mint dev`, and a genuinely missing path correctly serves `404`. Verify
> against the dev server, not the link checker.

---

## The API playground

`docs.json` points `api.openapi` at `api-reference/organization.json`, and each operation
page names its operation in frontmatter:

```yaml
openapi: "GET /v1/user/me"
```

Referenced this way rather than as a navigation group, the spec supplies the try-it surface
*alongside* each page's own prose and warnings, instead of generating twelve competing
pages of its own.

**Requests are proxied** (`api.playground.proxy: true`). The TimeLog API sends no CORS
headers for this origin, so a browser-direct call would fail; Mintlify's proxy is what makes
the playground work at all. Do not turn it off.

### Base URL

TimeLog has no shared host — the base URL is `https://app{instance}.timelog.com/{account}/api`,
per tenant. The spec models `instance` and `account` as OpenAPI server variables, defaulting
to placeholders that deliberately reach nothing.

A reader supplies their own. A **signed-in** reader does not: the JWT handshake injects both
(see below). If you want the demo to work with no login at all, change the two `default`
values in `api-reference/organization.json` to a real demo site.

---

## Access control

Mintlify is **private by default and public by exception** — not the reverse. Pages are
gated unless something says otherwise, in one of two ways:

| Mechanism | Where | Meaning |
| --- | --- | --- |
| `"public": true` | on a navigation group in `docs.json` | everyone, signed in or not |
| `groups: ["partner"]` | in a page's frontmatter | only members of that group |

A page may carry one or the other, never both.

The tiers mirror the `public / partner / internal` model from the Fern POC:

| Tier | Pages |
| --- | --- |
| **public** | Get started, Departments, Legal entities |
| **partner** | Users — reads (`list`, `get-by-id`, `get-current`, `get-current-v2`) |
| **internal** | Users — writes (`create`, `update`, `validate-new-user`), Employee projections |

An unauthorised page returns **404, not 403**. That is Mintlify's design: a gated page does
not confirm it exists.

### Switching it on

The config above is committed and inert until authentication is enabled in the dashboard —
it is a dashboard setting, not a `docs.json` key.

1. **app.mintlify.com → Authentication** — set visibility to Private, method **JWT**.
2. **Generate new key** and store it where the handshake service can read it.
3. Set the **login URL** to the handshake service's `/login`.
4. Redeploy.

Group-based access requires **JWT or OAuth on an Enterprise plan**. Password and
Mintlify-managed auth gate the whole site and ignore `groups:` entirely.

### The handshake service

`C:\Dev\timelog-mintlify-auth` — signs identities and hands them back to the docs site. It
also injects the per-tenant base URL and a token into the playground, so a signed-in partner
never types either. Its README carries the token contract and the failure modes.

---

## Editing

Content can be edited here or through the Mintlify dashboard; both write to this repo.
`docs.json`, the spec and the asset files are repo-only — the Admin MCP cannot write them.

Branding values come from TimeLog's design system
(`Web/src/assets/styles/variables/colors.scss`): `#E84895` (`pink-80`) as primary, with
`#6D0D3C` (`pink-100`) for light-mode link text, because `#E84895` on white is about 3.5:1
and below AA for body text.

## Publishing

Changes deploy automatically on push to the default branch, via the Mintlify GitHub app.
