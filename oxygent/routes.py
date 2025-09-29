"""routes.py.

FastAPI routing layer for the OxyGent MAS service.

This module exposes several HTTP endpoints that support:
    * Health checks and root redirection
    * Retrieval of node‐level execution details stored in Elasticsearch
    * Proxying user requests to an LLM provider through the OxyGent agent stack
    * Lightweight persistence for scripted calls (save / list / load)

Every public callable is documented using **Google Python Style** docstrings so
that automatic documentation tooling such as *Sphinx napoleon* can render them
cleanly.

Typical usage example::

    # uvicorn main:app --reload
    curl http://localhost:8000/check_alive  #→ {"alive": 1}
"""

import json
import logging
import os
import re
import traceback
from datetime import datetime

import aiofiles
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from .config import Config
from .databases.db_es import JesEs, LocalEs
from .db_factory import DBFactory
from .oxy_factory import OxyFactory
from .schemas import OxyRequest, WebResponse
from .utils.data_utils import add_post_and_child_node_ids

logger = logging.getLogger(__name__)

router = APIRouter()


# Basic route to redirect to the web interface
@router.get("/")
def read_root():
    """Redirect the client to the bundled web front-end.

    Returns:
        fastapi.responses.RedirectResponse: HTTP 307 redirect to
        ``./web/index.html`` that ships with the service UI.
    """
    return RedirectResponse(url="./web/index.html")


@router.get("/check_alive")
def check_alive():
    """Health‑check endpoint.

    Returns:
        dict: ``{"alive": 1}`` when the service is running.
    """
    # Application health check endpoint
    return {"alive": 1}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    upload_dir = os.path.join(Config.get_cache_save_dir(), "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_path = os.path.join(upload_dir, file_name)
    pic_url = f"../static/{file_name}"

    # Save file asynchronously
    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    # Return file path
    return WebResponse(data={"file_name": pic_url}).to_dict()


@router.get("/node")
async def get_node_info(item_id: str):
    """Retrieve execution-node details using its *node_id* or *trace_id*.

    Args:
        item_id: Either a node identifier or a trace identifier. If the input
            is a trace-level identifier the function resolves it to the first
            concrete node before returning details.

    Returns:
        dict: A ``WebResponse``-compatible dictionary containing the node
        payload enriched with ``pre_id`` and ``next_id`` navigation helpers.
    """
    db_factory = DBFactory()
    if Config.get_es_config():
        jes_config = Config.get_es_config()
        hosts = jes_config["hosts"]
        user = jes_config["user"]
        password = jes_config["password"]
        es_client = db_factory.get_instance(JesEs, hosts, user, password)
    else:
        es_client = db_factory.get_instance(LocalEs)
    es_response = await es_client.search(
        Config.get_app_name() + "_node", {"query": {"term": {"_id": item_id}}}
    )
    try:
        datas = es_response["hits"]["hits"]
        if datas:
            node_data = datas[0]["_source"]
            trace_id = node_data["trace_id"]
        else:
            # puting item_id as trace_id
            trace_id = item_id

        """Get trace_id from trace table (abandoned)"""
        """If error, get trace_id from node table."""
        es_response = await es_client.search(
            Config.get_app_name() + "_node",
            {
                "query": {"term": {"trace_id": trace_id}},  # all of the nodes
                "size": 10000,
                "sort": [{"create_time": {"order": "asc"}}],
            },
        )
        node_ids = []
        for data in es_response["hits"]["hits"]:
            node_ids.append(data["_source"]["node_id"])

        if len(node_ids) == 0:
            return WebResponse(code=400, message="illegal node_id").to_dict()

        if trace_id == item_id:
            # puting item_id from trace_id，get node_id data for another time
            item_id = node_ids[0]
            es_response = await es_client.search(
                Config.get_app_name() + "_node", {"query": {"term": {"_id": item_id}}}
            )
            datas = es_response["hits"]["hits"]
            node_data = datas[0]["_source"]

        for i, node_id in enumerate(node_ids):
            if item_id == node_id:
                node_data["pre_id"] = node_ids[i - 1] if i >= 1 else ""
                node_data["next_id"] = node_ids[i + 1] if i <= len(node_ids) - 2 else ""

                if "input" in node_data:
                    node_data["input"] = json.loads(node_data["input"])

                if "prompt" in node_data["input"]["class_attr"]:
                    del node_data["input"]["class_attr"]["prompt"]
                env_value_to_key = {v: k for k, v in os.environ.items()}

                # Generate the maximum and minimum values for the data range
                node_data["data_range_map"] = dict()
                for tree in [
                    node_data["input"]["class_attr"],
                    node_data["input"]["class_attr"].get("llm_params", dict()),
                    node_data["input"]["arguments"],
                ]:
                    for k, v in tree.items():
                        if v and isinstance(v, str) and v in env_value_to_key:
                            tree[k] = f"${{{env_value_to_key[v]}}}"
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            if v <= 1:
                                max_value = 1
                            else:
                                max_value = v * 10
                            node_data["data_range_map"][k] = {
                                "min": 0,
                                "max": max_value,
                            }
                return WebResponse(data=node_data).to_dict()

    except Exception:
        error_msg = traceback.format_exc()
        logger.error(error_msg)
        return WebResponse(code=500, message="遇到问题").to_dict()


# Define the data model for the LLM call request
@router.get("/view")
async def get_task_info(item_id: str):
    db_factory = DBFactory()
    if Config.get_es_config():
        jes_config = Config.get_es_config()
        hosts = jes_config["hosts"]
        user = jes_config["user"]
        password = jes_config["password"]
        es_client = db_factory.get_instance(JesEs, hosts, user, password)
    else:
        es_client = db_factory.get_instance(LocalEs)

    # es_client.exists(Config.get_app_name() + "_node", doc_id=item_id)

    # If item_id is node_id
    es_response = await es_client.search(
        Config.get_app_name() + "_node", {"query": {"term": {"_id": item_id}}}
    )
    datas = es_response["hits"]["hits"]
    if datas:
        node_data = datas[0]["_source"]
        trace_id = node_data["trace_id"]
    else:
        # Input item_id as trace_id
        trace_id = item_id

    es_response = await es_client.search(
        Config.get_app_name() + "_node",
        {
            "query": {"term": {"trace_id": trace_id}},
            "size": 10000,
            "sort": [{"create_time": {"order": "asc"}}],
        },
    )
    nodes = []
    for data in es_response["hits"]["hits"]:
        data["_source"]["call_stack"] = data["_source"]["call_stack"]
        data["_source"]["node_id_stack"] = data["_source"]["node_id_stack"]
        data["_source"]["pre_node_ids"] = data["_source"]["pre_node_ids"]
        if (
            len(data["_source"]["pre_node_ids"]) == 1
            and data["_source"]["pre_node_ids"][0] == ""
        ):
            data["_source"]["pre_node_ids"] = []
        nodes.append(data["_source"])
    for index, node in enumerate(nodes):
        node["index"] = index
    add_post_and_child_node_ids(nodes)
    task_data = {"nodes": nodes, "trace_id": trace_id}
    return WebResponse(data=task_data).to_dict()


class Item(BaseModel):
    class_attr: dict
    arguments: dict


@router.post("/call")
async def call(item: Item):
    """Invoke an **OxyGent** agent according to the *Item* request.

    The endpoint supports ad-hoc overrides for both class constructor arguments
    (``class_attr`` field) and runtime ``arguments``.

    Example::

        POST /call
        {
            "class_attr": {"class_name": "api_llm", "max_tokens": 2048"},
            "arguments": {"temperature": 0.7, "stream": False}
        }

    Args:
        item: The validated request payload.

    Returns:
        dict: ``WebResponse`` wrapper containing the model output.
    """
    try:
        pattern = r"^\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}$"
        for tree in [
            item.class_attr,
            item.class_attr.get("llm_params", dict()),
            item.arguments,
        ]:
            for k, v in tree.items():
                if not isinstance(v, str):
                    continue
                match = re.match(pattern, v.strip())
                if match:
                    tree[k] = os.getenv(match.group(1), v)

        item.class_attr["name"] = item.class_attr["class_name"].lower()
        llm_params_type_dict = {
            "temperature": float,
            "max_tokens": int,
            "top_p": float,
        }
        for k, v in item.class_attr.get("llm_params", dict()).items():
            if k in llm_params_type_dict:
                item.class_attr["llm_params"][k] = llm_params_type_dict[k](v)
        oxy = OxyFactory.create_oxy(item.class_attr["class_name"], **item.class_attr)
        oxy_response = await oxy.execute(OxyRequest(arguments=item.arguments))
        return WebResponse(data={"output": oxy_response.output}).to_dict()
    except Exception:
        error_msg = traceback.format_exc()
        logger.error(error_msg)
        return WebResponse(code=500, message="遇到问题").to_dict()


class Script(BaseModel):
    """Schema for serialized *calling scripts* stored on disk.

    Attributes:
        name: Human-friendly script label displayed in the UI.
        contents: Arbitrary list structure that is later posted to ``/call``.
    """

    name: str
    contents: list


# ---------------------------------------------------------------------------
# Local *script* storage helpers
# ---------------------------------------------------------------------------


@router.get("/list_script")
def list_script():
    script_save_dir = os.path.join(Config.get_cache_save_dir(), "script")
    os.makedirs(script_save_dir, exist_ok=True)
    files = os.listdir(script_save_dir)
    if files:
        return WebResponse(
            data={
                "scripts": [
                    os.path.splitext(file)[0]
                    for file in files
                    if file.endswith(".json")
                ]
            }
        ).to_dict()
    else:
        return WebResponse(data={"scripts": []}).to_dict()


@router.post("/save_script")
def save_script(script: Script):
    """Persist a script definition to ``$CACHE_DIR/script``.

    Args:
        script: The script metadata and payload to store.

    Returns:
        dict: ``WebResponse`` with the generated ``script_id`` timestamp.
    """
    script_save_dir = os.path.join(Config.get_cache_save_dir(), "script")
    with open(os.path.join(script_save_dir, script.name + ".json"), "w") as f:
        f.write(json.dumps(script.contents, ensure_ascii=False))
    return WebResponse(data={"script_id": script.name + ".json"}).to_dict()


@router.get("/load_script")
def load_script(item_id: str):
    """Load a previously saved script.

    Args:
        script_id: Timestamp‑based identifier returned by :func:`save_script`.

    Returns:
        dict: ``WebResponse`` containing the original ``contents`` array or an
        error message when the file is missing.
    """
    script_save_dir = os.path.join(Config.get_cache_save_dir(), "script")

    json_path = os.path.join(script_save_dir, item_id + ".json")
    if not os.path.exists(json_path):
        return WebResponse(code=500, message="File not exist").to_dict()
    with open(json_path, "r") as f:
        return WebResponse(data={"contents": json.loads(f.read())}).to_dict()
