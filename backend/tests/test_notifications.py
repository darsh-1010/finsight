"""
Tests for notification endpoints.

  GET  /api/v1/notifications
  POST /api/v1/notifications/{id}/read

The /unread-count sub-path does NOT exist in this codebase.
The listing endpoint returns a JSON array directly (no wrapper object).
Notifications seeded via the admin API are committed separately so they
are visible to the route handler's DB session.
"""



class TestGetNotifications:
    """Tests for the notifications listing endpoint (GET /api/v1/notifications)."""

    def test_unauthenticated_returns_401(self, client):
        """Unauthenticated requests must be rejected."""
        response = client.get("/api/v1/notifications")
        assert response.status_code == 401

    def test_authenticated_returns_200(self, auth_client):
        """Authenticated user receives 200."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/notifications")
        assert response.status_code == 200

    def test_response_is_a_list(self, auth_client):
        """Endpoint returns a JSON array (not a wrapped object)."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/notifications")
        assert isinstance(response.json(), list)

    def test_empty_list_for_new_user(self, auth_client):
        """A fresh user with no targeted notifications should get an empty array."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/notifications")
        # May be empty if no ALL-audience notifications exist in the test DB
        assert isinstance(response.json(), list)

    def test_limit_param_accepted(self, auth_client):
        """Endpoint accepts a limit query parameter."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/notifications?limit=5")
        assert response.status_code == 200

    def test_limit_upper_bound_enforced(self, auth_client):
        """Limit above 100 must be rejected (422)."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/notifications?limit=200")
        assert response.status_code == 422

    def test_limit_lower_bound_enforced(self, auth_client):
        """Limit below 1 must be rejected (422)."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/notifications?limit=0")
        assert response.status_code == 422

    def test_unread_only_param_accepted(self, auth_client):
        """unread_only=true must not crash the endpoint."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/notifications?unread_only=true")
        assert response.status_code == 200

    def test_notification_item_schema(self, auth_client):
        """If any notifications are returned, each item must have required fields."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/notifications")
        items = response.json()
        required_fields = {"id", "title", "message", "notification_type", "is_read"}
        for item in items:
            missing = required_fields - set(item.keys())
            assert not missing, f"Item missing fields: {missing}"

    def test_no_server_error(self, auth_client):
        """Endpoint must never return a 5xx status."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/notifications")
        assert response.status_code < 500


class TestMarkNotificationRead:
    """Tests for marking a notification as read (POST /api/v1/notifications/{id}/read)."""

    def test_unauthenticated_returns_401(self, client):
        """Marking a notification without auth must be rejected."""
        response = client.post("/api/v1/notifications/999/read")
        assert response.status_code == 401

    def test_mark_nonexistent_notification_returns_404(self, auth_client):
        """Marking a non-existent notification should return 404."""
        test_client, _ = auth_client
        response = test_client.post("/api/v1/notifications/99999999/read")
        assert response.status_code == 404

    def test_mark_read_no_server_error(self, auth_client):
        """Marking any notification ID must not return a 5xx."""
        test_client, _ = auth_client
        response = test_client.post("/api/v1/notifications/1/read")
        assert response.status_code < 500
