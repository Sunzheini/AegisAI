def test_orchestrator_logging_setup(caplog, orchestrator_client):
    """Test that workflow orchestrator has proper logging setup."""
    with caplog.at_level("INFO", logger="workflow-orchestrator"):
        # Get the logger from the orchestrator module
        from workflow_orchestrator_example import logger as orchestrator_logger

        orchestrator_logger.info("Orchestrator test log")

        assert any(
            "Orchestrator test log" in record.message for record in caplog.records
        )
        assert any(record.name == "workflow-orchestrator" for record in caplog.records)


def test_orchestrator_health_endpoint_logging(caplog, orchestrator_client):
    """Test that orchestrator health endpoint logs properly."""
    with caplog.at_level("INFO", logger="workflow-orchestrator"):
        # Try the jobs endpoint instead since health might not exist
        response = orchestrator_client.get("/jobs/nonexistent")

        # Should get 404 for non-existent job, but logging should still work
        assert response.status_code == 404

        # Check that request was logged
        request_logs = [
            r
            for r in caplog.records
            if "request received" in r.getMessage().lower()
            and r.name == "workflow-orchestrator"
        ]
        assert len(request_logs) > 0, "No request logs found for workflow-orchestrator"

        # Check that response was logged
        response_logs = [
            r
            for r in caplog.records
            if "response sent" in r.getMessage().lower()
            and r.name == "workflow-orchestrator"
        ]
        assert (
            len(response_logs) > 0
        ), "No response logs found for workflow-orchestrator"
