import tempfile
import uuid

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Article, Comment

User = get_user_model()


def _ajax_post(client, url):
    """
    shared_utils.middleware.IdempotencyMiddleware caches POST responses per
    (requester, idempotency key) — sending the same key twice is treated as
    a replay of the same logical operation and returns the first response
    instead of re-running the view. Tests that POST to the same toggle
    endpoint more than once (e.g. like then unlike) need a fresh key per
    call so each call actually executes.
    """
    return client.post(
        url,
        HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        HTTP_X_IDEMPOTENCY_KEY=str(uuid.uuid4()),
    )


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CommentLikeTests(TestCase):
    """
    Comment.likes is new — it's the only way to answer "most liked comment"
    on Profile Analysis, mirroring Article.likes/total_likes() exactly.
    """

    def setUp(self):
        self.author = User.objects.create_user('comment_author', password='x')
        self.liker = User.objects.create_user('comment_liker', password='x')
        self.article = Article.objects.create(title='Post', body='body', author=self.author)
        self.comment = Comment.objects.create(article=self.article, author=self.author, body='Nice post.')

    def test_total_likes_starts_at_zero(self):
        self.assertEqual(self.comment.total_likes(), 0)

    def test_toggle_like_adds_like(self):
        self.client.force_login(self.liker)
        response = _ajax_post(self.client, reverse('blog:toggle_comment_like', args=[self.comment.pk]))
        data = response.json()
        self.assertTrue(data['is_liked'])
        self.assertEqual(data['count'], 1)
        self.assertEqual(self.comment.total_likes(), 1)

    def test_toggle_like_twice_removes_like(self):
        self.client.force_login(self.liker)
        url = reverse('blog:toggle_comment_like', args=[self.comment.pk])
        _ajax_post(self.client, url)
        response = _ajax_post(self.client, url)
        data = response.json()
        self.assertFalse(data['is_liked'])
        self.assertEqual(data['count'], 0)

    def test_anonymous_user_cannot_like(self):
        response = _ajax_post(self.client, reverse('blog:toggle_comment_like', args=[self.comment.pk]))
        self.assertEqual(response.status_code, 302)  # redirected to login
        self.assertEqual(self.comment.total_likes(), 0)

    def test_most_liked_comment_query_orders_by_like_count(self):
        other_comment = Comment.objects.create(article=self.article, author=self.liker, body='Also great.')
        other_comment.likes.add(self.author, self.liker)  # 2 likes
        self.comment.likes.add(self.liker)  # 1 like

        from django.db.models import Count
        top = (
            Comment.objects.filter(article__author=self.author)
            .annotate(like_count=Count('likes'))
            .order_by('-like_count', '-created_on')
            .first()
        )
        self.assertEqual(top.pk, other_comment.pk)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IdempotencyMiddlewareTests(TestCase):
    """
    shared_utils/middleware.py::IdempotencyMiddleware — regression coverage
    for a cache-key collision bug: the cache key used to be scoped only by
    the client-supplied idempotency key (with X-Requested-With, identical
    for every AJAX client, used as a last-resort fallback), so two different
    users sending the same key could be served each other's cached response.
    """

    def setUp(self):
        self.author = User.objects.create_user('idem_author', password='x')
        self.user_a = User.objects.create_user('idem_user_a', password='x')
        self.user_b = User.objects.create_user('idem_user_b', password='x')
        article = Article.objects.create(title='Idem Post', body='body', author=self.author)
        self.comment_a = Comment.objects.create(article=article, author=self.author, body='a')
        self.comment_b = Comment.objects.create(article=article, author=self.author, body='b')

    def test_same_idempotency_key_does_not_collide_across_users(self):
        client_a, client_b = Client(), Client()
        client_a.force_login(self.user_a)
        client_b.force_login(self.user_b)
        shared_key = 'shared-client-supplied-key'

        response_a = client_a.post(
            reverse('blog:toggle_comment_like', args=[self.comment_a.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_X_IDEMPOTENCY_KEY=shared_key,
        )
        response_b = client_b.post(
            reverse('blog:toggle_comment_like', args=[self.comment_b.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_X_IDEMPOTENCY_KEY=shared_key,
        )
        # If user B's request had been served user A's cached response
        # instead of actually executing, comment_b would never get liked.
        self.assertEqual(response_a.json()['count'], 1)
        self.assertEqual(response_b.json()['count'], 1)
        self.assertEqual(self.comment_a.total_likes(), 1)
        self.assertEqual(self.comment_b.total_likes(), 1)

    def test_repeating_same_key_for_same_user_replays_cached_response(self):
        self.client.force_login(self.user_a)
        url = reverse('blog:toggle_comment_like', args=[self.comment_a.pk])
        key = 'same-user-repeated-key'
        first = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_X_IDEMPOTENCY_KEY=key)
        second = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_X_IDEMPOTENCY_KEY=key)
        # Replayed, not re-executed — the toggle only actually ran once.
        self.assertTrue(first.json()['is_liked'])
        self.assertTrue(second.json()['is_liked'])
        self.assertEqual(self.comment_a.total_likes(), 1)

    def test_ajax_marker_alone_is_never_treated_as_an_idempotency_key(self):
        self.client.force_login(self.user_a)
        url = reverse('blog:toggle_comment_like', args=[self.comment_a.pk])
        first = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        second = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        # Both calls must actually execute (toggle on, then toggle off) —
        # X-Requested-With must never function as an implicit shared key.
        self.assertTrue(first.json()['is_liked'])
        self.assertFalse(second.json()['is_liked'])


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ArticleImageStorageCleanupTests(TestCase):
    """
    blog/signals.py::delete_article_image_from_storage — same orphaned-
    file-on-delete gap found and fixed for DataRoomDocument also existed
    for Article.image; this is the mirrored fix for the blog app.
    """

    def test_deleting_article_removes_image_from_storage(self):
        author = User.objects.create_user('image_cleanup_author', password='x')
        article = Article.objects.create(
            title='Post', body='body', author=author,
            image=SimpleUploadedFile('cover.jpg', b'x' * 10, content_type='image/jpeg'),
        )
        storage, path = article.image.storage, article.image.name
        self.assertTrue(storage.exists(path))

        article.delete()

        self.assertFalse(storage.exists(path))
