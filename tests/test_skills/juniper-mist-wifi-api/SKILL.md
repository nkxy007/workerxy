---
description: Interact with Juniper Mist WiFi API. Use when managing Mist orgs, sites,
  or APs.
metadata:
  author: xtoftech
  created: '2026-03-10'
  total-updates: 0
name: juniper-mist-wifi-api
---
# juniper-mist-wifi-api — Skill Instructions

Overview
- Use this skill to interact with the Juniper Mist REST API when managing Mist organizations, sites, and access points (devices).
- The instructions below show the common request patterns, required headers, typical endpoints, example requests, and common edge cases to handle.

Prerequisites
- A valid Mist API token with sufficient privileges for the target org(s).
- Base API URL (generally): `https://api.mist.com/api/v1/`
- Know the organization ID (`org_id`) you will operate on (you can list orgs to discover it).
- JSON-capable HTTP client (curl, requests, or HTTP library your agent can call).
- Network connectivity to the Mist API.

Authentication & headers
- Include the API token in every request header:
  - `Authorization: Token <YOUR_API_TOKEN>`
  - `Content-Type: application/json`
- Example headers in an HTTP request: `Authorization: Token abc123def456` and `Content-Type: application/json`

Common endpoints and patterns (canonical forms)
- List orgs
  - GET /orgs
- Sites
  - List sites for org: GET /orgs/{org_id}/sites
  - Create site: POST /orgs/{org_id}/sites
  - Get site by site id: GET /sites/{site_id}
  - Update site: PATCH /sites/{site_id}
  - Delete site: DELETE /sites/{site_id}
- Devices (APs and other devices)
  - List devices for org: GET /orgs/{org_id}/devices
  - Get device by device id: GET /orgs/{org_id}/devices/{device_id} (or GET /orgs/{org_id}/devices?mac=<mac>)
  - Update device: PATCH /orgs/{org_id}/devices/{device_id}
  - Claiming or provisioning devices may require different endpoints (device claim APIs / LEDs / ports) — consult API docs for provisioning-specific flows.
- Query and pagination
  - Many list endpoints support query params like `limit`, `offset` or filter params (e.g., `?site_id=123`, `?mac=aa:bb:cc:dd:ee:ff`).
  - Expect paginated responses; follow `limit` / `offset` or other metadata in the response to fetch additional pages.

Step-by-step common workflows

1) Discover org_id
- Request: GET https://api.mist.com/api/v1/orgs
- Use Authorization header with token.
- Find the org object for the desired organization and read its `id` field.
- Example: response contains `[ { "id": 12345, "name": "Acme Corp", ... } ]` → use `12345` as `org_id`.

2) List sites for an organization
- Request: GET https://api.mist.com/api/v1/orgs/{org_id}/sites?limit=100&offset=0
- Read returned list of site objects. Each site typically contains `id`, `name`, `address`, `timezone`, and other metadata.
- Example usage: list all sites and filter client-side for site name.

3) Create a site
- Request: POST https://api.mist.com/api/v1/orgs/{org_id}/sites
- Body (JSON) example:
  { "name": "sydney-dc1", "address": "1 Example St, Sydney, AU", "timezone": "Australia/Sydney" }
- Response: 201 Created and the full site object (including `id`). Save `site_id`.

4) Get a site by ID
- Request: GET https://api.mist.com/api/v1/sites/{site_id}
- Use this to verify creation or fetch site details.

5) Update a site
- Request: PATCH https://api.mist.com/api/v1/sites/{site_id}
- Body partial update example:
  { "name": "sydney-dc1-renamed", "timezone": "Australia/Sydney" }
- Response: 200 OK with updated site object.

6) Delete a site
- Request: DELETE https://api.mist.com/api/v1/sites/{site_id}
- Response: 204 No Content on success.

7) List devices (APs) in an org or by site
- Request: GET https://api.mist.com/api/v1/orgs/{org_id}/devices?limit=100&offset=0
- Optional filters: many endpoints allow `site_id`, `mac`, `model` etc.
- Response: list of device objects with `id`, `mac`, `ip`, `model`, `serial`, `status`, and `site_id`.

8) Get a device by ID or MAC
- By ID: GET https://api.mist.com/api/v1/orgs/{org_id}/devices/{device_id}
- By MAC: GET https://api.mist.com/api/v1/orgs/{org_id}/devices?mac=aa:bb:cc:dd:ee:ff
- Response: device object.

9) Update device configuration or metadata
- Request: PATCH https://api.mist.com/api/v1/orgs/{org_id}/devices/{device_id}
- Body example to change name/notes:
  { "name": "ap-sydney-01", "notes": "Replaced radio 5GHz antenna" }
- Response: 200 OK with updated device object.
- For operational commands (reboot, blink LED, claim/unclaim), use the specific endpoints defined by Mist (check API docs for device management actions).

10) Create or claim devices (provisioning)
- Provisioning often uses dedicated claim endpoints and may require device serial/claim codes.
- Example pattern: POST https://api.mist.com/api/v1/orgs/{org_id}/devices/claim with relevant payload; exact fields depend on Mist API version.
- If device creation is unsupported via public API for your org, follow the Mist provisioning/claim process in the official docs.

Error handling and common status codes
- 200 OK — GET or PATCH successful, returns object(s).
- 201 Created — resource created (POST).
- 204 No Content — successful DELETE.
- 400 Bad Request — invalid payload or missing required fields. Inspect response body for validation errors.
- 401 / 403 Unauthorized or Forbidden — invalid token or insufficient permissions. Verify token and org access.
- 404 Not Found — resource (org/site/device) not found. Verify IDs are correct and belong to the org.
- 409 Conflict — resource conflict (e.g., duplicate name or already-claimed device).
- 429 Too Many Requests — rate limit exceeded. Retry after waiting (honor Retry-After header if provided).
- 5xx — server errors; retry with backoff.

Common edge cases and how to handle them
- Missing or invalid token
  - Verify `Authorization: Token <token>` header is present.
  - If 401/403, ensure token has access to the target org.
- Wrong org_id
  - Always confirm `org_id` by listing orgs before acting. A site or device ID returned for a different org will cause 404 or permission errors.
- Pagination
  - List endpoints are usually paginated. Use `limit` and `offset` (or provided meta/next links) to fetch all results.
- Partial updates
  - Use PATCH for partial updates; do not send the entire object unless necessary.
- Rate limiting
  - Respect `Retry-After` header on 429 responses and implement exponential backoff.
- Resource dependencies
  - Some operations require pre-existing resources (e.g., device can’t be assigned to a nonexistent site). Validate referenced IDs exist before changing associations.
- Device claim / provisioning complexity
  - Claiming devices may require serial numbers or claim codes and may be bound to inventory or partner accounts. If encountering errors, verify device eligibility and org claim policies.
- Validation errors on create
  - For POST requests returning 400, parse the response body for specific field errors and surface them to the user; ensure required fields (name, timezone, site_id where applicable) are present and valid.
- Concurrency and idempotency
  - Avoid duplicate creates by checking if a resource with the same unique field already exists (e.g., site name). For critical operations, implement idempotency keys if the API supports them or perform existence checks before POSTing.
- Field differences across API versions
  - Field names and endpoints sometimes change. If encountering unknown fields or endpoints, check current Mist API docs for your account’s API version.

Concrete examples (requests & payloads)
- List orgs
  - GET https://api.mist.com/api/v1/orgs
  - Headers: Authorization: Token <TOKEN>
- Create a site (example payload)
  - POST https://api.mist.com/api/v1/orgs/12345/sites
  - Body:
    { "name": "sydney-dc1", "address": "1 Example St, Sydney, AU", "timezone": "Australia/Sydney" }
  - Expect: 201 Created with site object including `id`.
- List devices in a site
  - GET https://api.mist.com/api/v1/orgs/12345/devices?site_id=67890&limit=100
- Update a device name
  - PATCH https://api.mist.com/api/v1/orgs/12345/devices/98765
  - Body:
    { "name": "ap-sydney-01" }
  - Expect: 200 OK with updated device object.

Best practices for an agent using this skill
- Always include the Authorization header and validate token scope first.
- Discover `org_id` programmatically via GET /orgs instead of hardcoding.
- Confirm existence of referenced IDs (site_id, device_id) before making modifications.
- Implement pagination handling to enumerate lists.
- Use PATCH for safe partial updates.
- Handle rate limits and transient server errors with retries and exponential backoff.
- Log request and response IDs for traceability; surface API error messages to operators.
- For destructive actions (DELETE, unclaim), require an explicit confirmation step or idempotent check before proceeding.

References
- Use the official Juniper Mist API documentation for any endpoint not covered here, and to confirm current endpoint paths, request/response fields, and provisioning flows for devices.