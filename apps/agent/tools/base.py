"""
Base tool class for AI agent function calling.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """
    Base class for all agent tools.
    Each tool maps to an OpenAI function that the agent can call.
    """
    
    # Tool metadata - must be set by subclasses
    name: str = ""
    description: str = ""
    
    # Roles that can use this tool
    allowed_roles: list = ["customer", "client", "staff"]
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """
        Return JSON schema for tool parameters.
        
        Returns:
            JSON schema dictionary for OpenAI function parameters
        """
        pass
    
    @abstractmethod
    def execute(self, user, role: str, **kwargs) -> Dict[str, Any]:
        """
        Execute the tool with given parameters.
        
        Args:
            user: The authenticated user
            role: User's role (customer, client, staff)
            **kwargs: Tool parameters
            
        Returns:
            Result dictionary with success status and data
        """
        pass
    
    def to_openai_function(self) -> Dict[str, Any]:
        """
        Convert to OpenAI function calling format.
        
        Returns:
            Dictionary in OpenAI tools format
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }
    
    def can_use(self, role: str) -> bool:
        """
        Check if a role can use this tool.
        
        Args:
            role: User's role
            
        Returns:
            True if role can use this tool
        """
        return role in self.allowed_roles
