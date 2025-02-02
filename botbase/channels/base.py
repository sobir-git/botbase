from abc import ABC, abstractmethod

from fastapi import APIRouter, BackgroundTasks, Request


class BaseChannel(ABC):
    def __init__(self, name: str):
        self.name = name
        self.router = APIRouter(prefix=f"/webhook/{self.name}")

    @abstractmethod
    def register_routes(self, app):
        """
        Register the channel-specific routes to the FastAPI app.
        """
        pass

    @abstractmethod
    async def process_request(self, request: Request, background_tasks: BackgroundTasks):
        """
        Process an incoming webhook request.
        """
        pass

    @abstractmethod
    def close(self):
        """
        Close the channel (e.g., flush pending messages). Non-blocking.
        """
        pass
