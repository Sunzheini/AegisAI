import pytest
import asyncio
import json
import async_timeout


class TestRedisPubSubIntegration:
    """Test Redis Pub/Sub functionality with database 2."""

    @pytest.mark.asyncio
    async def test_redis_connection_db2(self, redis_client):
        """Test that we're connected to the correct database."""
        # Get current database info
        client_info = await redis_client.client_info()
        assert client_info['db'] == 2, f"Should be connected to database 2, but got {client_info['db']}"

        # Test basic operations to verify database isolation
        await redis_client.set("test_key", "test_value")
        value = await redis_client.get("test_key")
        assert value == "test_value"

    @pytest.mark.asyncio
    async def test_pub_sub_basic(self, redis_client):
        """Test basic publish/subscribe functionality."""
        test_channel = "test:channel:1"
        test_message = "Hello, Redis Pub/Sub!"

        messages_received = []

        # Create pubsub inside the test
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(test_channel)

        async def message_listener():
            try:
                async with async_timeout.timeout(2):
                    async for message in pubsub.listen():
                        if message['type'] == 'message':
                            messages_received.append(message['data'])
                            return  # Exit after first message
            except asyncio.TimeoutError:
                pass

        # Start listening
        listener_task = asyncio.create_task(message_listener())

        # Wait a bit for subscription to be active
        await asyncio.sleep(0.1)

        # Publish message
        subscribers = await redis_client.publish(test_channel, test_message)
        assert subscribers == 1, f"Should have 1 subscriber, got {subscribers}"

        # Wait for message with timeout
        try:
            await asyncio.wait_for(listener_task, timeout=3.0)
        except asyncio.TimeoutError:
            # If timeout, cancel the task
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

        # Cleanup
        await pubsub.unsubscribe(test_channel)
        await pubsub.aclose()

        assert len(messages_received) == 1
        assert messages_received[0] == test_message

    @pytest.mark.asyncio
    async def test_json_message_pubsub(self, redis_client):
        """Test publishing JSON messages."""
        channel = "test:json:messages"
        test_data = {
            "user_id": 123,
            "action": "login",
            "timestamp": "2024-01-01T00:00:00Z"
        }

        messages_received = []

        # Create pubsub inside the test
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)

        async def json_listener():
            try:
                async with async_timeout.timeout(2):
                    async for message in pubsub.listen():
                        if message['type'] == 'message':
                            messages_received.append(message['data'])
                            return  # Exit after first message
            except asyncio.TimeoutError:
                pass

        listener_task = asyncio.create_task(json_listener())
        await asyncio.sleep(0.1)

        # Publish JSON
        await redis_client.publish(channel, json.dumps(test_data))

        # Wait for message with timeout
        try:
            await asyncio.wait_for(listener_task, timeout=3.0)
        except asyncio.TimeoutError:
            # If timeout, cancel the task
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

        # Cleanup
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()

        assert len(messages_received) == 1
        parsed_data = json.loads(messages_received[0])
        assert parsed_data["user_id"] == 123
        assert parsed_data["action"] == "login"


class TestRedisWithAuthentication:
    """Test Redis features that might require authentication."""

    @pytest.mark.asyncio
    async def test_authenticated_pubsub(self, redis_client, authenticated_client):
        """Test Pub/Sub in context of authenticated user."""
        channel = "user:123:notifications"
        test_message = "Welcome back!"

        # Simulate user-specific channel
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)

        messages_received = []

        async def user_listener():
            try:
                async with async_timeout.timeout(2):
                    async for message in pubsub.listen():
                        if message['type'] == 'message':
                            messages_received.append(message['data'])
                            return  # Exit after first message
            except asyncio.TimeoutError:
                pass

        listener_task = asyncio.create_task(user_listener())
        await asyncio.sleep(0.1)

        # In a real scenario, this might be called by your API
        subscribers = await redis_client.publish(channel, test_message)
        assert subscribers == 1

        # Wait for message with timeout
        try:
            await asyncio.wait_for(listener_task, timeout=3.0)
        except asyncio.TimeoutError:
            # If timeout, cancel the task
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

        # Cleanup
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()

        assert len(messages_received) == 1
