"""Token rate limiter for OxyGent system.

This module provides token bucket rate limiting functionality with both
synchronous and asynchronous token acquisition methods.
"""

import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class TokenLimiter:
    """Token bucket rate limiter implementation.
    
    Provides thread-safe token-based rate limiting with both sync and async
    interfaces. Uses the token bucket algorithm to control request rates.
    
    Attributes:
        rate (float): Token refill rate (tokens per second)
        capacity (int): Maximum number of tokens in the bucket
        tokens (float): Current number of available tokens
        last_refill_time (float): Last time tokens were refilled
        _lock (asyncio.Lock): Async lock for thread-safe operations
    """
    
    def __init__(self, rate: float = 1.0, capacity: int = 10):
        """Initialize the token limiter.
        
        Args:
            rate: Token refill rate (tokens per second)
            capacity: Maximum number of tokens in the bucket
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_refill_time = time.time()
        self._lock = asyncio.Lock()
        
    def _refill_tokens(self):
        """Refill tokens based on elapsed time."""
        current_time = time.time()
        elapsed = current_time - self.last_refill_time
        tokens_to_add = elapsed * self.rate
        
        if tokens_to_add > 0:
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self.last_refill_time = current_time
            
    def acquire_sync(self, tokens: int = 1) -> bool:
        """Synchronously acquire tokens.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens were acquired, False if not enough tokens available
        """
        self._refill_tokens()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            logger.debug(f"Acquired {tokens} tokens. Remaining: {self.tokens}")
            return True
        else:
            logger.debug(f"Failed to acquire {tokens} tokens. Available: {self.tokens}")
            return False
            
    async def acquire_async(self, tokens: int = 1) -> bool:
        """Asynchronously acquire tokens.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens were acquired, False if not enough tokens available
        """
        async with self._lock:
            self._refill_tokens()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(f"Acquired {tokens} tokens. Remaining: {self.tokens}")
                return True
            else:
                logger.debug(f"Failed to acquire {tokens} tokens. Available: {self.tokens}")
                return False
                
    async def wait_for_tokens(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """Wait until the specified number of tokens are available.
        
        Args:
            tokens: Number of tokens to wait for
            timeout: Maximum time to wait in seconds (None for no timeout)
            
        Returns:
            True if tokens were acquired, False if timeout occurred
        """
        start_time = time.time()
        
        while True:
            if await self.acquire_async(tokens):
                return True
                
            # Calculate wait time needed
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.rate
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    logger.warning(f"Timeout waiting for {tokens} tokens")
                    return False
                wait_time = min(wait_time, timeout - elapsed)
            
            logger.debug(f"Waiting {wait_time:.2f}s for {tokens} tokens")
            await asyncio.sleep(wait_time)
            
    def get_available_tokens(self) -> float:
        """Get the current number of available tokens.
        
        Returns:
            Current number of tokens available
        """
        self._refill_tokens()
        return self.tokens
        
    def get_wait_time(self, tokens: int = 1) -> float:
        """Calculate the time needed to wait for the specified number of tokens.
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Time in seconds needed to wait
        """
        self._refill_tokens()
        
        if self.tokens >= tokens:
            return 0.0
            
        tokens_needed = tokens - self.tokens
        return tokens_needed / self.rate
        
    def reset(self):
        """Reset the token bucket to full capacity."""
        self.tokens = float(self.capacity)
        self.last_refill_time = time.time()
        logger.info(f"Token limiter reset to {self.capacity} tokens")
        
    def update_rate(self, rate: float):
        """Update the token refill rate.
        
        Args:
            rate: New token refill rate (tokens per second)
        """
        self.rate = rate
        logger.info(f"Token limiter rate updated to {rate} tokens/second")
        
    def update_capacity(self, capacity: int):
        """Update the token bucket capacity.
        
        Args:
            capacity: New maximum number of tokens
        """
        self.capacity = capacity
        self.tokens = min(self.tokens, float(capacity))
        logger.info(f"Token limiter capacity updated to {capacity} tokens")


class RateLimitManager:
    """Manager for multiple token limiters.
    
    Manages rate limiters for different entities in the OxyGent system.
    """
    
    def __init__(self):
        """Initialize the rate limit manager."""
        self._limiters: dict[str, TokenLimiter] = {}
        self._enabled = False
        
    def enable(self):
        """Enable rate limiting."""
        self._enabled = True
        logger.info("Rate limiting enabled")
        
    def disable(self):
        """Disable rate limiting."""
        self._enabled = False
        logger.info("Rate limiting disabled")
        
    def is_enabled(self) -> bool:
        """Check if rate limiting is enabled.
        
        Returns:
            True if rate limiting is enabled
        """
        return self._enabled
        
    def create_limiter(self, name: str, rate: float = 1.0, capacity: int = 10) -> TokenLimiter:
        """Create a new token limiter.
        
        Args:
            name: Name of the limiter
            rate: Token refill rate
            capacity: Token bucket capacity
            
        Returns:
            Created token limiter
        """
        limiter = TokenLimiter(rate, capacity)
        self._limiters[name] = limiter
        logger.info(f"Created token limiter '{name}' with rate={rate}, capacity={capacity}")
        return limiter
        
    def get_limiter(self, name: str) -> Optional[TokenLimiter]:
        """Get a token limiter by name.
        
        Args:
            name: Name of the limiter
            
        Returns:
            Token limiter if found, None otherwise
        """
        return self._limiters.get(name)
        
    def remove_limiter(self, name: str):
        """Remove a token limiter.
        
        Args:
            name: Name of the limiter to remove
        """
        if name in self._limiters:
            del self._limiters[name]
            logger.info(f"Removed token limiter '{name}'")
            
    def check_rate_limit(self, name: str, tokens: int = 1) -> bool:
        """Check if rate limit allows the operation.
        
        Args:
            name: Name of the limiter
            tokens: Number of tokens to acquire
            
        Returns:
            True if operation is allowed, False otherwise
        """
        if not self._enabled:
            return True
            
        limiter = self._limiters.get(name)
        if limiter is None:
            return True
            
        return limiter.acquire_sync(tokens)
        
    async def check_rate_limit_async(self, name: str, tokens: int = 1) -> bool:
        """Async check if rate limit allows the operation.
        
        Args:
            name: Name of the limiter
            tokens: Number of tokens to acquire
            
        Returns:
            True if operation is allowed, False otherwise
        """
        if not self._enabled:
            return True
            
        limiter = self._limiters.get(name)
        if limiter is None:
            return True
            
        return await limiter.acquire_async(tokens)


# Global rate limit manager instance
_global_rate_limit_manager = RateLimitManager()


def get_rate_limit_manager() -> RateLimitManager:
    """Get the global rate limit manager.
    
    Returns:
        Global rate limit manager instance
    """
    return _global_rate_limit_manager