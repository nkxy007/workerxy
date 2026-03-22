"""
jira_ticket_manager.py
-----------------------
Multipurpose Jira ticket management module using Atlassian API token auth.

Usage:
    python jira_ticket_manager.py --help

Environment variables (recommended over CLI flags):
    JIRA_BASE_URL   - e.g. https://yourorg.atlassian.net
    JIRA_USER       - your Atlassian account email
    JIRA_API_TOKEN  - API token from https://id.atlassian.com/manage-profile/security/api-tokens
"""

import os
import sys
import json
import argparse
import logging
from typing import Any, Optional

import requests
from requests.auth import HTTPBasicAuth
import creds as jira_creds

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("jira_ticket_manager")


# ---------------------------------------------------------------------------
# JiraClient
# ---------------------------------------------------------------------------
class JiraClient:
    """Thin wrapper around the Jira REST API v3."""

    def __init__(self, base_url: str, user: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.auth = HTTPBasicAuth(user, api_token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}/rest/api/3/{path.lstrip('/')}"

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> Any:
        url = self._url(path)
        log.debug("%s %s  params=%s", method, url, params)

        resp = requests.request(
            method,
            url,
            auth=self.auth,
            headers=self.headers,
            json=payload,
            params=params,
            timeout=30,
        )

        if not resp.ok:
            try:
                detail = resp.json()
            except Exception:
                detail = resp.text
            log.error("HTTP %s: %s", resp.status_code, detail)
            resp.raise_for_status()

        # 204 No Content → return empty dict
        if resp.status_code == 204 or not resp.text:
            return {}

        return resp.json()


    def _search_jql(
        self,
        jql: str,
        max_results: int = 50,
        fields=None,
    ):
        """
        POST to /rest/api/3/search/jql — the current Atlassian endpoint.

        /rest/api/3/search was fully removed (HTTP 410) in 2025.
        The replacement uses POST with a JSON body and nextPageToken
        pagination (startAt is gone).
        """
        default_fields = [
            "key", "summary", "status", "assignee",
            "priority", "created", "updated",
        ]
        resolved_fields = fields if fields else default_fields

        collected = []
        next_page_token = None
        page = 0

        while True:
            batch_size = min(max_results - len(collected), 100)
            payload = {
                "jql": jql,
                "maxResults": batch_size,
                "fields": resolved_fields,
            }
            if next_page_token:
                payload["nextPageToken"] = next_page_token

            log.debug("search/jql page=%d fetching up to %d", page, batch_size)
            data = self._request("POST", "search/jql", payload=payload)

            issues = data.get("issues", [])
            collected.extend(issues)
            page += 1

            next_page_token = data.get("nextPageToken")
            if not next_page_token or len(collected) >= max_results:
                break

        return collected[:max_results]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_ticket(self, issue_key: str) -> dict:
        """
        Fetch a Jira issue by key (e.g. "PROJ-123").
        Returns the raw issue object.
        """
        log.info("Fetching ticket: %s", issue_key)
        return self._request("GET", f"issue/{issue_key}")

    def get_ticket_details(self, issue_key: str) -> dict:
        """
        Fetch a Jira issue with full field expansion and comments.
        Returns a structured summary dict.
        """
        log.info("Fetching full details for ticket: %s", issue_key)
        raw = self._request(
            "GET",
            f"issue/{issue_key}",
            params={"expand": "renderedFields,names,changelog"},
        )

        fields = raw.get("fields", {})

        # Comments
        comments_raw = fields.get("comment", {}).get("comments", [])
        comments = [
            {
                "id": c.get("id"),
                "author": c.get("author", {}).get("displayName"),
                "created": c.get("created"),
                "body": _extract_text(c.get("body", {})),
            }
            for c in comments_raw
        ]

        # Changelog summary
        histories = raw.get("changelog", {}).get("histories", [])
        changelog = [
            {
                "author": h.get("author", {}).get("displayName"),
                "created": h.get("created"),
                "items": h.get("items", []),
            }
            for h in histories
        ]

        return {
            "key": raw.get("key"),
            "summary": fields.get("summary"),
            "status": fields.get("status", {}).get("name"),
            "priority": fields.get("priority", {}).get("name"),
            "issue_type": fields.get("issuetype", {}).get("name"),
            "project": fields.get("project", {}).get("name"),
            "assignee": (fields.get("assignee") or {}).get("displayName"),
            "reporter": (fields.get("reporter") or {}).get("displayName"),
            "created": fields.get("created"),
            "updated": fields.get("updated"),
            "due_date": fields.get("duedate"),
            "labels": fields.get("labels", []),
            "components": [c["name"] for c in fields.get("components", [])],
            "description": _extract_text(fields.get("description") or {}),
            "comments": comments,
            "changelog": changelog,
        }

    def update_ticket(self, issue_key: str, fields: dict) -> dict:
        """
        Update arbitrary fields on a Jira issue.

        `fields` is a plain dict of field_name → value as accepted by the
        Jira REST API.  Common examples:

            {"summary": "New title"}
            {"assignee": {"accountId": "abc123"}}
            {"priority": {"name": "High"}}
            {"labels": ["backend", "urgent"]}
            {"duedate": "2025-12-31"}
        """
        log.info("Updating ticket %s  fields=%s", issue_key, list(fields.keys()))
        payload = {"fields": fields}
        result = self._request("PUT", f"issue/{issue_key}", payload=payload)
        log.info("Ticket %s updated successfully.", issue_key)
        return result

    def add_comment(self, issue_key: str, comment_text: str) -> dict:
        """
        Add a plain-text comment to a Jira issue.
        """
        log.info("Adding comment to ticket: %s", issue_key)
        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": comment_text}],
                    }
                ],
            }
        }
        return self._request("POST", f"issue/{issue_key}/comment", payload=payload)

    def transition_ticket(self, issue_key: str, transition_name: str) -> dict:
        """
        Move a ticket to a new status by transition name (e.g. "In Progress", "Done").
        Performs a lookup of available transitions first.
        """
        log.info("Transitioning ticket %s → '%s'", issue_key, transition_name)
        transitions = self._request("GET", f"issue/{issue_key}/transitions")

        match = None
        for t in transitions.get("transitions", []):
            if t["name"].lower() == transition_name.lower():
                match = t
                break

        if not match:
            available = [t["name"] for t in transitions.get("transitions", [])]
            raise ValueError(
                f"Transition '{transition_name}' not found. "
                f"Available: {available}"
            )

        payload = {"transition": {"id": match["id"]}}
        result = self._request("POST", f"issue/{issue_key}/transitions", payload=payload)
        log.info("Transition applied: %s", match["name"])
        return result

    def search_tickets(
        self,
        jql: str,
        max_results: int = 50,
        fields: Optional[list] = None,
    ) -> list:
        """
        Run a JQL query and return a list of matching issues.
        Uses POST /rest/api/3/search/jql (replaces the removed GET /search).
        """
        log.info("Searching with JQL: %s", jql)
        return self._search_jql(jql, max_results=max_results, fields=fields)

    def get_recent_tickets(
        self,
        project: Optional[str] = None,
        max_results: int = 50,
        status: Optional[str] = None,
        days: int = 30,
    ) -> list:
        """
        Return tickets ordered by most recently created.

        The /rest/api/3/search/jql endpoint requires at least one bounding
        restriction — a bare ORDER BY is rejected with HTTP 400.  When no
        project is supplied we default to `created >= -Nd` so the query is
        always bounded.

        Args:
            project:    Optional project key to scope results (e.g. "PROJ").
            max_results: How many tickets to return.
            status:     Optional status filter (e.g. "In Progress", "To Do").
            days:       How many days back to search when no project is given
                        (default 30).  Ignored when project is supplied.
        """
        clauses = []
        if project:
            clauses.append(f"project = {project}")
        else:
            # Must have at least one bounding clause or the API rejects the query.
            clauses.append(f"created >= -{days}d")
        if status:
            clauses.append(f'status = "{status}"')
        jql = " AND ".join(clauses) + " ORDER BY created DESC"
        log.info("Fetching recent tickets: %s", jql)
        return self.search_tickets(jql, max_results=max_results)

    def get_tickets_by_assignee(
        self,
        assignee: Optional[str] = None,
        project: Optional[str] = None,
        max_results: int = 50,
        status: Optional[str] = None,
        order_by: str = "created",
        order_dir: str = "DESC",
    ) -> list:
        """
        Return tickets assigned to a user, ordered by most recent first.

        Args:
            assignee:   Atlassian display name, accountId, or "currentUser()"
                        (defaults to "currentUser()" when omitted).
            project:    Optional project key filter.
            max_results: How many tickets to return.
            status:     Optional status filter.
            order_by:   Field to sort by — "created" | "updated" | "priority" (default: "created").
            order_dir:  "ASC" or "DESC" (default: "DESC").
        """
        if not assignee or assignee.lower() in ("me", "current", "currentuser"):
            assignee_clause = "assignee = currentUser()"
        else:
            # accountId (long hex string) vs display name
            if len(assignee) > 20 and " " not in assignee:
                assignee_clause = f'assignee = "{assignee}"'
            else:
                assignee_clause = f'assignee in membersOf("{assignee}") OR assignee = "{assignee}"'
                assignee_clause = f'assignee = "{assignee}"'

        clauses = [assignee_clause]
        if project:
            clauses.append(f"project = {project}")
        if status:
            clauses.append(f'status = "{status}"')

        valid_order = {"created", "updated", "priority", "status"}
        ob = order_by if order_by in valid_order else "created"
        od = "DESC" if order_dir.upper() != "ASC" else "ASC"

        jql = " AND ".join(clauses) + f" ORDER BY {ob} {od}"
        log.info("Fetching tickets for assignee: %s", jql)
        return self.search_tickets(jql, max_results=max_results)

    def list_transitions(self, issue_key: str) -> list:
        """
        Return the list of available transitions for an issue.
        """
        result = self._request("GET", f"issue/{issue_key}/transitions")
        return result.get("transitions", [])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_text(node: Any, depth: int = 0) -> str:
    """Recursively pull plain text out of Atlassian Document Format (ADF) nodes."""
    if not node or depth > 20:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        node_type = node.get("type")
        text = node.get("text", "")
        children = node.get("content", [])
        child_text = "".join(_extract_text(c, depth + 1) for c in children)
        sep = "\n" if node_type in ("paragraph", "heading", "listItem", "bulletList", "orderedList") else ""
        return f"{text}{child_text}{sep}"
    if isinstance(node, list):
        return "".join(_extract_text(item, depth + 1) for item in node)
    return ""


def _load_client() -> JiraClient:
    """Build a JiraClient from environment variables."""
    base_url = os.environ.get("JIRA_BASE_URL", jira_creds.JIRA_BASE_URL).strip()
    user = os.environ.get("JIRA_USER", jira_creds.JIRA_USER).strip()
    api_token = os.environ.get("JIRA_API_TOKEN", jira_creds.JIRA_API_TOKEN).strip()

    if not all([base_url, user, api_token]):
        log.error(
            "Missing credentials. Set JIRA_BASE_URL, JIRA_USER, JIRA_API_TOKEN "
            "environment variables."
        )
        sys.exit(1)

    return JiraClient(base_url, user, api_token)


def _pretty(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_issues(issues: list) -> None:
    """Pretty-print a list of issues to stdout."""
    if not issues:
        print("\n  No tickets found.\n")
        return
    print(f"\n  {'KEY':<15} {'CREATED':<22} {'STATUS':<18} {'PRIORITY':<10} {'ASSIGNEE':<22} SUMMARY")
    print(f"  {'-'*110}")
    for issue in issues:
        f = issue.get("fields", {})
        key      = issue.get("key", "-")
        created  = (f.get("created") or "-")[:19].replace("T", " ")
        status   = f.get("status", {}).get("name", "-")
        priority = (f.get("priority") or {}).get("name", "-")
        assignee = (f.get("assignee") or {}).get("displayName", "Unassigned")
        summary  = (f.get("summary") or "")[:55]
        print(f"  {key:<15} {created:<22} {status:<18} {priority:<10} {assignee:<22} {summary}")
    print()


def cmd_get(args: argparse.Namespace) -> None:
    client = _load_client()
    result = client.get_ticket(args.key)
    fields = result.get("fields", {})
    print(f"\n{'='*60}")
    print(f"  {result.get('key')}  —  {fields.get('summary')}")
    print(f"{'='*60}")
    print(f"  Status   : {fields.get('status', {}).get('name')}")
    print(f"  Priority : {(fields.get('priority') or {}).get('name')}")
    print(f"  Assignee : {(fields.get('assignee') or {}).get('displayName', 'Unassigned')}")
    print(f"  Reporter : {(fields.get('reporter') or {}).get('displayName')}")
    print(f"  Created  : {fields.get('created')}")
    print(f"  Updated  : {fields.get('updated')}")
    print()


def cmd_details(args: argparse.Namespace) -> None:
    client = _load_client()
    details = client.get_ticket_details(args.key)
    print(_pretty(details))


def cmd_update(args: argparse.Namespace) -> None:
    client = _load_client()

    fields: dict = {}

    if args.summary:
        fields["summary"] = args.summary

    if args.assignee_id:
        fields["assignee"] = {"accountId": args.assignee_id}

    if args.priority:
        fields["priority"] = {"name": args.priority}

    if args.labels:
        fields["labels"] = [l.strip() for l in args.labels.split(",")]

    if args.due_date:
        fields["duedate"] = args.due_date

    if args.custom_json:
        try:
            extra = json.loads(args.custom_json)
            fields.update(extra)
        except json.JSONDecodeError as exc:
            log.error("Invalid JSON in --custom-json: %s", exc)
            sys.exit(1)

    if not fields:
        log.error("No update fields provided. Use --summary, --priority, etc.")
        sys.exit(1)

    client.update_ticket(args.key, fields)
    print(f"✓ Ticket {args.key} updated.")


def cmd_comment(args: argparse.Namespace) -> None:
    client = _load_client()
    result = client.add_comment(args.key, args.text)
    print(f"✓ Comment added (id={result.get('id')}) to {args.key}.")


def cmd_transition(args: argparse.Namespace) -> None:
    client = _load_client()
    client.transition_ticket(args.key, args.status)
    print(f"✓ Ticket {args.key} transitioned to '{args.status}'.")


def cmd_transitions(args: argparse.Namespace) -> None:
    client = _load_client()
    transitions = client.list_transitions(args.key)
    print(f"\nAvailable transitions for {args.key}:")
    for t in transitions:
        print(f"  [{t['id']}] {t['name']}")
    print()


def cmd_recent(args: argparse.Namespace) -> None:
    client = _load_client()
    issues = client.get_recent_tickets(
        project=args.project,
        max_results=args.limit,
        status=args.status,
        days=args.days,
    )
    scope = f"project {args.project}" if args.project else f"last {args.days} days"
    print(f"\n  Most recent {len(issues)} ticket(s) ({scope})"
          + (f" with status '{args.status}'" if args.status else "")
          + ":")
    _print_issues(issues)


def cmd_assigned(args: argparse.Namespace) -> None:
    client = _load_client()
    assignee = args.assignee or "currentUser()"
    issues = client.get_tickets_by_assignee(
        assignee=assignee,
        project=args.project,
        max_results=args.limit,
        status=args.status,
        order_by=args.order_by,
        order_dir=args.order_dir,
    )
    label = "current user" if assignee in ("currentUser()", "me", "current") else assignee
    print(f"\n  {len(issues)} ticket(s) assigned to {label}"
          + (f" in project {args.project}" if args.project else "")
          + (f" with status '{args.status}'" if args.status else "")
          + ":")
    _print_issues(issues)


def cmd_search(args: argparse.Namespace) -> None:
    client = _load_client()
    issues = client.search_tickets(args.jql, max_results=args.limit)
    print(f"\n  {len(issues)} issue(s) found for JQL: {args.jql}")
    _print_issues(issues)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jira_ticket_manager",
        description="Multipurpose Jira ticket management CLI + importable module.",
        epilog=(
            "Credentials via env vars:\n"
            "  JIRA_BASE_URL   https://yourorg.atlassian.net\n"
            "  JIRA_USER       your@email.com\n"
            "  JIRA_API_TOKEN  your_api_token\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # --- get ---
    p_get = sub.add_parser("get", help="Fetch a ticket (summary view).")
    p_get.add_argument("key", help="Issue key, e.g. PROJ-123")
    p_get.set_defaults(func=cmd_get)

    # --- details ---
    p_det = sub.add_parser("details", help="Fetch full ticket details incl. comments & changelog (JSON).")
    p_det.add_argument("key", help="Issue key, e.g. PROJ-123")
    p_det.set_defaults(func=cmd_details)

    # --- update ---
    p_upd = sub.add_parser("update", help="Update one or more fields on a ticket.")
    p_upd.add_argument("key", help="Issue key, e.g. PROJ-123")
    p_upd.add_argument("--summary", help="New summary/title text.")
    p_upd.add_argument("--assignee-id", help="Atlassian accountId of the new assignee.")
    p_upd.add_argument("--priority", help="Priority name, e.g. High, Medium, Low.")
    p_upd.add_argument("--labels", help="Comma-separated labels, e.g. backend,urgent.")
    p_upd.add_argument("--due-date", help="Due date in YYYY-MM-DD format.")
    p_upd.add_argument(
        "--custom-json",
        help='Raw JSON fields dict, e.g. \'{"story_points": 5}\'.',
    )
    p_upd.set_defaults(func=cmd_update)

    # --- comment ---
    p_com = sub.add_parser("comment", help="Add a comment to a ticket.")
    p_com.add_argument("key", help="Issue key, e.g. PROJ-123")
    p_com.add_argument("text", help="Comment text.")
    p_com.set_defaults(func=cmd_comment)

    # --- transition ---
    p_tr = sub.add_parser("transition", help="Move a ticket to a new status.")
    p_tr.add_argument("key", help="Issue key, e.g. PROJ-123")
    p_tr.add_argument("status", help='Target transition name, e.g. "In Progress" or "Done".')
    p_tr.set_defaults(func=cmd_transition)

    # --- transitions ---
    p_trs = sub.add_parser("transitions", help="List available transitions for a ticket.")
    p_trs.add_argument("key", help="Issue key, e.g. PROJ-123")
    p_trs.set_defaults(func=cmd_transitions)

    # --- recent ---
    p_rec = sub.add_parser("recent", help="List tickets ordered by most recently created.")
    p_rec.add_argument("--project", help="Scope to a project key, e.g. PROJ.")
    p_rec.add_argument("--status", help='Filter by status, e.g. "In Progress".')
    p_rec.add_argument("--days", type=int, default=30,
                       help="How many days back to search when no --project given (default 30).")
    p_rec.add_argument("--limit", type=int, default=50, help="Max results (default 50).")
    p_rec.set_defaults(func=cmd_recent)

    # --- assigned ---
    p_asgn = sub.add_parser("assigned", help="List tickets assigned to a user (default: yourself).")
    p_asgn.add_argument(
        "--assignee",
        default=None,
        help='Display name or accountId. Omit to use currentUser(). Pass "me" explicitly if needed.',
    )
    p_asgn.add_argument("--project", help="Scope to a project key, e.g. PROJ.")
    p_asgn.add_argument("--status", help='Filter by status, e.g. "To Do".')
    p_asgn.add_argument(
        "--order-by",
        default="created",
        choices=["created", "updated", "priority", "status"],
        help="Sort field (default: created).",
    )
    p_asgn.add_argument(
        "--order-dir",
        default="DESC",
        choices=["ASC", "DESC"],
        help="Sort direction (default: DESC = newest first).",
    )
    p_asgn.add_argument("--limit", type=int, default=50, help="Max results (default 50).")
    p_asgn.set_defaults(func=cmd_assigned)

    # --- search ---
    p_src = sub.add_parser("search", help="Search tickets with a JQL query.")
    p_src.add_argument("jql", help='JQL query string, e.g. \'project=PROJ AND status="To Do"\'.')
    p_src.add_argument("--limit", type=int, default=50, help="Max results (default 50).")
    p_src.set_defaults(func=cmd_search)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

