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