from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from .models import Click, Link, SLUG_LENGTH


class LinkModelTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password="password123"
        )
        self.bob = User.objects.create_user(
            username="bob", email="bob@example.com", password="password123"
        )

    def test_slug_autogenerates_and_public_path(self) -> None:
        link = Link.objects.create(user=self.alice, target_url="https://example.com")

        self.assertTrue(link.slug)
        self.assertEqual(len(link.slug), SLUG_LENGTH)
        self.assertEqual(link.public_path, f"/{self.alice.username}/{link.slug}/")

    def test_slug_unique_per_user(self) -> None:
        Link.objects.create(
            user=self.alice,
            target_url="https://example.com/one",
            slug="customslug",
        )

        with self.assertRaises(IntegrityError):
            Link.objects.create(
                user=self.alice,
                target_url="https://example.com/two",
                slug="customslug",
            )

    def test_same_slug_allowed_for_different_users(self) -> None:
        first = Link.objects.create(
            user=self.alice,
            target_url="https://example.com/one",
            slug="sharedslug",
        )
        second = Link.objects.create(
            user=self.bob,
            target_url="https://example.com/two",
            slug="sharedslug",
        )

        self.assertNotEqual(first.pk, second.pk)


class ClickModelTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password="password123"
        )
        self.link = Link.objects.create(
            user=self.alice, target_url="https://example.com"
        )

    def test_click_records_metadata(self) -> None:
        click = Click.objects.create(
            link=self.link,
            referrer="https://referrer.test",
            user_agent="FakeBrowser/1.0",
            ip_address="203.0.113.1",
        )

        self.assertEqual(click.link, self.link)
        self.assertEqual(click.referrer, "https://referrer.test")
        self.assertEqual(click.user_agent, "FakeBrowser/1.0")
        self.assertEqual(click.ip_address, "203.0.113.1")


class LinkCRUDTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password="password123"
        )
        self.bob = User.objects.create_user(
            username="bob", email="bob@example.com", password="password123"
        )
        self.alice_link = Link.objects.create(
            user=self.alice, target_url="https://example.com/alice", slug="alice1"
        )
        self.bob_link = Link.objects.create(
            user=self.bob, target_url="https://example.com/bob", slug="bob1"
        )

    def test_list_shows_only_user_links(self) -> None:
        self.client.login(email="alice@example.com", password="password123")
        response = self.client.get(reverse("link_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alice1")
        self.assertNotContains(response, "bob1")

    def test_create_link_sets_user_and_redirects(self) -> None:
        self.client.login(email="alice@example.com", password="password123")
        response = self.client.post(
            reverse("link_create"),
            {"target_url": "https://new.example.com", "slug": "newslug"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        created = Link.objects.get(slug="newslug", user=self.alice)
        self.assertEqual(created.target_url, "https://new.example.com")

    def test_detail_requires_owner(self) -> None:
        self.client.login(email="alice@example.com", password="password123")

        ok = self.client.get(reverse("link_detail", args=[self.alice_link.pk]))
        self.assertEqual(ok.status_code, 200)

        forbidden = self.client.get(reverse("link_detail", args=[self.bob_link.pk]))
        self.assertEqual(forbidden.status_code, 404)

    def test_update_allows_owner(self) -> None:
        self.client.login(email="alice@example.com", password="password123")
        response = self.client.post(
            reverse("link_update", args=[self.alice_link.pk]),
            {"target_url": "https://updated.example.com", "slug": "alice1"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.alice_link.refresh_from_db()
        self.assertEqual(self.alice_link.target_url, "https://updated.example.com")

    def test_delete_allows_owner(self) -> None:
        self.client.login(email="alice@example.com", password="password123")
        response = self.client.post(
            reverse("link_delete", args=[self.alice_link.pk]), follow=True
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Link.objects.filter(pk=self.alice_link.pk).exists())


class LinkPublicRedirectTests(TestCase):
    def setUp(self) -> None:
        User = get_user_model()
        self.alice = User.objects.create_user(
            username="alice", email="alice@example.com", password="password123"
        )
        self.link = Link.objects.create(
            user=self.alice,
            target_url="https://example.com/target",
            slug="testslug",
        )

    def test_redirect_creates_click_and_redirects(self) -> None:
        response = self.client.get(
            reverse("link_redirect", args=[self.alice.username, self.link.slug]),
            HTTP_REFERER="https://social.example.com",
            HTTP_USER_AGENT="TestBrowser/1.0",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], self.link.target_url)
        click = Click.objects.get(link=self.link)
        self.assertEqual(click.referrer, "https://social.example.com")
        self.assertEqual(click.user_agent, "TestBrowser/1.0")

    def test_redirect_captures_ip_address(self) -> None:
        response = self.client.get(
            reverse("link_redirect", args=[self.alice.username, self.link.slug]),
            REMOTE_ADDR="192.0.2.1",
        )

        self.assertEqual(response.status_code, 302)
        click = Click.objects.get(link=self.link)
        self.assertEqual(click.ip_address, "192.0.2.1")

    def test_redirect_nonexistent_slug_returns_404(self) -> None:
        response = self.client.get(
            reverse("link_redirect", args=[self.alice.username, "nonexistent"])
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Click.objects.count(), 0)

    def test_redirect_wrong_username_returns_404(self) -> None:
        response = self.client.get(
            reverse("link_redirect", args=["wronguser", self.link.slug])
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Click.objects.count(), 0)
