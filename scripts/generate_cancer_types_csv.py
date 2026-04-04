#!/usr/bin/env python3
"""
Generate cancer_types.csv from a GENIE VCF and cancer type classification files.

Extracts cancer type names and total patient counts from VCF INFO fields,
then maps them to display names and haemonc/solid classifications using
the provided text files.

Usage:
    python scripts/generate_cancer_types_csv.py \
        --vcf data/GENIE_v19_GRCh38_counts_v1.0.0.vcf.gz \
        --haemonc data/haemonc_cancer_types.txt \
        --solid data/solid_cancer_types.txt \
        --output data/cancer_types_v19.csv

Optionally, pass --reference to use an existing cancer_types.csv as a
lookup for display_name mappings (handles edge cases like "NOS", commas,
and slashes that can't be reliably derived from CamelCase VCF names):

    python scripts/generate_cancer_types_csv.py \
        --vcf data/GENIE_v19_GRCh38_counts_v1.0.0.vcf.gz \
        --haemonc data/haemonc_cancer_types.txt \
        --solid data/solid_cancer_types.txt \
        --reference data/cancer_types.csv \
        --output data/cancer_types_v19.csv
"""

import argparse
import csv
import gzip
import re
import sys


def parse_vcf_cancer_types(vcf_path: str) -> dict[str, int]:
    """
    Scan a gzipped VCF to extract all cancer type VCF names and their
    total patient counts.

    VCF INFO keys follow the pattern:
        SameNucleotideChange_{CancerType}_Count_N_{TotalN}={value}

    Scans the full file because some VCFs only include cancer type fields
    for non-zero counts, so a single variant line may not list all types.

    Returns dict of {vcf_name: total_patient_count}.
    """
    cancer_types = {}
    count = 0

    with gzip.open(vcf_path, mode="rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue

            count += 1
            # Parse INFO column (8th field, index 7)
            info = line.strip().split("\t")[7]
            for field in info.split(";"):
                if not field.startswith("SameNucleotideChange_"):
                    continue
                key = field.split("=")[0]
                # Format: SameNucleotideChange_{CancerType}_Count_N_{TotalN}
                remainder = key[len("SameNucleotideChange_"):]
                match = re.match(r"^(.+)_Count_N_(\d+)$", remainder)
                if match:
                    vcf_name = match.group(1)
                    total_n = int(match.group(2))
                    # Keep the patient count (same across all variants)
                    if vcf_name not in cancer_types:
                        cancer_types[vcf_name] = total_n

            if count % 100000 == 0:
                print(f"  Scanned {count} variants, found {len(cancer_types)} cancer types so far...")

    print(f"  Scanned {count} variants total")
    return cancer_types


def load_display_names(filepath: str) -> set[str]:
    """Load cancer type display names from a text file (one per line)."""
    with open(filepath) as f:
        return {line.strip() for line in f if line.strip()}


def load_reference_csv(filepath: str) -> dict[str, str]:
    """
    Load an existing cancer_types.csv as a vcf_name -> display_name lookup.
    """
    mapping = {}
    with open(filepath, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            mapping[row["vcf_name"]] = row["display_name"]
    return mapping


def normalise(name: str) -> str:
    """Normalise a name for fuzzy matching: lowercase, strip non-alnum."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def build_display_name_lookup(
    haemonc_names: set[str], solid_names: set[str]
) -> dict[str, str]:
    """
    Build a normalised lookup from all display names.
    Returns dict of {normalised_name: original_display_name}.
    """
    lookup = {}
    for name in haemonc_names | solid_names:
        lookup[normalise(name)] = name
    return lookup


def main():
    parser = argparse.ArgumentParser(
        description="Generate cancer_types.csv from GENIE VCF"
    )
    parser.add_argument("--vcf", required=True, help="Path to gzipped GENIE VCF")
    parser.add_argument(
        "--haemonc", required=True, help="Path to haemonc cancer types txt"
    )
    parser.add_argument(
        "--solid", required=True, help="Path to solid cancer types txt"
    )
    parser.add_argument("--output", required=True, help="Output CSV path")
    parser.add_argument(
        "--reference",
        default=None,
        help="Optional: existing cancer_types.csv for display name lookup",
    )
    args = parser.parse_args()

    print(f"Parsing VCF: {args.vcf}")
    vcf_cancer_types = parse_vcf_cancer_types(args.vcf)
    print(f"  Found {len(vcf_cancer_types)} cancer types in VCF")

    haemonc_names = load_display_names(args.haemonc)
    solid_names = load_display_names(args.solid)
    print(f"  Haemonc types: {len(haemonc_names)}, Solid types: {len(solid_names)}")

    # Build lookup for vcf_name -> display_name
    if args.reference:
        print(f"  Using reference CSV: {args.reference}")
        ref_mapping = load_reference_csv(args.reference)
    else:
        ref_mapping = {}

    # Normalised lookup from txt files
    display_lookup = build_display_name_lookup(haemonc_names, solid_names)

    # Build rows
    rows = []
    unmatched = []

    for vcf_name, total_n in sorted(vcf_cancer_types.items()):
        display_name = None
        is_haemonc = 0
        is_solid = 0

        # Try reference CSV first
        if vcf_name in ref_mapping:
            display_name = ref_mapping[vcf_name]
        else:
            # Try normalised matching against txt files
            norm = normalise(vcf_name)
            if norm in display_lookup:
                display_name = display_lookup[norm]

        if display_name:
            is_haemonc = 1 if display_name in haemonc_names else 0
            is_solid = 1 if display_name in solid_names else 0
        else:
            # Unmatched — use vcf_name as display name, flag for review
            display_name = vcf_name
            unmatched.append(vcf_name)

        rows.append(
            {
                "display_name": display_name,
                "vcf_name": vcf_name,
                "is_haemonc": is_haemonc,
                "is_solid": is_solid,
                "total_patient_count": total_n,
            }
        )

    # Write CSV
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "display_name",
                "vcf_name",
                "is_haemonc",
                "is_solid",
                "total_patient_count",
            ],
            quoting=csv.QUOTE_ALL,
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} cancer types to {args.output}")

    if unmatched:
        print(f"\nWARNING: {len(unmatched)} cancer types not matched to "
              "haemonc/solid classification:")
        for name in unmatched:
            print(f"  - {name}")
        print("These have is_haemonc=0, is_solid=0. Review and update manually.")
    else:
        print("All cancer types matched successfully.")


if __name__ == "__main__":
    main()
