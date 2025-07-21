"""base_vector_db.py Base Vector Database Class Module.

This file defines the abstract base class for vector database services, inheriting from
BaseDB and providing the interface contract for Redis operations.
"""

import logging
from abc import ABC, abstractmethod

from oxygent.databases.base_db import BaseDB

logger = logging.getLogger(__name__)


class BaseVectorDB(BaseDB, ABC):
    @abstractmethod
    async def create_space(self, index_name, body):
        pass

    @abstractmethod
    async def query_search(self, index_name, body):
        pass
