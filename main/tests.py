from django.test import TestCase
from django.urls import reverse, NoReverseMatch


def r(name: str) -> str:
    """Reverse with or without 'main' namespace, depending on project urls."""
    try:
        return reverse(f"main:{name}")
    except NoReverseMatch:
        return reverse(name)


class IndexViewTests(TestCase):
    """Homepage test."""
    def test_index_returns_200(self):
        resp = self.client.get(r("index"))
        self.assertEqual(resp.status_code, 200)


class AboutViewTests(TestCase):
    """About page test."""
    def test_about_returns_200(self):
        resp = self.client.get(r("about"))
        self.assertEqual(resp.status_code, 200)


class ReleaseNotesViewTests(TestCase):
    """Release notes page test."""
    def test_release_notes_returns_200(self):
        resp = self.client.get(r("release_notes"))
        self.assertEqual(resp.status_code, 200)


class VariantsViewTests(TestCase):
    """Variants page test."""
    def test_variants_returns_200(self):
        resp = self.client.get(r("variants"))
        self.assertEqual(resp.status_code, 200)


class SearchViewTests(TestCase):
    """Tests for the search redirect view."""

    def test_gene_search_redirects(self):
        """A gene-name query should redirect (302) without error."""
        resp = self.client.get(r("search") + "?search_value=BRCA1")
        self.assertEqual(resp.status_code, 302)

    def test_empty_search_value_does_not_500(self):
        """An empty search_value must not raise an unhandled server error."""
        resp = self.client.get(r("search") + "?search_value=")
        self.assertEqual(resp.status_code, 302)


class AjaxVariantsTests(TestCase):
    """Tests for the ajax_variants JSON endpoint."""

    def test_missing_search_value_returns_json_not_500(self):
        """Calling /ajax_variants/ without search_value must return HTTP 200
        with a JSON body.
        """
        resp = self.client.get(r("ajax_variants"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/json", resp.get("Content-Type", ""))
