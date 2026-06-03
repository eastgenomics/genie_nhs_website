# NHS GENIE UAT Acceptance Checklist

**UAT URL:** `__UAT_URL__`
**Prod URL:** `__PROD_URL__`
**Date:** ________
**Tester:** ________

---

## Navigation

- [ ] Homepage loads with NHS GENIE logo and search bar
- [ ] "Information about generation of patient count data" link navigates to /about/ without errors
- [ ] /about/ page renders patient count category descriptions correctly
- [ ] Clicking the NHS GENIE logo (top left) returns you to the homescreen

## Search

- [ ] Gene search: enter "SAMHD1" -> redirects to /variants/, table loads with data
- [ ] Region search: enter "20:36897839-36935111" -> table loads with results
- [ ] Invalid gene (e.g. "FAKEGENE999") -> empty table, no crash, "no variants were found message"

## Variant Table

- [ ] Table shows columns: Chrom, Pos, Consequence, HGVSc, HGVSp, Protein pos, Transcript, Gene, All, Solid, HaemOnc
- [ ] "+" button expands row detail subtable (cancer type patient counts load via AJAX)
- [ ] Consequence filter (e.g. select only "PTV LoF") -> table updates correctly
- [ ] Silent variants are filtered out by default; toggling them on shows synonymous variants
- [ ] Protein position sorting / range filtering works
- [ ] Column search boxes filter results correctly

## Visual / UI

- [ ] No broken CSS — page renders with correct Bootstrap styling
- [ ] No JS console errors (check browser developer tools)
- [ ] "(?) " info modal opens when clicked next to the consequence filter
- [ ] Footer / version string shows correct GENIE version (v19)

## Geo-restriction (UK only)

- [ ] Site loads normally from a UK connection
- [ ] Site returns HTTP 403 from a non-UK connection (e.g. via a non-UK VPN / proxy)

## Automated acceptance tests (optional; for admins)

- [ ] All automated tests passed (`make acceptance-test`)
- [ ] DB row count verified (`make verify-db`) — expected ~1,267,112 variants for v19

**Result:** PASS / FAIL

**Notes:**

---
