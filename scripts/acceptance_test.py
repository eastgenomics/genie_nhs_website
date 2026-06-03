#!/usr/bin/env python3
"""
NHS GENIE Acceptance Test Suite

Runs known-value and parity tests against UAT (and optionally prod) instances.

Known-value expectations are derived from GENIE v19 acceptance testing:
https://cuhbioinformatics.atlassian.net/wiki/spaces/DV/pages/4426629121/

IMPORTANT: Expected values are for GENIE_v19_GRCh38_counts_v1.0.0.vcf.gz.
All coordinates are GRCh38. The worked examples below (SAMHD1 / TP63) are
taken from the "All patient counts ..." and "Inframe deletion counts ..."
tests on that page. If the data version changes, these values must be updated.

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

def _find_variant_row(base_url: str, region: str, hgvsp_substr: str):
    """Return the variant row at a GRCh38 region whose hgvs_p contains a
    given substring (used to disambiguate multiple alleles at one position)."""
    data = fetch_json(base_url, "/main/ajax_variants/", {
        "search_key": "region", "search_value": region,
    })
    for row in data.get("rows", []):
        if hgvsp_substr in (row.get("hgvs_p") or ""):
            return row
    return None


def _pc_field_by_cancer(pc_rows: list, field: str) -> dict:
    """Map cancer_type -> value of `field` for non-null PC rows."""
    out = {}
    for r in pc_rows:
        val = r.get(field)
        if val is not None:
            out[r["cancer_type"]] = val
    return out


def _check_pc(suite, base_url, label, variant_id, field, expected):
    """Assert that PC `field` matches expected {cancer_type: value} exactly
    for the listed cancer types (other cancer types are not constrained)."""
    try:
        pc_data = fetch_json(
            base_url, "/main/ajax_variant_cancer_pcs",
            {"variant_id": variant_id},
        )
    except RuntimeError as e:
        suite.add(label, False, str(e))
        return
    actual = _pc_field_by_cancer(pc_data.get("rows", []), field)
    mismatches = [
        f"{ct}: expected={exp}, got={actual.get(ct)}"
        for ct, exp in expected.items()
        if actual.get(ct) != exp
    ]
    suite.add(label, not mismatches, "; ".join(mismatches))


def run_known_value_tests(suite: TestSuite, base_url: str):
    """Tests against hardcoded expected values from v19 acceptance testing.

    Worked examples (GRCh38) from the GENIE v19 controlled-file test page:
      - SAMHD1 20:36935111 G>A   (missense)       SameNuc/SameAA counts
      - SAMHD1 20:36927220 G>A   (stop_gained)    downstream-truncating counts
      - SAMHD1 20:36919495 ..del (inframe del)    nested inframe-deletion counts
    Cohort denominators: All Cancers 208523, Haemonc 18695, Solid 182170.
    """
    print(f"\n{BOLD}Known-value tests against: {base_url}{RESET}\n")

    # KV-S: Smoke -- HTTP 200 on key pages
    for label, path in [
        ("KV-S1 Homepage returns 200", "/"),
        ("KV-S2 About page returns 200", "/main/about/"),
        ("KV-S3 Variants page returns 200",
         "/main/variants/?search_key=gene&search_value=SAMHD1"),
    ]:
        status = fetch_status(base_url, path)
        suite.add(label, status == 200, f"Got HTTP {status}")

    # KV-1: SAMHD1 20:36935111 G>A (missense, p.Arg143Cys) exists with the
    # expected SameNucleotideChange aggregate counts on the table row.
    print("  Testing SAMHD1 20:36935111 G>A (missense)...")
    try:
        row = _find_variant_row(base_url, "20:36935111", "Arg143Cys")
    except RuntimeError as e:
        row = None
        suite.add("KV-1  SAMHD1 20:36935111 row present", False, str(e))
    if row is not None:
        suite.add(
            "KV-1  SAMHD1 20:36935111 row (gene + nucleotide counts)",
            row.get("gene") == "SAMHD1"
            and row.get("all_cancers_count") == 2
            and row.get("haemonc_cancers_count") == 2
            and row.get("solid_cancers_count") == 0,
            f"gene={row.get('gene')} all={row.get('all_cancers_count')} "
            f"haem={row.get('haemonc_cancers_count')} "
            f"solid={row.get('solid_cancers_count')}",
        )
        # KV-2: SameAminoAcidChange per cancer type for the same variant.
        _check_pc(
            suite, base_url,
            "KV-2  SAMHD1 20:36935111 SameAminoAcidChange counts",
            row.get("variant_id"), "same_amino_acid_change_pc",
            {
                "All Cancers": 2,
                "Haemonc Cancers": 2,
                "Mature B-Cell Neoplasms": 1,
                "Mature T and NK Neoplasms": 1,
            },
        )
        # KV-5: cohort denominators (cancer_n) carried on the PC rows.
        _check_pc(
            suite, base_url,
            "KV-5  Cohort denominators (cancer_n)",
            row.get("variant_id"), "cancer_n",
            {
                "All Cancers": 208523,
                "Haemonc Cancers": 18695,
                "Solid Cancers": 182170,
                "Mature B-Cell Neoplasms": 7653,
            },
        )
    elif not any(r.name.startswith("KV-1") for r in suite.results):
        suite.add("KV-1  SAMHD1 20:36935111 row present", False, "not found")

    # KV-3: SAMHD1 20:36927220 G>A (stop_gained, p.Arg220Ter)
    # SameOrDownstreamTruncatingVariantsPerAA counts.
    print("  Testing SAMHD1 20:36927220 G>A (downstream truncating)...")
    try:
        row = _find_variant_row(base_url, "20:36927220", "Arg220Ter")
    except RuntimeError as e:
        row = None
        suite.add("KV-3  SAMHD1 20:36927220 downstream-truncating", False,
                  str(e))
    if row is not None:
        _check_pc(
            suite, base_url,
            "KV-3  SAMHD1 20:36927220 SameOrDownstreamTruncatingPerAA counts",
            row.get("variant_id"),
            "same_or_downstream_truncating_variants_per_aa_pc",
            {
                "All Cancers": 21,
                "Haemonc Cancers": 20,
                "Mature B-Cell Neoplasms": 15,
                "Mature T and NK Neoplasms": 4,
                "Histiocytosis": 1,
                "UNKNOWN": 2,
            },
        )

    # KV-4: SAMHD1 20:36919495 ACAT>A (inframe deletion, p.Met240del)
    # NestedInframeDeletionsPerAA counts.
    print("  Testing SAMHD1 20:36919495 (nested inframe deletion)...")
    try:
        row = _find_variant_row(base_url, "20:36919495", "Met240del")
    except RuntimeError as e:
        row = None
        suite.add("KV-4  SAMHD1 20:36919495 nested inframe deletion", False,
                  str(e))
    if row is not None:
        _check_pc(
            suite, base_url,
            "KV-4  SAMHD1 20:36919495 NestedInframeDeletionsPerAA counts",
            row.get("variant_id"), "nested_inframe_deletions_per_aa_pc",
            {
                "All Cancers": 1,
                "Haemonc Cancers": 1,
                "Mature B-Cell Neoplasms": 1,
            },
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
            "PT-2  SAMHD1 gene (rows + total)",
            "/main/ajax_variants/",
            {"search_key": "gene", "search_value": "SAMHD1"},
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

    # PT-3: Compare cancer type patient counts for SAMHD1 20:36935111 G>A
    print("  Comparing PT-3 variant 20:36935111 cancer type PCs...")

    try:
        uat_region = fetch_json(uat_url, "/main/ajax_variants/", {
            "search_key": "region", "search_value": "20:36935111"
        })
        prod_region = fetch_json(prod_url, "/main/ajax_variants/", {
            "search_key": "region", "search_value": "20:36935111"
        })
    except RuntimeError as e:
        suite.add("PT-3  Variant 20:36935111 cancer type PCs", False, str(e))
        return

    uat_vid = None
    for row in uat_region.get("rows", []):
        if "Arg143Cys" in (row.get("hgvs_p") or ""):
            uat_vid = row.get("variant_id")
            break

    prod_vid = None
    for row in prod_region.get("rows", []):
        if "Arg143Cys" in (row.get("hgvs_p") or ""):
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
                "PT-3  Variant 20:36935111 cancer type PCs", False, str(e)
            )
            return

        pcs_match = uat_pcs.get("rows") == prod_pcs.get("rows")
        suite.add(
            "PT-3  Variant 20:36935111 cancer type PCs",
            pcs_match,
            "Patient count rows differ" if not pcs_match else "",
        )
    else:
        suite.add(
            "PT-3  Variant 20:36935111 cancer type PCs",
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
