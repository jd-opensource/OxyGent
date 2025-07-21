import logging
import os

from elasticsearch import AsyncElasticsearch

from .base_es import BaseEs

logger = logging.getLogger(__name__)


class JesEs(BaseEs):
    def __init__(self, hosts, user, password, maxsize=200, timeout=20):
        try:
            self.client = AsyncElasticsearch(
                hosts, http_auth=(user, password), maxsize=maxsize, timeout=timeout
            )
        except Exception as e:
            logger.error(e)
            self.client = None

    async def create_index(self, index_name: str, body: dict) -> dict:
        """Create a new index in Elasticsearch with the specified configuration.

        Args:
            index_name: Name of the index to create
            body: Index configuration including mappings, settings, etc.

        Returns:
            Result of the index creation operation

        Raises:
            Exception: If the index name is empty or the body is empty
        """
        # Validate parameters
        if not index_name or not index_name.strip():
            raise ValueError("The name of the index can not be empty")
        if not body:
            raise ValueError("The config of the index ca not be empty")

        # Create the index if not exists
        if not await self._index_exists(index_name):
            return await self._create_new_index(index_name, body)

        # If the index exists, return None or raise error
        return None  # or raise IndexAlreadyExistsError(f"Index '{index_name}' exist")

    async def _index_exists(self, index_name: str) -> bool:
        """Check if the index exists.

        Args:
            index_name (str): The name of the index should be checked

        Returns:
            bool: If the index exists
        """
        return await self.client.indices.exists(index=index_name)

    async def _create_new_index(self, index_name: str, body: dict) -> dict:
        """Create new index.

        Args:
            index_name (str): The name of the index to create
            body (dict): The config of the index

        Returns:
            dict: The result of the create operation
        """
        return await self.client.indices.create(index=index_name, body=body)

    async def index(self, index_name, doc_id, body):
        return await self.client.index(index=index_name, id=doc_id, body=body)

    async def update(self, index_name, doc_id, body):
        return await self.client.update(index=index_name, id=doc_id, body={"doc": body})

    async def search(self, index_name, body):
        return await self.client.search(index=index_name, body=body)

    async def exists(self, index_name, doc_id):
        return await self.client.exists(index=index_name, id=doc_id)

    async def close(self):
        return await self.client.close()


async def main():
    hosts = os.getenv("ES_HOST_LIST")
    user = os.getenv("ES_TEST_USER")
    password = os.getenv("ES_TEST_PASSWORD")

    redis = JesEs(hosts, user, password)
    index_name = "mas_doc_test"

    print(
        await redis.index(
            index_name, doc_id="doc1", body={"title": "Hello", "content": "World"}
        )
    )
    print(await redis.search(index_name, {"query": {"match": {"title": "Hello"}}}))
    print(await redis.exists(index_name, doc_id="doc1"))
    print(
        await redis.update(
            index_name, doc_id="doc1", body={"title": "Hello", "content": "World!"}
        )
    )
    await redis.close()
