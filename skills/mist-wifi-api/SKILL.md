---
name: mist-wifi-api
description: Interact with the Juniper Mist WiFi cloud API to manage organizations, sites, access points, WLANs, clients, and retrieve stats. Use when the user wants to automate, query, or configure any aspect of a Juniper Mist wireless environment via REST API. Covers authentication setup, endpoint selection by region, and common CRUD operations across org and site scopes.
compatibility: Requires the rest_api_mcp MCP tool to be available. Requires API_AC5_MIST_COM_TOKEN or equivalent region-specific env var to be set. For API calls always check if environment variables are set to know which one to pass in the parameters.

metadata:
  author: xtf
  version: "1.0"
  api-version: "v1"
  reference: https://www.juniper.net/documentation/us/en/software/mist/automation-integration/topics/concept/restful-api-overview.html
---

# Juniper Mist WiFi API Skill

Use this skill to interact with the Juniper Mist cloud REST API via the `rest_api_call` MCP tool.
Mist is 100% API-backed — everything visible in the portal can be automated via API.

## Step 1 — Identify the correct API base_url

Your API base URL depends on which regional cloud your Mist org is hosted on.
Find your region by looking at the portal URL: `manage.{region}.mist.com`.
Replace `manage` with `api` to get your API host.

| Region   | Portal URL                  | API base_url                    |
|----------|-----------------------------|---------------------------------|
| Global 01 | manage.mist.com            | https://api.mist.com            |
| Global 02 | manage.gc1.mist.com        | https://api.gc1.mist.com        |
| Global 03 | manage.ac2.mist.com        | https://api.ac2.mist.com        |
| Global 04 | manage.gc2.mist.com        | https://api.gc2.mist.com        |
| Global 05 | manage.gc4.mist.com        | https://api.gc4.mist.com        |
| EMEA 01   | manage.eu.mist.com         | https://api.eu.mist.com         |
| EMEA 02   | manage.gc3.mist.com        | https://api.gc3.mist.com        |
| EMEA 03   | manage.ac6.mist.com        | https://api.ac6.mist.com        |
| EMEA 04   | manage.gc6.mist.com        | https://api.gc6.mist.com        |
| APAC 01   | manage.ac5.mist.com        | https://api.ac5.mist.com        |
| APAC 02   | manage.gc5.mist.com        | https://api.gc5.mist.com        |
| APAC 03   | manage.gc7.mist.com        | https://api.gc7.mist.com        |

**Important:** The portal subdomain uses `manage`, the API subdomain uses `api`.
Example: user is on `https://manage.ac5.mist.com` → `base_url = "https://api.ac5.mist.com"`

## Step 2 — Authentication

Mist API uses **Bearer Token** authentication. Always use `auth_method: "bearer_token"`.
Basic Auth (username/password) is being deprecated in September 2026 — do not use it.

The env var is derived from the API hostname using the standard prefix convention:

| base_url                    | env var                     |
|-----------------------------|-----------------------------|
| https://api.mist.com        | API_MIST_COM_TOKEN          |
| https://api.ac5.mist.com    | API_AC5_MIST_COM_TOKEN      |
| https://api.eu.mist.com     | API_EU_MIST_COM_TOKEN       |
| https://api.gc1.mist.com    | API_GC1_MIST_COM_TOKEN      |

Set the token before calling:
```bash
export API_AC5_MIST_COM_TOKEN=your_mist_api_token_here
export API_AC5_MIST_COM_ORGID=your_mist_org_id_here
```

To create a token: log into the Mist portal → Organization → API Tokens, or call
`POST /api/v1/self/apitokens` while logged in via browser.

## Step 3 — URL structure

All Mist API endpoints follow this pattern:
```
/api/v1/{scope}/{scope_id}/{object}
```

Scopes: `orgs`, `sites`, `self`, `installer`, `const`, `msp`

Examples:
- `/api/v1/self` — current user info
- `/api/v1/orgs/{org_id}/sites` — list all sites in an org
- `/api/v1/sites/{site_id}/wlans` — list WLANs at a site
- `/api/v1/sites/{site_id}/stats/devices` — device stats at a site
- `/api/v1/orgs/{org_id}/inventory` — org device inventory

## Step 4 — HTTP Methods → CRUD mapping

| HTTP Method | Operation | When to use |
|-------------|-----------|-------------|
| GET         | Read      | Retrieve objects or lists |
| POST        | Create    | Create new objects |
| PUT         | Update    | Modify existing objects (replaces arrays/objects entirely) |
| DELETE      | Remove    | Delete objects |

## Step 5 — Rate limiting

Mist limits to **5,000 API calls per hour** per token.
Prefer org-level calls over site-level loops for large deployments.
The login endpoint `/api/v1/login` is further rate-limited after 3 failures.

---

## Common Call Examples

See [references/common-endpoints.md](references/common-endpoints.md) for ready-to-use
call patterns covering: self/org info, sites, WLANs, APs, clients, and stats.

---

## Tool call template

Always use the `rest_api_call` tool with this structure:

```json
{
  "base_url": "https://api.ac5.mist.com",
  "endpoint": "/api/v1/orgs/{org_id}/sites",
  "method": "GET",
  "auth_method": "bearer_token"
}
```

For POST/PUT include a `body`:
```json
{
  "base_url": "https://api.ac5.mist.com",
  "endpoint": "/api/v1/orgs/{org_id}/sites",
  "method": "POST",
  "auth_method": "bearer_token",
  "body": {
    "name": "New Site",
    "timezone": "Australia/Sydney",
    "country_code": "AU",
    "address": "1 George St, Sydney NSW 2000"
  }
}
```

For paginated results use `query_params`:
```json
{
  "base_url": "https://api.ac5.mist.com",
  "endpoint": "/api/v1/orgs/{org_id}/inventory",
  "method": "GET",
  "auth_method": "bearer_token",
  "query_params": { "page": 1, "limit": 100 }
}
```

---

## Troubleshooting

- **401 Unauthorized** — token is wrong or env var not set. Run `rest_api_inspect_env` to verify.
- **404 Not Found** — wrong org_id or site_id, or wrong regional base_url.
- **429 Too Many Requests** — hit the 5,000/hr rate limit. Wait or switch to org-level calls.
- **Wrong region** — if you get unexpected 404s, confirm you are using `api.` not `manage.` in base_url.