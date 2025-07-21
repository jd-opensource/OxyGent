"""vector_db.py Vearch Vector Database Implementation Module.

This file implements a comprehensive interface for Vearch vector database operations,
providing functionality for vector storage, similarity search, and tool retrieval with
embedding support and advanced filtering capabilities.
"""

import asyncio
import base64
import json
import random

import httpx
import numpy as np
import pandas as pd

from oxygent.databases.db_vector.base_vector_db import BaseVectorDB
from oxygent.embedding_cache import EmbeddingCache


class VectorToolAsync(object):
    """Asynchronous toolkit for low-level Vearch database operations.

    This class provides HTTP-based communication with Vearch master and router nodes,
    handling database creation, space management, document operations, and search
    queries. All operations are asynchronous and use httpx for HTTP communication.
    """

    def __init__(self):
        pass

    @staticmethod
    async def create_db(master_url, db_name):
        """Create a new database in Vearch.

        Args:
            master_url: URL of the Vearch master node
            db_name: Name of the database to create

        Returns:
            Dict[str, Any]: JSON response from the Vearch API

        NOTE:
            The following functions would obey the same format of return value if not mentioned
        """
        url = f"{master_url}/db/_create"
        data = {"name": db_name}
        async with httpx.AsyncClient() as client:
            response = await client.put(url, json=data)
            return response.json()

    @staticmethod
    async def create_space(master_url, db_name, space_config):
        """Create a new space (table) within a database.

        Args:
            master_url: URL of the Vearch master node
            db_name: Name of the target database
            space_config: Configuration dictionary for the space including schema and indexing

        Returns:
            Dict[str, Any]: API Response
        """
        url = f"{master_url}/space/{db_name}/_create"
        async with httpx.AsyncClient() as client:
            response = await client.put(url, json=space_config)
            return response.json()

    @staticmethod
    async def drop_space(master_url, db_name, space_name):
        """Delete a space from the database.

        Args:
            master_url: URL of the Vearch master node
            db_name: Name of the database containing the space
            space_name: Name of the space to delete

        Returns:
            str: Text response from the Vearch API
        """
        url = f"{master_url}/space/{db_name}/{space_name}"
        async with httpx.AsyncClient() as client:
            response = await client.delete(url)
            return response.text

    @staticmethod
    def generate_random_str(randomlength=10):
        """Generate a random string for document IDs.

        Args:
            randomlength: Length of the random string

        Returns:
            str: Random alphanumeric string
        """
        base_str = "ABCDEFGHIGKLMNOPQRSTUVWXYZabcdefghigklmnopqrstuvwxyz0123456789"
        return "".join(random.choices(base_str, k=randomlength))

    @staticmethod
    async def insert_batch(db_name, space_name, router_url, data_list):
        """Insert multiple documents in batch using bulk API.

        Args:
            db_name: Name of the target database
            space_name: Name of the target space
            router_url: URL of the Vearch router node
            data_list: Bulk data in NDJSON format

        Returns:
            str: Text response from the Vearch API
        """
        url = f"{router_url}/{db_name}/{space_name}/_bulk"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data_list)
            return response.text

    @staticmethod
    async def insert_single(db_name, space_name, router_url, data_list):
        """Insert a single document.

        Args:
            db_name: Name of the target database
            space_name: Name of the target space
            router_url: URL of the Vearch router node
            data_list: Document data in JSON format

        Returns:
            str: Text response from the Vearch API
        """
        url = f"{router_url}/{db_name}/{space_name}"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data_list)
            return response.text

    @staticmethod
    async def view_space(db_name, space_name, master_url):
        """Get space information and configuration.

        Args:
            db_name: Name of the database
            space_name: Name of the space
            master_url: URL of the Vearch master node

        Returns:
            Dict[str, Any]: JSON response containing space details
        """
        url = f"{master_url}/space/{db_name}/{space_name}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            return response.json()

    @staticmethod
    async def check_info(db_name, space_name, master_url):
        """Check space information and status.

        Args:
            db_name: Name of the database
            space_name: Name of the space
            master_url: URL of the Vearch master node

        Returns:
            Dict[str, Any]: JSON response containing space status
        """
        url = f"{master_url}/space/{db_name}/{space_name}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            return response.json()

    @staticmethod
    async def get_cluster_health(master_url):
        """Get cluster health information including document counts.

        Args:
            master_url: URL of the Vearch master node

        Returns:
            Dict[str, Any]: JSON response containing cluster health data
        """
        url = f"{master_url}/_cluster/health"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            return response.json()

    @staticmethod
    async def check_doc_num(master_url, db_name, space_name):
        """Get the number of documents in a specific space.

        Args:
            master_url: URL of the Vearch master node
            db_name: Name of the database
            space_name: Name of the space

        Returns:
            int: Number of documents, or -1 if space not found

        NOTE:
            This assumes the response structure is a list;
            may need adjustment based on actual API response
        """
        his = await VectorToolAsync.get_cluster_health(master_url)
        doc_num = -1
        for it in his:
            if it["db_name"] == db_name:
                for more_info in it["spaces"]:
                    if space_name == more_info["name"]:
                        return more_info["doc_num"]
        return doc_num

    @staticmethod
    async def search_by_filter(db_name, space_name, router_url, data_list):
        """Search documents using filter conditions only.

        Args:
            db_name: Name of the database
            space_name: Name of the space
            router_url: URL of the Vearch router node
            data_list: Search query with filter conditions

        Returns:
            Dict[str, Any]: JSON response containing search results
        """
        url = f"{router_url}/{db_name}/{space_name}/_search"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data_list)
            return response.json()

    @staticmethod
    async def emb_search(db_name, space_name, router_url, emb, retrieval_nums, fields):
        """Perform vector similarity search using embeddings.

        Args:
            db_name: Name of the database
            space_name: Name of the space
            router_url: URL of the Vearch router node
            emb: Embedding vector for similarity search
            retrieval_nums: Maximum number of results to return
            fields: List of fields to return in results

        Returns:
            Dict[str, Any]: JSON response containing similarity search results
        """
        url = f"{router_url}/{db_name}/{space_name}/_search"
        search_query = {
            "query": {
                "sum": [
                    {"field": "vector", "feature": [float(e) for e in list(emb)[0]]}
                ],
            },
            "fields": fields,
            "is_brute_search": 1,
            "size": retrieval_nums,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=search_query)
            return response.json()

    @staticmethod
    async def filter_and_emb_search(
        db_name, space_name, router_url, emb, retrieval_nums, fields, filter={}
    ):
        """Perform hybrid search combining vector similarity and filter conditions.

        Args:
            db_name: Name of the database
            space_name: Name of the space
            router_url: URL of the Vearch router node
            emb: Embedding vector for similarity search
            retrieval_nums: Maximum number of results to return
            fields: List of fields to return in results
            filter: Dictionary of filter conditions

        Returns:
            Dict[str, Any]: JSON response containing filtered similarity search results
        """
        url = f"{router_url}/{db_name}/{space_name}/_search"
        filter_lis = []
        for k, v in filter.items():
            filter_lis.append({"term": {k: [v], "operator": "and"}})
        search_query = {
            "query": {
                "sum": [
                    {"field": "vector", "feature": [float(e) for e in list(emb)[0]]}
                ],
                "filter": filter_lis,
            },
            "fields": fields,
            "is_brute_search": 1,
            "size": retrieval_nums,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=search_query)
            return response.json()

    @staticmethod
    async def delete_by_docid(db_name, space_name, router_url, doc_id):
        """Delete a document by its ID.

        Args:
            db_name: Name of the database
            space_name: Name of the space
            router_url: URL of the Vearch router node
            doc_id: ID of the document to delete

        Returns:
            str: Text response from the Vearch API
        """
        url = f"{router_url}/{db_name}/{space_name}/{doc_id}"
        async with httpx.AsyncClient() as client:
            response = await client.delete(url)
            return response.text

    @staticmethod
    def retrieval2df(res):
        """Convert Vearch search results to pandas DataFrame.

        Args:
            res: JSON response from Vearch search API

        Returns:
            pd.DataFrame: pandas.DataFrame containing flattened search results
        """
        df_list = []
        result_data = res["hits"]["hits"]
        for item in result_data:
            item_dict = {k: v for k, v in item.items() if k != "_source"}
            item_dict.update(item["_source"])
            df_list.append(item_dict)
        return pd.DataFrame(df_list)

    @staticmethod
    def check_search_result(res_json):
        """Check if search results contain valid data.

        Args:
            res_json: JSON response from Vearch search API

        Returns:
            bool: Boolean indicating if results are valid and non-empty

        NOTE: Examples of responses:
            - Normal: {'took': 1, 'timed_out': False, '_shards': {'total': 1, 'successful': 1}, 'hits': {'total': 2, 'max_score': 0.502149224281311, 'hits': [...]}}
            - Table doesn't exist: {'error': {'root_cause': [{'type': '', 'reason': 'dbName or spaceName param not build db or space'}], 'type': '', 'reason': 'dbName or spaceName param not build db or space'}, 'status': 400}
            - No results: {'took': 0, 'timed_out': False, '_shards': {'total': 1, 'successful': 1}, 'hits': {'total': 0, 'max_score': -1}}
        """
        if "error" in res_json:
            return False
        if res_json.get("hits", {}).get("total", 0) == 0:
            return False
        else:
            return True


class VearchDB(BaseVectorDB):
    """High-level Vearch database client with embedding support and tool management.

    This class provides a comprehensive interface for Vearch operations, including
    automatic embedding generation, tool retrieval systems, and business logic
    implementations. It supports both system-level tool management and user-level
    document operations.
    """

    def __init__(self, config):
        """Initialize Vearch database client.

        Args:
            config: Configuration dictionary containing database connection details,
                   space names, and optional embedding model configuration

        NOTE:
            If 'tool_df_space_name' is not in config, this is not a system-level instance.
            System usage must provide this configuration.
        """
        self.config = VearchConfig(config)
        self.vearch_tools = VectorToolAsync()  # Initialize vector datebase tools
        # Low level operations are not provided in this class

        if (
            "tool_df_space_name" not in config
        ):  # Not a system instance; the config should be provided in system instance
            pass

        if "embedding_model_url" in config:  # Initalize  embedding function
            emb_model = EmbeddingModel(url=self.config.embedding_model_url)
            self.emb_func = emb_model.get_embeddings_async
        else:
            self.emb_func = None

    async def create_space(self, space_config):
        """Create a new space with custom configuration.

        Args:
            space_config: Space configuration dictionary

        Return:
            Dict[str, Any]: API Response
        """
        res = await self.vearch_tools.create_space(
            self.config.master_url, self.config.db_name, space_config
        )
        return res

    async def create_tool_df_space(self, tool_df_space_name):
        """Create system-specific tool dataframe space with predefined schema.

        This method creates a specialized space for storing tool information
        with vector embeddings for similarity search and metadata fields
        for filtering by application and agent names.

        Args:
            tool_df_space_name: Name of the tool space to create
        """
        # System-specific space configuration for tool storage
        space_config0 = {
            "name": tool_df_space_name,
            "partition_num": 1,
            "replica_num": 3,
            "engine": {
                "index_size": 70000,
                "id_type": "String",
                "retrieval_type": "IVFPQ",
                "retrieval_param": {
                    "metric_type": "InnerProduct",
                    "ncentroids": 256,
                    "nsubvector": 32,
                },
            },
            "properties": {
                "app_name": {"type": "string", "index": True},
                "agent_name": {"type": "string", "index": True},
                "tool_name": {"type": "string", "index": True},
                "tool_desc": {
                    "type": "string",
                },
                "vector": {"dimension": 1024, "type": "vector"},
                "remark": {
                    "type": "string",
                },
            },
        }
        res = await self.vearch_tools.create_space(
            self.config.master_url, self.config.db_name, space_config0
        )
        return res

    async def drop_space(self, space_name):
        """Delete a space from the database.

        Args:
            space_name: Name of the space to delete
        """
        res = await self.vearch_tools.drop_space(
            self.config.master_url, self.config.db_name, space_name
        )
        return res

    async def query_search(
        self, space_name, query, retrieval_nums, fields=[], threshold=None
    ):
        """Perform semantic search based on text query with optional threshold
        filtering.

        Args:
            space_name: Name of the space to search
            query: Text query to search for
            retrieval_nums: Maximum number of results to return
            fields: List of fields to include in results
            threshold: Optional score threshold for filtering results

        Returns:
            pd.DataFrame: pandas.DataFrame containing search results

        Raises:
            ValueError: If embedding function is not specified

        NOTE:
            The Threshold could not be specified
        """
        # Generate embedding for the query
        if self.emb_func:
            emb = await self.emb_func([query])
        else:
            raise ValueError("Please specify the embedding function")

        # Perform vector similarity search
        res = await self.vearch_tools.emb_search(
            self.config.db_name,
            space_name=space_name,
            router_url=self.config.router_url,
            emb=emb,
            retrieval_nums=retrieval_nums,
            fields=fields,
        )

        # Process result and apply threshold if provided
        if self.vearch_tools.check_search_result(res):
            res_df = self.vearch_tools.retrieval2df(res)
            if threshold:
                res_df = res_df[res_df["_score"] > threshold].reset_index(drop=True)
        else:
            res_df = pd.DataFrame()

        return res_df

    async def query_search_batch(
        self, space_name, query_list, retrieval_nums, fields=[]
    ):
        """Perform batch semantic search for multiple queries.

        Args:
            space_name: Name of the space to search
            query_list: List of text queries to search for
            retrieval_nums: Maximum number of results per query
            fields: List of fields to include in results

        Returns:
            pandas.DataFrame containing concatenated results from all queries

        NOTE:
            Results are not deduplicated and no threshold filtering is applied.

        Raises:
            ValueError: If embedding function is not specified
        """
        if self.emb_func is None:
            raise ValueError("Please specify the embedding function")

        batch_result = []
        for q in query_list:
            emb = await self.emb_func([q])
            res = await self.vearch_tools.emb_search(
                self.config.db_name,
                space_name=space_name,
                router_url=self.config.router_url,
                emb=emb,
                retrieval_nums=retrieval_nums,
                fields=fields,
            )
            if self.vearch_tools.check_search_result(res):
                res_df = self.vearch_tools.retrieval2df(res)
                batch_result.append(res_df)
        batch_result_df = pd.concat(batch_result)
        return batch_result_df

    async def check_space_exist(self, space_name):
        """Check if a space exists in the database.

        Args:
            space_name: Name of the space to check

        Returns:
            bool: Boolean indicating if the space exists
        """
        try:
            res = await self.vearch_tools.check_info(
                self.config.db_name, space_name, self.config.master_url
            )

            if res.get("msg", "space_notexists") == "success":
                return True
            else:
                return False
        except Exception:
            return False

    ##
    ## NOTE: System-level methods for tool management
    ##
    async def create_vearch_table_by_tool_list(self, tool_list):
        """Initialize Vearch database with tool information for system use.

        This method creates and populates the system tool space with tool metadata
        and embeddings for efficient retrieval. It handles the complete workflow
        from space creation to data upload.

        Args:
            tool_list: List of tuples containing tool information
                      Format: [('app_name', 'agent_name', 'tool_name', 'tool_desc'), ...]

        Example:
            tool_list = [('app_test3', 'agent_test3', 'tool_test3', 'tool_desc_test3')]
        """
        # Create system table if not exist
        if not await self.check_space_exist(self.config.tool_df_space_name):
            await self.create_tool_df_space()

        df = pd.DataFrame(
            tool_list, columns=["app_name", "agent_name", "tool_name", "tool_desc"]
        )
        # print(df)

        # 1. Generate embeddings for tool dscriptions
        with EmbeddingCache() as embedding:
            # Method 1: Individual embedding
            # for app_name, agent_name, tool_name, tool_desc in tool_list:
            #     tool_desc_embedding = embedding.get(tool_desc)
            #     print(tool_desc_embedding)

            # Method 2: Batch embedding
            tool_desc_embeddings = await embedding.get(list(df["tool_desc"]))
            df["tool_desc_embedding"] = list(tool_desc_embeddings)

        # 2. Validate single app constraint
        unique_app_name = df["app_name"].unique()
        assert len(unique_app_name) == 1, "app_name must be unique"

        # 3. Clean existing data for this app
        await self.delete_by_appname(unique_app_name[0])

        # 4. Update new data
        await self.upload_by_df(df)

        return

    async def upload_by_df(self, df):
        """Upload tool data from DataFrame to Vearch.

        Args:
            df: pandas.DataFrame containing tool information with embeddings

        Returns:
            str: Response from bulk insert operation
        """
        items = ""
        for ind, row in df.iterrows():
            # Prepare document data
            data = {
                "app_name": row["app_name"],
                "agent_name": row["agent_name"],
                "tool_name": row["tool_name"],
                "vector": {
                    "feature": [float(e) for e in list(row["tool_desc_embedding"])]
                },
                "tool_desc": row["tool_desc"],
                "remark": "1",
            }
            # Build NDJSON format for bulk insert
            items += (
                json.dumps({"index": {"_id": self.vearch_tools.generate_random_str()}})
                + "\n"
                + json.dumps(data)
                + "\n"
            )
        # Perform bulk insert
        res = await self.vearch_tools.insert_batch(
            self.config.db_name,
            self.config.tool_df_space_name,
            self.config.router_url,
            items,
        )

        return res

    async def delete_by_appname(self, app_name):
        """Delete all documents associated with a specific app name.

        Args:
            app_name: Name of the application whose tools should be deleted
        """
        ids = await self.recall_by_appname(app_name)

        # Delete each document individually
        for doc_id in ids:
            await self.vearch_tools.delete_by_docid(
                self.config.db_name,
                self.config.tool_df_space_name,
                self.config.router_url,
                doc_id,
            )
        return

    async def recall_by_appname(self, app_name):
        """Retrieve all document IDs for a specific app name.

        Args:
            app_name: Name of the application to search for

        Returns:
            list: List of document IDs associated with the app
        """
        search_query = {
            "query": {
                "filter": [
                    {"term": {"app_name": app_name}},
                ]
            },
            "fields": [],
            "size": 20000,  # Large number to get all documents
        }
        resp = await self.vearch_tools.search_by_filter(
            self.config.db_name,
            self.config.tool_df_space_name,
            self.config.router_url,
            search_query,
        )
        if resp["hits"]["total"] > 0:
            res_df = self.vearch_tools.retrieval2df(resp)
            ids = res_df["_id"].to_list()
        else:
            ids = []
        return ids

    async def tool_retrieval(
        self,
        query,
        app_name=None,
        agent_name=None,
        top_k=5,
        threshold=0.01,
        *args,
        **kwargs,
    ):
        """Retrieve relevant tools based on query with app and agent filtering.

        This is the main method for tool discovery in the system, combining
        semantic search with metadata filtering to find appropriate tools.

        Args:
            query: Text description of the desired tool functionality
            app_name: Filter by application name
            agent_name: Filter by agent name
            top_k: Maximum number of tools to return (default: 5)
            threshold: Minimum similarity score threshold (default: 0.01)

        Returns:
            list: List of tool names that match the criteria
        """
        filter = {"app_name": app_name, "agent_name": agent_name}
        emb = await self.emb_func([query])
        # Perform filtered similarity search
        resp = await self.vearch_tools.filter_and_emb_search(
            self.config.db_name,
            self.config.tool_df_space_name,
            self.config.router_url,
            emb,
            top_k,
            [],
            filter,
        )
        # Process results and apply threshold
        if resp["hits"]["total"] > 0:
            res_df = self.vearch_tools.retrieval2df(resp)
            res_df = res_df.loc[res_df["_score"] > threshold]
            tools = res_df["tool_name"].to_list()
            return tools
        else:
            return []

    ##
    ## NOTE:Agent-level methods for table operations
    ##
    async def single_mode_insert_by_text(self, body, vector_col, sapce_name):
        """Insert a single document with automatic embedding generation.

        Args:
            body: Document data dictionary
            vector_col: Name of the field to generate embedding from
            sapce_name: Name of the target space

        Returns:
            str: Response from insert operation

        Example:
            body = {
                "data": {
                    "test1": "Test field test1",
                    "test2": "Test field test2"
                },
                "vector_col": "test1"
            }
        """
        # 1. Generate embedding for the specified field
        emb = await self.emb_func([body[vector_col]])
        vector = {"feature": [float(e) for e in list(emb[0])]}  # Convert to float
        # 2. Add vector to document body
        body["vector"] = vector
        # print(body)

        res = await self.vearch_tools.insert_single(
            self.config.db_name, sapce_name, self.config.router_url, json.dumps(body)
        )

        return res

    ##
    ## NOTE:Helper methods for parameter passing
    ##

    async def emb_search(self, emb, retrieval_nums, fields):
        """Direct embedding search when user hasn't specified embedding function.

        Args:
            emb: Pre-computed embedding vector
            retrieval_nums: Maximum number of results
            fields: Fields to return

        Returns:
            pd.DataFrame: pandas.DataFrame with search results or empty DataFrame
        """
        res = await self.vearch_tools.emb_search(
            self.config.db_name,
            self.config.space_name,
            self.config.router_url,
            self.config.emb,
            retrieval_nums,
            fields,
        )
        if self.vearch_tools.check_search_result(res):
            res = self.vearch_tools.retrieval2df(res)
        else:
            res = pd.DataFrame()
        return res

    async def filter_and_emb_search(self, emb, retrieval_nums, fields, filter={}):
        """Combined embedding and filter search.

        Args:
            emb: Pre-computed embedding vector
            retrieval_nums: Maximum number of results
            fields: Fields to return
            filter: Filter conditions dictionary

        Returns:
            pd.DataFrame: pandas.DataFrame with search results or empty DataFrame
        """
        res = await self.vearch_tools.filter_and_emb_search(
            self.config.db_name,
            self.config.space_name,
            self.config.router_url,
            emb,
            retrieval_nums,
            fields,
            filter,
        )
        if self.vearch_tools.check_search_result(res):
            res = self.vearch_tools.retrieval2df(res)
        else:
            res = pd.DataFrame()
        return res

    async def search_by_filter(self, space_name, filter):
        """Search using filter conditions only.

        Args:
            space_name: Name of the space to search
            filter: Filter conditions

        Returns:
            pd.DataFrame: pandas.DataFrame with search results or empty DataFrame
        """
        res = await self.vearch_tools.search_by_filter(
            self.config.db_name, space_name, self.config.router_url, data_list=filter
        )
        if self.vearch_tools.check_search_result(res):
            res = self.vearch_tools.retrieval2df(res)
        else:
            res = pd.DataFrame()
        return res


class VearchConfig(object):
    """Configuration wrapper for Vearch database settings.

    This class converts configuration dictionaries into object attributes for easier
    access and maintains embedding function mappings.
    """

    def __init__(self, config):
        # Convert all config items to class attributes
        for key, value in config.items():
            setattr(self, key, value)
        # todo: Maintain mapping between embedding functions and indexes


class EmbeddingModel(object):
    """Client for remote embedding model service.

    This class handles communication with embedding model endpoints, providing
    asynchronous batch embedding generation with optimization for parallel processing
    and proper error handling.
    """

    def __init__(self, url):
        self.url = url

    async def get_embeddings_async(self, querys):
        """Generate embeddings for a batch of text queries asynchronously.

        This method handles batch embedding generation with parallel processing
        for decoding, normalization, and proper error handling for various
        failure scenarios.

        Args:
            querys: List or tuple of text strings to embed

        Returns:
            numpy.ndarray: Normalized embedding vectors, shape (n_queries, embedding_dim)

        Raises:
            ValueError: For invalid input types or various error conditions

        NOTE:
            The method performs several optimizations:
            - Parallel decoding of base64 responses
            - Vector normalization for consistent similarity computation
            - Comprehensive error handling for network and processing issues
        """
        if not isinstance(querys, (list, tuple)):
            raise ValueError("querys must be a list or tuple")
        try:
            url = self.url
            # Prepare request payload in expected format
            payload = {
                "model_name": "embedding",
                "inputs": [
                    {
                        "name": "text",
                        "shape": [len(querys)],
                        "datatype": "BYTES",
                        "data": querys,
                    }
                ],
                "outputs": [{"name": "last_hidden_state_clip"}],
            }
            # Make async HTTP request
            async with httpx.AsyncClient(
                verify=False,  # Skip SSL verification if needed
                timeout=60.0,
            ) as client:
                response = await client.post(
                    url,
                    headers={
                        "Accept-Encoding": "identity",
                    },
                    json=payload,
                )
                # Check HTTP status
                if response.status_code != 200:
                    # print(f"HTTP error: {response.status}")
                    return None

                # Parse JSON response
                result = response.json()

                # Parallel processing optimization for result decoding
                decode_tasks = []

                # Create async tasks for decoding each embedding
                for item in result["outputs"][0]["data"]:
                    task = asyncio.create_task(
                        asyncio.to_thread(
                            lambda x: np.array(
                                json.loads(base64.b64decode(x).decode("utf-8"))
                            ),
                            item,
                        )
                    )
                    decode_tasks.append(task)
                # Wait for all decoding tasks to complete
                decoded_data = await asyncio.gather(*decode_tasks)
                # Combine results into single array
                combined = np.concatenate(decoded_data)
                # Normalize vectors for consistent similarity computation
                norms = np.linalg.norm(combined, axis=1, keepdims=True)
                normalized = combined / norms
                return normalized
        except httpx.HTTPError as e:
            raise ValueError(f"HTTP client error: {str(e)}")
            # print(f"HTTP client error: {str(e)}")
        except asyncio.TimeoutError:
            raise ValueError("Request timed out")
            # print("Request timed out")
        except Exception as e:
            raise ValueError(f"Unexpected error: {str(e)}")
            # print(f"Unexpected error: {str(e)}")
            # print(f"Problematic input: {querys[:3]}...")  # Print 3 examples to avoid leaking data
        return None
