import pytest
import asyncio


class TestRedisRouterEndpoints:
    """Test the Redis router endpoints."""

    def test_redis_health_endpoint(self, client):
        """Test Redis health check endpoint."""
        response = client.get("/redis/health")

        # Might be 503 if Redis isn't running, or 200 if it is
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database"] == 2

    def test_publish_endpoint(self, client):
        """Test the publish endpoint."""
        response = client.post(
            "/redis/publish",
            params={"channel": "test:channel", "message": "test message"},
        )

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "published"
            assert data["channel"] == "test:channel"
            assert data["database"] == 2
        elif response.status_code == 503:
            # Redis is unavailable - skip or handle accordingly
            pytest.skip("Redis unavailable")

    def test_publish_endpoint_validation(self, client):
        """Test publish endpoint validation."""
        # Test empty channel
        response = client.post(
            "/redis/publish", params={"channel": "", "message": "test"}
        )
        assert response.status_code == 400

        # Test empty message
        response = client.post(
            "/redis/publish", params={"channel": "test", "message": ""}
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_pubsub_integration(self, redis_client):
        """Test the actual Pub/Sub functionality."""
        # This tests the business logic without HTTP layer
        channel = "test:integration"
        test_message = "integration test message"

        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)

        messages_received = []

        async def listener():
            try:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        messages_received.append(message["data"])
                        break
            except Exception:
                pass

        listener_task = asyncio.create_task(listener())
        await asyncio.sleep(0.1)

        # This simulates what the endpoint does
        subscribers = await redis_client.publish(channel, test_message)
        assert subscribers == 1

        # Wait a bit for the message
        await asyncio.sleep(0.5)

        # Cancel the listener
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass

        # Cleanup
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()

        assert len(messages_received) == 1
        assert messages_received[0] == test_message
