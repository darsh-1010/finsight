"""
Tests for token wallet and transaction endpoints.

  GET /api/v1/tokens/usage
  GET /api/v1/tokens/transactions

Note: The token usage endpoint requires the user to have an active subscription
      (created by the signup flow). Tests verify the exact schema returned by
      the TokenUsage Pydantic model: available_tokens, total_used_tokens, etc.
"""



class TestTokenUsage:
    """Tests for GET /api/v1/tokens/usage."""

    def test_unauthenticated_returns_401(self, client):
        """Token usage endpoint requires authentication."""
        response = client.get("/api/v1/tokens/usage")
        assert response.status_code == 401

    def test_authenticated_returns_200(self, auth_client):
        """Authenticated user with subscription receives HTTP 200."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/usage")
        assert response.status_code == 200

    def test_usage_response_has_available_tokens(self, auth_client):
        """Response must contain 'available_tokens' field (actual schema field name)."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/usage")
        body = response.json()
        assert "available_tokens" in body, f"Response body: {body}"

    def test_usage_available_tokens_is_non_negative(self, auth_client):
        """Available tokens for a newly registered user must be ≥ 0."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/usage")
        body = response.json()
        assert body["available_tokens"] >= 0

    def test_usage_response_has_total_used_tokens(self, auth_client):
        """Response must contain 'total_used_tokens' field."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/usage")
        body = response.json()
        assert "total_used_tokens" in body

    def test_usage_response_has_weekly_tokens(self, auth_client):
        """Response must contain 'weekly_tokens' field."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/usage")
        body = response.json()
        assert "weekly_tokens" in body

    def test_usage_response_has_tier_info(self, auth_client):
        """Response must include tier_level and tier_name."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/usage")
        body = response.json()
        assert "tier_level" in body
        assert "tier_name" in body

    def test_signup_bonus_gives_positive_available_tokens(self, auth_client):
        """After signup a Foundation-tier user should have > 0 available tokens."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/usage")
        body = response.json()
        # Foundation tier allocates weekly_tokens = 1000 on signup
        assert body["available_tokens"] > 0

    def test_usage_response_has_daily_info(self, auth_client):
        """Response must contain daily usage info."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/usage")
        body = response.json()
        assert "daily_tokens_used" in body
        assert "daily_token_limit" in body

    def test_total_used_is_zero_for_new_user(self, auth_client):
        """A brand new user should have zero total_used_tokens."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/usage")
        body = response.json()
        assert body["total_used_tokens"] == 0


class TestTokenTransactions:
    """Tests for GET /api/v1/tokens/transactions."""

    def test_unauthenticated_returns_401(self, client):
        """Token transactions endpoint requires authentication."""
        response = client.get("/api/v1/tokens/transactions")
        assert response.status_code == 401

    def test_authenticated_returns_200(self, auth_client):
        """Authenticated user receives HTTP 200."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/transactions")
        assert response.status_code == 200

    def test_response_has_items_key(self, auth_client):
        """Response body must contain an 'items' list."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/transactions")
        body = response.json()
        assert "items" in body
        assert isinstance(body["items"], list)

    def test_response_has_pagination_keys(self, auth_client):
        """Response must include 'limit' and 'offset' pagination fields."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/transactions")
        body = response.json()
        assert "limit" in body
        assert "offset" in body

    def test_default_limit_is_50(self, auth_client):
        """Default limit should match the route default of 50."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/transactions")
        assert response.json()["limit"] == 50

    def test_custom_limit_accepted(self, auth_client):
        """Custom limit query parameter is respected."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/transactions?limit=10")
        assert response.json()["limit"] == 10

    def test_custom_offset_accepted(self, auth_client):
        """Custom offset query parameter is respected."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/transactions?offset=5")
        assert response.json()["offset"] == 5

    def test_limit_upper_bound_enforced(self, auth_client):
        """Limit above 100 must be rejected (422)."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/transactions?limit=200")
        assert response.status_code == 422

    def test_limit_lower_bound_enforced(self, auth_client):
        """Limit of 0 must be rejected (422)."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/transactions?limit=0")
        assert response.status_code == 422

    def test_negative_offset_rejected(self, auth_client):
        """Negative offset must be rejected (422)."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/transactions?offset=-1")
        assert response.status_code == 422

    def test_new_user_has_signup_bonus_transaction(self, auth_client):
        """A newly signed-up user should have at least one signup_bonus transaction."""
        test_client, _ = auth_client
        response = test_client.get("/api/v1/tokens/transactions")
        items = response.json()["items"]
        transaction_types = [t.get("transaction_type", "") for t in items]
        assert "signup_bonus" in transaction_types
