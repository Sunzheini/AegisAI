def test_validation_service_logging_setup(caplog, validation_client):
    """Test that validation service has proper logging setup."""
    with caplog.at_level("INFO", logger="validation-service"):
        # Get the logger from the validation service module
        from validation_worker_service import logger as validation_logger
        validation_logger.info("Validation service test log")

        assert any("Validation service test log" in record.message for record in caplog.records)
        assert any(record.name == "validation-service" for record in caplog.records)


def test_validation_service_health_endpoint_logging(caplog, validation_client):
    """Test that validation service health endpoint logs properly."""
    with caplog.at_level("INFO", logger="validation-service"):
        response = validation_client.get("/health")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Service"] == "validation-service"

        # Check that request was logged
        request_logs = [
            r for r in caplog.records
            if "request received" in r.getMessage().lower() and r.name == "validation-service"
        ]
        assert len(request_logs) > 0, "No request logs found for validation-service"

        # Check that response was logged
        response_logs = [
            r for r in caplog.records
            if "response sent" in r.getMessage().lower() and r.name == "validation-service"
        ]
        assert len(response_logs) > 0, "No response logs found for validation-service"
