class SingletonInterface:
    """A singleton interface to ensure only one instance of a class is created."""

    _INSTANCE = None
    _INITIALIZED = False

    def __new__(cls, *args, **kwargs):
        if cls._INSTANCE is None:
            cls._INSTANCE = super().__new__(cls)
        return cls._INSTANCE

    def __init__(self, *args, **kwargs):
        if not self._INITIALIZED:
            self._INITIALIZED = True

            # Call the actual initialization logic in subclass
            self._initialize(*args, **kwargs)

    def _initialize(self, *args, **kwargs):
        """Override this method in subclasses for initialization logic."""
        pass
