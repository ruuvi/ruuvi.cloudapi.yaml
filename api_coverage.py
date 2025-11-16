import argparse
import json
import yaml
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
import html


class StatusIgnore:
    def __init__(self, patterns):
        self.codes = set()
        self.prefixes = set()
        for token in patterns:
            token = str(token).strip()
            if not token:
                continue
            # Allow comma-separated lists
            if "," in token or " " in token:
                for part in token.replace(",", " ").split():
                    self._add_token(part)
            else:
                self._add_token(token)

    def _add_token(self, token: str):
        try:
            self.codes.add(int(token))
            return
        except ValueError:
            pass
        # Pattern like 5XX, 4XX, etc.
        if len(token) == 3 and token[0].isdigit() and token[1:] == "XX":
            self.prefixes.add(token[0])
        else:
            # Unknown formats are ignored silently
            pass

    def is_ignored(self, status: int) -> bool:
        if status in self.codes:
            return True
        s = str(status)
        if len(s) == 3 and s[0] in self.prefixes:
            return True
        return False


def load_openapi(path: Path):
    with path.open() as f:
        spec = yaml.safe_load(f)

    documented = defaultdict(set)  # (method, path) -> {int status}
    for raw_path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, op in path_item.items():
            method_up = method.upper()
            if method_up not in {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}:
                continue
            responses = op.get("responses", {}) or {}
            for status in responses.keys():
                if status.isdigit():
                    documented[(method_up, raw_path)].add(int(status))
    return documented


def extract_path_from_url(url: str) -> str:
    """
    Very crude URL -> path extractor.
    https://testnet.ruuvi.com/sensor-settings?sensor=... -> /sensor-settings
    """
    no_scheme = url.split("://", 1)[-1]
    # remove host
    after_host = no_scheme.split("/", 1)[-1]
    path = "/" + after_host.split("?", 1)[0]
    return path


def load_har(path: Path):
    with path.open() as f:
        har = json.load(f)

    # Maps
    seen_statuses = defaultdict(set)  # (method, path) -> {status}
    case_to_triplet = {}             # testCaseId -> (method, path, status)

    for entry in har["log"]["entries"]:
        req = entry["request"]
        res = entry["response"]

        method = req["method"].upper()
        url = req["url"]
        path_str = extract_path_from_url(url)
        status = res["status"]

        # Find X-Schemathesis-TestCaseId header if present
        test_case_id = None
        for h in req.get("headers", []):
            if h.get("name").lower() == "x-schemathesis-testcaseid".lower():
                test_case_id = h.get("value")
                break

        seen_statuses[(method, path_str)].add(status)
        if test_case_id:
            case_to_triplet[test_case_id] = (method, path_str, status)

    return seen_statuses, case_to_triplet


def load_failing_test_ids(junit_path: Path):
    tree = ET.parse(junit_path)
    root = tree.getroot()
    failing_ids = set()

    # All <failure> elements carry "message" attribute with "Test Case ID: XYZ"
    for failure in root.iter("failure"):
        msg = failure.get("message") or ""
        for line in msg.splitlines():
            line = line.strip()
            if line.startswith("1. Test Case ID:") or line.startswith("2. Test Case ID:"):
                # Lines look like: "1. Test Case ID: 7dQuzM"
                parts = line.split("Test Case ID:", 1)
                if len(parts) == 2:
                    case_id = parts[1].strip()
                    if case_id:
                        failing_ids.add(case_id)
            elif line.startswith("Test Case ID:"):
                # fallback in case format changes
                parts = line.split("Test Case ID:", 1)
                if len(parts) == 2:
                    case_id = parts[1].strip()
                    if case_id:
                        failing_ids.add(case_id)
    return failing_ids


def classify_endpoint(
    method,
    path,
    documented_codes,
    seen,
    passing,
    failing,
    ignore: StatusIgnore,
):
    documented_codes = set(documented_codes)
    nonignored_docs = {c for c in documented_codes if not ignore.is_ignored(c)}
    ignored_docs = documented_codes - nonignored_docs

    extra_statuses = seen - documented_codes

    covered_passing = set()
    covered_failing = set()
    untested = set()

    # Only non-ignored documented codes are counted for coverage
    for code in nonignored_docs:
        if code in failing:
            covered_failing.add(code)
        elif code in passing:
            covered_passing.add(code)
        else:
            untested.add(code)

    ignored_passing = {c for c in ignored_docs if c in passing and c not in failing}
    ignored_failing = {c for c in ignored_docs if c in failing}

    # Extra statuses are always treated as failures (ignored or not)
    extra_ignored = {c for c in extra_statuses if ignore.is_ignored(c)}
    extra_nonignored = extra_statuses - extra_ignored

    has_any_coverage = bool(
        covered_passing
        or covered_failing
        or ignored_passing
        or ignored_failing
        or extra_statuses
    )
    has_any_passing = bool(covered_passing or ignored_passing)
    has_any_failing = bool(covered_failing or ignored_failing or extra_statuses)

    # Color logic:
    #   green  = every non-ignored documented status covered & passing, and no failures anywhere
    #   yellow = some covered & passing, or partial coverage, or mix of pass+fail
    #   red    = some covered but none pass (only failures / extra failures)
    #   grey   = nothing covered at all
    if not has_any_coverage:
        color = "grey"
    else:
        if has_any_failing:
            if has_any_passing:
                color = "yellow"
            else:
                color = "red"
        else:
            # some coverage, no failing
            if len(covered_passing) == len(nonignored_docs):
                color = "green"
            else:
                color = "yellow"

    return {
        "method": method,
        "path": path,
        "documented": documented_codes,
        "nonignored_docs": nonignored_docs,
        "ignored_docs": ignored_docs,
        "seen": seen,
        "passing": passing,
        "failing": failing,
        "covered_passing": covered_passing,
        "covered_failing": covered_failing,
        "untested": untested,
        "ignored_passing": ignored_passing,
        "ignored_failing": ignored_failing,
        "extra_nonignored": extra_nonignored,
        "extra_ignored": extra_ignored,
        "color": color,
    }


def render_html(out_path: Path, endpoint_reports, summary, ignore_patterns):
    css = """
    body { font-family: sans-serif; margin: 1em; }
    h1 { font-size: 1.4em; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 1em; }
    th, td { border: 1px solid #ccc; padding: 4px 8px; font-size: 0.9em; }
    .endpoint-header.green { background-color: #c8e6c9; }
    .endpoint-header.yellow { background-color: #fff9c4; }
    .endpoint-header.red { background-color: #ffcdd2; }
    .endpoint-header.grey { background-color: #eeeeee; }
    .endpoint-header th { text-align: left; }
    .badge { display: inline-block; width: 0.8em; height: 0.8em; margin-right: 0.5em; border-radius: 0.2em; }
    .badge.green { background-color: #4caf50; }
    .badge.yellow { background-color: #ffeb3b; }
    .badge.red { background-color: #f44336; }
    .badge.grey { background-color: #9e9e9e; }
    details { margin-bottom: 0.8em; }
    summary { cursor: pointer; font-weight: bold; margin-bottom: 0.2em; }
    .muted { color: #666; font-size: 0.85em; }
    """
    with out_path.open("w", encoding="utf-8") as f:
        f.write("<!doctype html><html><head><meta charset='utf-8'>")
        f.write("<title>API coverage report</title>")
        f.write("<style>")
        f.write(css)
        f.write("</style></head><body>")
        f.write("<h1>API coverage report</h1>")

        # Summary
        total_doc = summary["total_doc"]
        total_pass = summary["total_pass"]
        total_fail = summary["total_fail"]
        total_untested = summary["total_untested"]
        extra_total = summary["extra_total"]

        def pct(x):
            return f"{(x * 100.0 / total_doc):.1f}%" if total_doc else "-"

        f.write("<h2>Summary</h2>")
        f.write("<table>")
        f.write("<tr><th>Metric</th><th>Count</th><th>Percent of documented (non-ignored)</th></tr>")
        f.write(f"<tr><td>Documented statuses (non-ignored)</td><td>{total_doc}</td><td>-</td></tr>")
        f.write(f"<tr><td>Covered &amp; passing</td><td>{total_pass}</td><td>{pct(total_pass)}</td></tr>")
        f.write(f"<tr><td>Covered &amp; failing</td><td>{total_fail}</td><td>{pct(total_fail)}</td></tr>")
        f.write(f"<tr><td>Untested</td><td>{total_untested}</td><td>{pct(total_untested)}</td></tr>")
        f.write(f"<tr><td>Seen but undocumented statuses (always treated as failures)</td><td>{extra_total}</td><td>-</td></tr>")
        f.write("</table>")
        f.write("<p class='muted'>Ignored for coverage (but still reported if seen failing): ")
        f.write(", ".join(html.escape(p) for p in ignore_patterns) if ignore_patterns else "none")
        f.write("</p>")

        # Per-endpoint details
        f.write("<h2>Endpoints</h2>")
        for ep in endpoint_reports:
            method = html.escape(ep["method"])
            path = html.escape(ep["path"])
            color = ep["color"]
            f.write("<details>")
            f.write("<summary>")
            f.write(f"<span class='badge {color}'></span>")
            f.write(f"{method} {path}</summary>")
            f.write("<table>")
            f.write(f"<tr class='endpoint-header {color}'><th colspan='2'>{method} {path}</th></tr>")

            def row(label, values):
                if not values:
                    val_str = "-"
                else:
                    val_str = ", ".join(str(v) for v in sorted(values))
                f.write(f"<tr><td>{html.escape(label)}</td><td>{html.escape(val_str)}</td></tr>")

            row("Documented", ep["documented"])
            row("Documented (non-ignored)", ep["nonignored_docs"])
            row("Seen (any)", ep["seen"])
            row("Covered & passing", ep["covered_passing"])
            row("Covered & failing", ep["covered_failing"])
            row("Untested (non-ignored documented)", ep["untested"])
            row("Ignored documented statuses", ep["ignored_docs"])
            row("Ignored & failing", ep["ignored_failing"])
            row("Undocumented but seen (treated as failures)", ep["extra_nonignored"] | ep["extra_ignored"])

            f.write("</table>")
            f.write("</details>")

        f.write("</body></html>")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--openapi", required=True, help="Path to bundled OpenAPI YAML")
    parser.add_argument("--har", required=True, help="Path to Schemathesis HAR JSON")
    parser.add_argument("--junit", required=True, help="Path to Schemathesis JUnit XML")
    parser.add_argument(
        "--out",
        help="Path to write HTML coverage report",
    )
    parser.add_argument(
        "--ignore-status",
        action="append",
        help=(
            "Status codes or patterns to ignore for coverage, e.g. 429 or 5XX. "
            "May be given multiple times or as comma-separated lists. "
            "Defaults to 429 and 5XX if not provided."
        ),
    )
    args = parser.parse_args()

    if args.ignore_status is None:
        ignore_patterns = ["429", "5XX"]
    else:
        # Flatten provided patterns
        ignore_patterns = []
        for item in args.ignore_status:
            if item is None:
                continue
            for part in str(item).replace(",", " ").split():
                if part:
                    ignore_patterns.append(part)

    ignore = StatusIgnore(ignore_patterns)

    openapi_path = Path(args.openapi)
    har_path = Path(args.har)
    junit_path = Path(args.junit)
    out_path = Path(args.out) if args.out else None

    documented = load_openapi(openapi_path)
    seen_statuses, case_to_triplet = load_har(har_path)
    failing_ids = load_failing_test_ids(junit_path)

    # Determine which (method, path, status) have failing test cases
    failing_statuses = defaultdict(set)   # (method, path) -> {status}
    passing_statuses = defaultdict(set)   # (method, path) -> {status}

    for case_id, (method, path, status) in case_to_triplet.items():
        if case_id in failing_ids:
            failing_statuses[(method, path)].add(status)
        else:
            passing_statuses[(method, path)].add(status)

    # For statuses seen in HAR but with no testcase id (no fuzz ID), treat as passing
    for (method, path), statuses in seen_statuses.items():
        for status in statuses:
            # If already marked failing, keep it failing
            if status in failing_statuses[(method, path)]:
                continue
            # If we have at least one known passing test case for this triplet, it's passing
            if status in passing_statuses[(method, path)]:
                continue
            # No testcase id at all -> assume passing
            passing_statuses[(method, path)].add(status)

    endpoint_reports = []
    total_doc = 0
    total_pass = 0
    total_fail = 0
    total_untested = 0
    extra_total = 0

    # Produce coverage report (text) and collect for HTML
    for (method, path), documented_codes in sorted(documented.items()):
        seen = seen_statuses.get((method, path), set())
        failing = failing_statuses.get((method, path), set())
        passing = passing_statuses.get((method, path), set())

        ep = classify_endpoint(
            method,
            path,
            documented_codes,
            seen,
            passing,
            failing,
            ignore,
        )
        endpoint_reports.append(ep)

        # Update summary (only non-ignored documented codes)
        total_doc += len(ep["nonignored_docs"])
        total_pass += len(ep["covered_passing"])
        total_fail += len(ep["covered_failing"])
        total_untested += len(ep["untested"])
        extra_total += len(ep["extra_nonignored"]) + len(ep["extra_ignored"])

        # Text output
        documented_codes_sorted = sorted(ep["documented"])
        print(f"{method} {path}")
        print(f"  documented:                     {documented_codes_sorted}")
        print(f"  documented (non-ignored):       {sorted(ep['nonignored_docs']) or '-'}")
        print(f"  seen (any):                     {sorted(ep['seen']) or '-'}")
        print(f"  covered & passing:              {sorted(ep['covered_passing']) or '-'}")
        print(f"  covered & failing:              {sorted(ep['covered_failing']) or '-'}")
        print(f"  untested (non-ignored):         {sorted(ep['untested']) or '-'}")
        print(f"  ignored documented statuses:    {sorted(ep['ignored_docs']) or '-'}")
        print(f"  ignored & failing:              {sorted(ep['ignored_failing']) or '-'}")
        extra_all = ep["extra_nonignored"] | ep["extra_ignored"]
        print(f"  undocumented but seen (FAIL):   {sorted(extra_all) or '-'}")
        print()

    if out_path:
        summary = {
            "total_doc": total_doc,
            "total_pass": total_pass,
            "total_fail": total_fail,
            "total_untested": total_untested,
            "extra_total": extra_total,
        }
        render_html(out_path, endpoint_reports, summary, ignore_patterns)


if __name__ == "__main__":
    main()
