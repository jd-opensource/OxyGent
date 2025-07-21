"""base_es.py Base Elasticsearch Database Class Module.

This file defines the abstract base class for Elasticsearch database services,
inheriting from BaseDB and providing the interface contract for ES operations.
"""

from abc import ABC, abstractmethod

from oxygent.databases.base_db import BaseDB


class BaseEs(BaseDB, ABC):
    """Abstract base class for Elasticsearch database services.

    This class inherits from BaseDB to get retry functionality and error handling, while
    defining the essential interface that all Elasticsearch implementations must
    provide. All methods are abstract and must be implemented by subclasses.
    """

    @abstractmethod
    async def create_index(self, index_name, body):
        """Create a new index in Elasticsearch with the specified configuration.

        Args:
            index_name: Name of the index to create
            body: Index configuration including mappings, settings, etc.

        Returns:
            Result of the index creation operation

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def index(self, index_name, doc_id, body):
        """Index a document in Elasticsearch.

        This method adds or updates a document in the specified index with the given ID.

        Args:
            index_name: Name of the index to store the document
            doc_id: Unique identifier for the document
            body: Document content to be indexed

        Returns:
            Result of the indexing operation

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def update(self, index_name, doc_id, body):
        pass

    @abstractmethod
    async def search(self, index_name, body):
        """Execute a search query against an Elasticsearch index.

        Args:
            index_name: Name of the index to search
            body: Search query body containing filters, aggregations, etc.

        Returns:
            Search results matching the query criteria

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def exists(self, index_name, doc_id):
        """Check if a document exists in the specified index.

        Args:
            index_name: Name of the index to check
            doc_id: Document ID to verify existence

        Returns:
            Boolean indicating whether the document exists

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass

    @abstractmethod
    async def close(self):
        """Close the Elasticsearch client connection and clean up resources.

        This method should be called when the ES client is no longer needed
        to properly release connections and resources.

        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        pass
