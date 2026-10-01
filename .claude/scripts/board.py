#!/usr/bin/env python3
"""Keep work/backlog.md in sync with the GitHub project board.

The board is the source of truth for tickets and their status; backlog.md is
a local mirror that factory-manager reads. New ideas typed into backlog.md as
plain "- [ ] <description>" lines are turned into issues on the board.

Usage (from the repo root):
  board.py sync                          pull the board into backlog.md, push new lines
  board.py next                          print the first Todo ticket as JSON ({} if none)
  board.py status <issue> <Todo|In Progress|Done>
  board.py add <title> --id <ticket-id> [--body <text>] [--label <name>]...
  board.py setup                         check that the configured board is reachable

Configuration (GH_OWNER, GH_REPO, GH_PROJECT_NUMBER) comes from
.claude/hooks/config.sh. Stdlib only; needs an authenticated gh CLI.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

CONFIG = Path(".claude/hooks/config.sh")
BACKLOG = Path("work/backlog.md")
STATUSES = ("Todo", "In Progress", "Done")
MARKERS = {"Todo": " ", "In Progress": "~", "Done": "x"}

HEADER = """# Ticket backlog

Local mirror of the GitHub project board, maintained by `factory-manager` via
`python3 .claude/scripts/board.py sync`. Board order = priority order.
`[ ]` Todo, `[~]` In Progress, `[x]` Done.

To add an idea, append a plain `- [ ] <description>` line (optionally
`- [ ] <ticket-id>: <description>`); the next sync creates the issue and puts it
on the board. Change order and status on the board, not here.
"""

ID_LINE = re.compile(r"^Ticket id:\s*`([a-z0-9-]+)`", re.MULTILINE)
TRACKED_LINE = re.compile(r"^- \[[ ~x]\] #(\d+) ")
PARKED = re.compile(r"\[\[parked: [^\]]+\]\]")
NEW_LINE = re.compile(r"^- \[ \] (?!#\d)(?:([a-z0-9-]+): )?(.+)$")


def config():
    values = {}
    for line in CONFIG.read_text().splitlines():
        m = re.match(r'^(GH_\w+)="(.*)"', line)
        if m:
            values[m.group(1)] = m.group(2)
    if not values.get("GH_PROJECT_NUMBER"):
        sys.exit("GH_PROJECT_NUMBER is not set in .claude/hooks/config.sh")
    return values


def gh(*args):
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        sys.exit(f"gh {' '.join(args[:2])} failed: {result.stderr.strip()}")
    return result.stdout


QUERY = """
query($owner: String!, $number: Int!, $cursor: String) {
  user(login: $owner) {
    projectV2(number: $number) {
      id
      field(name: "Status") {
        ... on ProjectV2SingleSelectField { id options { id name } }
      }
      items(first: 100, after: $cursor, orderBy: {field: POSITION, direction: ASC}) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          status: fieldValueByName(name: "Status") {
            ... on ProjectV2ItemFieldSingleSelectValue { name }
          }
          content {
            ... on Issue {
              number title body url
              repository { nameWithOwner }
              labels(first: 20) { nodes { name } }
            }
          }
        }
      }
    }
  }
}
"""


def load_board(cfg):
    items, cursor, project = [], None, None
    while True:
        args = [
            "api",
            "graphql",
            "-f",
            f"query={QUERY}",
            "-F",
            f"owner={cfg['GH_OWNER']}",
            "-F",
            f"number={cfg['GH_PROJECT_NUMBER']}",
        ]
        if cursor:
            args += ["-f", f"cursor={cursor}"]
        project = json.loads(gh(*args))["data"]["user"]["projectV2"]
        page = project["items"]
        for node in page["nodes"]:
            issue = node["content"]
            if (
                not issue
                or issue.get("repository", {}).get("nameWithOwner") != cfg["GH_REPO"]
            ):
                continue
            match = ID_LINE.search(issue["body"] or "")
            items.append(
                {
                    "item_id": node["id"],
                    "number": issue["number"],
                    "id": match.group(1) if match else slugify(issue["title"]),
                    "title": issue["title"],
                    "body": issue["body"],
                    "url": issue["url"],
                    "labels": [label["name"] for label in issue["labels"]["nodes"]],
                    "status": (node["status"] or {}).get("name") or "Todo",
                }
            )
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return project, items


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return "-".join(slug.split("-")[:5])


def set_status(cfg, project, item_id, status):
    option = next(
        (o["id"] for o in project["field"]["options"] if o["name"] == status), None
    )
    if option is None:
        sys.exit(f"Board has no Status option '{status}'")
    gh(
        "project",
        "item-edit",
        "--id",
        item_id,
        "--project-id",
        project["id"],
        "--field-id",
        project["field"]["id"],
        "--single-select-option-id",
        option,
    )


def create_ticket(cfg, project, title, ticket_id, body="", labels=()):
    full_body = f"Ticket id: `{ticket_id}`\n\n{body}".rstrip() + "\n"
    args = [
        "issue",
        "create",
        "-R",
        cfg["GH_REPO"],
        "--title",
        title,
        "--body",
        full_body,
    ]
    for label in labels:
        args += ["--label", label]
    url = gh(*args).strip().splitlines()[-1]
    item = json.loads(
        gh(
            "project",
            "item-add",
            cfg["GH_PROJECT_NUMBER"],
            "--owner",
            cfg["GH_OWNER"],
            "--url",
            url,
            "--format",
            "json",
        )
    )
    set_status(cfg, project, item["id"], "Todo")
    return url


def read_backlog():
    parked, new = {}, []
    if not BACKLOG.exists():
        return parked, new
    for line in BACKLOG.read_text().splitlines():
        tracked = TRACKED_LINE.match(line)
        if tracked:
            tag = PARKED.search(line)
            if tag:
                parked[int(tracked.group(1))] = tag.group(0)
            continue
        fresh = NEW_LINE.match(line)
        if fresh:
            new.append((fresh.group(1), fresh.group(2).strip()))
    return parked, new


def write_backlog(items, parked):
    lines = [HEADER]
    for item in items:
        line = f"- [{MARKERS.get(item['status'], ' ')}] #{item['number']} {item['id']}: {item['title']}"
        if item["status"] == "Done":
            line += f" — work/{item['id']}/review.md"
        if item["number"] in parked and item["status"] != "Done":
            line += f" {parked[item['number']]}"
        lines.append(line)
    BACKLOG.parent.mkdir(parents=True, exist_ok=True)
    BACKLOG.write_text("\n".join(lines) + "\n")


def cmd_sync(cfg, _args):
    parked, new = read_backlog()
    project, items = load_board(cfg)
    for ticket_id, description in new:
        url = create_ticket(
            cfg, project, description, ticket_id or slugify(description)
        )
        print(f"created {url}")
    if new:
        project, items = load_board(cfg)
    for item in items:
        if item["status"] not in STATUSES:
            print(f"warning: #{item['number']} has unknown status '{item['status']}'")
    write_backlog(items, parked)
    counts = {s: sum(1 for i in items if i["status"] == s) for s in STATUSES}
    print(f"synced {BACKLOG}: " + ", ".join(f"{n} {s}" for s, n in counts.items()))


def cmd_next(cfg, _args):
    _, items = load_board(cfg)
    todo = next((i for i in items if i["status"] == "Todo"), None)
    print(
        json.dumps(
            {k: v for k, v in todo.items() if k != "item_id"} if todo else {}, indent=2
        )
    )


def cmd_status(cfg, args):
    if args.status not in STATUSES:
        sys.exit(f"status must be one of {', '.join(STATUSES)}")
    project, items = load_board(cfg)
    item = next((i for i in items if i["number"] == args.issue), None)
    if item is None:
        sys.exit(f"#{args.issue} is not on the board")
    set_status(cfg, project, item["item_id"], args.status)
    print(f"#{args.issue} -> {args.status}")
    cmd_sync(cfg, args)


def cmd_add(cfg, args):
    project, _ = load_board(cfg)
    print(create_ticket(cfg, project, args.title, args.id, args.body, args.label))


def cmd_setup(cfg, _args):
    project, items = load_board(cfg)
    options = [o["name"] for o in project["field"]["options"]]
    missing = [s for s in STATUSES if s not in options]
    if missing:
        sys.exit(f"Board Status field is missing options: {', '.join(missing)}")
    print(f"board OK: {len(items)} tickets from {cfg['GH_REPO']}, statuses {options}")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sync")
    sub.add_parser("next")
    sub.add_parser("setup")
    status = sub.add_parser("status")
    status.add_argument("issue", type=int)
    status.add_argument("status")
    add = sub.add_parser("add")
    add.add_argument("title")
    add.add_argument("--id", required=True)
    add.add_argument("--body", default="")
    add.add_argument("--label", action="append", default=[])
    args = parser.parse_args()
    cfg = config()
    {
        "sync": cmd_sync,
        "next": cmd_next,
        "status": cmd_status,
        "add": cmd_add,
        "setup": cmd_setup,
    }[args.command](cfg, args)


if __name__ == "__main__":
    main()
