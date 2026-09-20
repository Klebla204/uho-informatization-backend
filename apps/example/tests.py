from django.urls import reverse
from rest_framework.test import APITestCase


class ExampleHealthAPITest(APITestCase):
    def test_health_check_is_available(self):
        url = reverse("health_check")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertIn("service", response.json())
