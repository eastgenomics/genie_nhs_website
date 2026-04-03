# NHS GENIE UAT Acceptance Checklist

**UAT URL:** `__UAT_URL__`
**Prod URL:** `https://35.179.237.59`
**Date:** ________
**Tester:** ________

---

## Navigation

- [ ] Homepage loads with NHS GENIE logo and search bar
- [ ] "About" link in navbar navigates to /about/ without errors
- [ ] /about/ page renders patient count category descriptions correctly

## Search

- [ ] Gene search: enter "BRAF" -> redirects to /variants/, table loads with data
- [ ] Region search: enter "7:140453136-140924929" -> table loads with results
- [ ] Range search: enter "17:31094689" with POS > operator -> results include downstream variants
- [ ] Invalid gene (e.g. "FAKEGENE999") -> empty table, no crash

## Variant Table

- [ ] Table shows columns: Chr, Pos, Allele type, Consequence, MAF classification, HGVSc, HGVSp, Gene, Transcript, All, Solid, HaemOnc
- [ ] "+" button expands row detail subtable (cancer type patient counts load via AJAX)
- [ ] Classification filter (e.g. select only "PTV LoF") -> table updates correctly
- [ ] Allele type filter (SNV / INDEL toggle) -> table updates correctly
- [ ] Column search boxes filter results correctly

## Visual / UI

- [ ] No broken CSS — page renders with correct Bootstrap styling
- [ ] No JS console errors (check browser developer tools)
- [ ] "(?) " info modal opens when clicked next to classification filter
- [ ] Footer / version string shows correct GENIE version

## Sign-off

- [ ] All automated tests passed (`make acceptance-test`)
- [ ] DB row count verified (`make verify-db`)

**Result:** PASS / FAIL

**Notes:**

---
