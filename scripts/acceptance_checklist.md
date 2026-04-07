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

- [ ] Gene search: enter "TP53" -> redirects to /variants/, table loads with data
- [ ] Region search: enter "7:140453136-140924929" -> table loads with results
- [ ] Invalid gene (e.g. "FAKEGENE999") -> empty table, no crash, "no variants were found message"

## Variant Table

- [ ] Table shows columns: Chr, Pos, Allele type, Consequence, MAF classification, HGVSc, HGVSp, Gene, Transcript, All, Solid, HaemOnc
- [ ] "+" button expands row detail subtable (cancer type patient counts load via AJAX)
- [ ] Classification filter (e.g. select only "PTV LoF") -> table updates correctly
- [ ] Consequence filter (PTV etc toggles) -> table updates correctly
- [ ] Column search boxes filter results correctly

## Visual / UI

- [ ] No broken CSS — page renders with correct Bootstrap styling
- [ ] No JS console errors (check browser developer tools)
- [ ] "(?) " info modal opens when clicked next to classification filter
- [ ] Footer / version string shows correct GENIE version

## Automated acceptance tests (optional; for admins)

- [ ] All automated tests passed (`make acceptance-test`)
- [ ] DB row count verified (`make verify-db`)

**Result:** PASS / FAIL

**Notes:**

---
