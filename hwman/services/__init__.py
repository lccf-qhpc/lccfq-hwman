

from abc import ABC, abstractmethod


class Service(ABC):
    """
    Base class for all services in the system.
    """

    @abstractmethod
    def cleanup(self):
        ...






