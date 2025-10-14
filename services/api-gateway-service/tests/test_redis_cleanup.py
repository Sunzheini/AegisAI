import pytest


@pytest.mark.asyncio
async def test_redis_is_clean_between_tests(redis_client):
    """Test that Redis is clean between test runs."""
    # This should be empty if cleanup worked
    keys = await redis_client.keys("*")
    print(f"Keys in Redis after cleanup: {keys}")
    assert len(keys) == 0, f"Redis not clean! Found keys: {keys}"


@pytest.mark.asyncio
async def test_redis_cleanup_works(redis_client):
    """Test that the cleanup fixture actually works."""
    # Add data
    await redis_client.set("should_be_cleaned", "data")
    await redis_client.hset("should_be_cleaned_hash", "field", "value")

    # Verify data was added
    assert await redis_client.get("should_be_cleaned") == "data"
