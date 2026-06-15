from abc import ABC

class BaseService:
    """
    Abstract base class for all internal services.

    Ensures that every service has a reference back to the orchestrator 
    for cross-service communication.
    """
    def __init__(self, orchestrator=None):
        """
        Initializes the service.

        Args:
            orchestrator: The FacadeSessionOrchestrator instance.
        """
        self.orchestrator = orchestrator
