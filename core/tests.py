from django.test import TestCase, Client
from django.urls import reverse


class CoreViewsTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_index_view(self):
        """Test the index view renders correctly."""
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/index.html")
