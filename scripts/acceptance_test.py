#!/usr/bin/env python3
"""
NHS GENIE Acceptance Test Suite

Runs known-value and parity tests against UAT (and optionally prod) instances.

Known-value expectations are derived from GENIE v17 acceptance testing:
https://cuhbioinformatics.atlassian.net/wiki/spaces/SR/pages/4164452353/

IMPORTANT: Expected values are for Genie_v17_GRCh38_counts_v1.0.0.vcf.gz.
If the data version changes, these values must be updated.

Usage:
    python scripts/acceptance_test.py --uat-url http://HOST:PORT [--prod-url http://HOST:PORT]
    python scripts/acceptance_test.py --uat-url http://HOST:PORT --mode known-values
    python scripts/acceptance_test.py --uat-url http://HOST:PORT --mode parity --prod-url http://HOST:PORT
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field


def validate_base_url(url: str, arg_name: str) -> str:
    """Validate that a URL uses http:// or https:// scheme."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise argparse.ArgumentTypeError(
            f"{arg_name} must use http:// or https:// (got: {url})"
        )
    if not parsed.netloc:
        raise argparse.ArgumentTypeError(
            f"{arg_name} must include a host (got: {url})"
        )
    return url.rstrip("/")

# ── Colours (disabled when not a TTY) ────────────────────────────────────────

if sys.stdout.isatty():
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
else:
    GREEN = RED = YELLOW = BOLD = RESET = ""


# ── Helpers ──────────────────────────────────────────────────────────────────

@dataclass
class TestResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class TestSuite:
    results: list = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str = ""):
        self.results.append(TestResult(name, passed, detail))

    def print_summary(self):
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        print(f"\n{BOLD}{'=' * 60}{RESET}")
        print(f"{BOLD}Results: {passed}/{total} passed{RESET}")
        for r in self.results:
            icon = f"{GREEN}PASS{RESET}" if r.passed else f"{RED}FAIL{RESET}"
            print(f"  [{icon}] {r.name}")
            if r.detail and not r.passed:
                print(f"         {r.detail}")
        print()
        return passed == total


def fetch_json(base_url: str, path: str, params: dict | None = None) -> dict:
    """Fetch JSON from a URL with query parameters."""
    url = f"{base_url.rstrip('/')}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode()
            return json.loads(body)
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error fetching {url}: {e}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Invalid JSON from {url}: {e}\nResponse: {body[:500]}"
        ) from e


def fetch_status(base_url: str, path: str) -> int:
    """Fetch HTTP status code for a page."""
    url = f"{base_url.rstrip('/')}{path}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except urllib.error.URLError as e:
        print(f"  {RED}Network error: {url}: {e}{RESET}")
        return 0


# ── Known-value tests ────────────────────────────────────────────────────────

def run_known_value_tests(suite: TestSuite, base_url: str):
    """Tests against hardcoded expected values from v17 acceptance testing."""
    print(f"\n{BOLD}Known-value tests against: {base_url}{RESET}\n")

    # KV-6, KV-7, KV-8: Smoke -- HTTP 200 on key pages
    for label, path in [
        ("KV-6  Homepage returns 200", "/"),
        ("KV-7  About page returns 200", "/main/about/"),
        ("KV-8  Variants page returns 200",
         "/main/variants/?search_key=gene&search_value=BRAF"),
    ]:
        status = fetch_status(base_url, path)
        suite.add(label, status == 200, f"Got HTTP {status}")

    # KV-1: NF1 gene -> 7928 variants
    print("  Testing NF1 gene variant count...")
    try:
        data = fetch_json(base_url, "/main/ajax_variants/", {
            "search_key": "gene", "search_value": "NF1"
        })
        suite.add(
            "KV-1  NF1 gene total == 7928",
            int(data.get("total", 0)) == 7928,
            f"Got total={data.get('total')}",
        )
    except RuntimeError as e:
        suite.add("KV-1  NF1 gene total == 7928", False, str(e))

    # KV-2: Region 7:102227600-102227800 -> 35 variants
    print("  Testing region 7:102227600-102227800...")
    try:
        data = fetch_json(base_url, "/main/ajax_variants/", {
            "search_key": "region", "search_value": "7:102227600-102227800"
        })
        suite.add(
            "KV-2  Region 7:102227600-102227800 total == 35",
            int(data.get("total", 0)) == 35,
            f"Got total={data.get('total')}",
        )
    except RuntimeError as e:
        suite.add(
            "KV-2  Region 7:102227600-102227800 total == 35", False, str(e)
        )

    # KV-3: BRAF missense/inframe indel count -> 1349
    print("  Testing BRAF missense count...")
    try:
        data = fetch_json(base_url, "/main/ajax_variants/", {
            "search_key": "gene", "search_value": "BRAF"
        })
        missense_count = sum(
            1 for row in data.get("rows", [])
            if row.get("classification_category") == "Missense / Inframe indel"
        )
        suite.add(
            "KV-3  BRAF Missense/Inframe indel count == 1349",
            missense_count == 1349,
            f"Got count={missense_count}",
        )
    except RuntimeError as e:
        suite.add(
            "KV-3  BRAF Missense/Inframe indel count == 1349", False, str(e)
        )

    # KV-4 + KV-5: Variant 2-208248400-A-G exists and has correct patient counts
    print("  Testing variant 2:208248400 A>G patient counts...")
    try:
        data = fetch_json(base_url, "/main/ajax_variants/", {
            "search_key": "region", "search_value": "2:208248400"
        })
    except RuntimeError as e:
        suite.add("KV-4  Variant 2:208248400 exists in results", False, str(e))
        suite.add(
            "KV-5  Variant 2:208248400 cancer type patient counts match",
            False, "Skipped -- KV-4 failed",
        )
        return

    target_row = None
    for row in data.get("rows", []):
        if (str(row.get("chrom")) == "2"
                and row.get("pos") == 208248400):
            target_row = row
            break

    suite.add(
        "KV-4  Variant 2:208248400 exists in results",
        target_row is not None,
        "Variant not found in results",
    )

    if target_row:
        variant_id = target_row.get("variant_id")
        try:
            pc_data = fetch_json(
                base_url, "/main/ajax_variant_cancer_pcs",
                {"variant_id": variant_id},
            )
        except RuntimeError as e:
            suite.add(
                "KV-5  Variant 2:208248400 cancer type patient counts match",
                False, str(e),
            )
            return

        pc_rows = pc_data.get("rows", [])

        # Expected SameNucleotideChange patient counts (from Confluence testing)
        expected_pcs = {
            "Esophagogastric Cancer": 1,
            "Colorectal Cancer": 1,
            "Glioma": 1,
            "Wilms Tumor": 1,
            "Cervical Cancer": 2,
            "Gastrointestinal Stromal Tumor": 1,
        }

        actual_pcs = {}
        for pc_row in pc_rows:
            snc = pc_row.get("same_nucleotide_change_pc")
            if snc and snc > 0:
                actual_pcs[pc_row["cancer_type"]] = snc

        mismatches = []
        for cancer_type, expected_count in expected_pcs.items():
            actual = actual_pcs.get(cancer_type)
            if actual != expected_count:
                mismatches.append(
                    f"{cancer_type}: expected={expected_count}, got={actual}"
                )

        unexpected = {
            ct: count for ct, count in actual_pcs.items()
            if ct not in expected_pcs
        }
        if unexpected:
            mismatches.append(f"Unexpected non-zero counts: {unexpected}")

        suite.add(
            "KV-5  Variant 2:208248400 cancer type patient counts match",
            len(mismatches) == 0,
            "; ".join(mismatches) if mismatches else "",
        )
    else:
        suite.add(
            "KV-5  Variant 2:208248400 cancer type patient counts match",
            False,
            "Skipped -- variant not found in KV-4",
        )


# ── Parity tests ─────────────────────────────────────────────────────────────

def run_parity_tests(suite: TestSuite, uat_url: str, prod_url: str):
    """Compare JSON responses between UAT and prod for identical queries."""
    print(f"\n{BOLD}Parity tests: {uat_url} vs {prod_url}{RESET}\n")

    queries = [
        (
            "PT-1  BRAF gene (rows + total)",
            "/main/ajax_variants/",
            {"search_key": "gene", "search_value": "BRAF"},
        ),
        (
            "PT-2  Region 7:102227600-102227800",
            "/main/ajax_variants/",
            {"search_key": "region", "search_value": "7:102227600-102227800"},
        ),
        (
            "PT-4  IDH1 gene (rows + total)",
            "/main/ajax_variants/",
            {"search_key": "gene", "search_value": "IDH1"},
        ),
    ]

    for label, path, params in queries:
        print(f"  Comparing {label}...")
        try:
            uat_data = fetch_json(uat_url, path, params)
            prod_data = fetch_json(prod_url, path, params)
        except RuntimeError as e:
            suite.add(label, False, str(e))
            continue

        totals_match = uat_data.get("total") == prod_data.get("total")
        rows_match = uat_data.get("rows") == prod_data.get("rows")

        passed = totals_match and rows_match
        detail = ""
        if not totals_match:
            detail = (
                f"total mismatch: UAT={uat_data.get('total')}, "
                f"prod={prod_data.get('total')}"
            )
        elif not rows_match:
            uat_len = len(uat_data.get("rows", []))
            prod_len = len(prod_data.get("rows", []))
            detail = f"row data differs (UAT rows={uat_len}, prod rows={prod_len})"

        suite.add(label, passed, detail)

    # PT-3: Compare cancer type patient counts for variant 2:208248400
    print("  Comparing PT-3 variant 2:208248400 cancer type PCs...")

    try:
        uat_region = fetch_json(uat_url, "/main/ajax_variants/", {
            "search_key": "region", "search_value": "2:208248400"
        })
        prod_region = fetch_json(prod_url, "/main/ajax_variants/", {
            "search_key": "region", "search_value": "2:208248400"
        })
    except RuntimeError as e:
        suite.add("PT-3  Variant 2:208248400 cancer type PCs", False, str(e))
        return

    uat_vid = None
    for row in uat_region.get("rows", []):
        if str(row.get("chrom")) == "2" and row.get("pos") == 208248400:
            uat_vid = row.get("variant_id")
            break

    prod_vid = None
    for row in prod_region.get("rows", []):
        if str(row.get("chrom")) == "2" and row.get("pos") == 208248400:
            prod_vid = row.get("variant_id")
            break

    if uat_vid is not None and prod_vid is not None:
        try:
            uat_pcs = fetch_json(
                uat_url, "/main/ajax_variant_cancer_pcs", {"variant_id": uat_vid}
            )
            prod_pcs = fetch_json(
                prod_url, "/main/ajax_variant_cancer_pcs", {"variant_id": prod_vid}
            )
        except RuntimeError as e:
            suite.add(
                "PT-3  Variant 2:208248400 cancer type PCs", False, str(e)
            )
            return

        pcs_match = uat_pcs.get("rows") == prod_pcs.get("rows")
        suite.add(
            "PT-3  Variant 2:208248400 cancer type PCs",
            pcs_match,
            "Patient count rows differ" if not pcs_match else "",
        )
    else:
        suite.add(
            "PT-3  Variant 2:208248400 cancer type PCs",
            False,
            f"Variant not found (UAT vid={uat_vid}, prod vid={prod_vid})",
        )


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="NHS GENIE Acceptance Test Suite"
    )
    parser.add_argument(
        "--uat-url", required=True,
        help="UAT instance base URL (e.g. http://1.2.3.4:8000)",
    )
    parser.add_argument(
        "--prod-url", default=None,
        help="Prod instance base URL for parity tests (optional)",
    )
    parser.add_argument(
        "--mode", choices=["all", "known-values", "parity"],
        default="all",
        help="Test mode (default: all)",
    )
    args = parser.parse_args()
    args.uat_url = validate_base_url(args.uat_url, "--uat-url")
    if args.prod_url:
        args.prod_url = validate_base_url(args.prod_url, "--prod-url")

    if args.mode == "parity" and not args.prod_url:
        parser.error("--prod-url is required when --mode parity")

    suite = TestSuite()

    if args.mode in ("all", "known-values"):
        run_known_value_tests(suite, args.uat_url)

    if args.mode in ("all", "parity"):
        if args.prod_url:
            run_parity_tests(suite, args.uat_url, args.prod_url)
        else:
            print(
                f"\n{YELLOW}Parity tests skipped: "
                f"--prod-url not provided{RESET}"
            )

    all_passed = suite.print_summary()
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
