# mcp_servers/sqlite_tools.py
"""SQLite database management tools."""

import sqlite3
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP()

# 默认数据库路径
DEFAULT_DB_PATH = "database.db"


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
    return conn


@mcp.tool(description="Execute a SELECT query on SQLite database")
def execute_query(
    query: str = Field(description="SQL SELECT query to execute"),
    db_path: str = Field(description="Database file path", default=DEFAULT_DB_PATH),
    params: Optional[List] = Field(description="Query parameters", default=None)
) -> dict:
    """
    Execute a SELECT query and return results.

    Args:
        query (str): SQL SELECT query
        db_path (str): Path to SQLite database file
        params (List): Optional query parameters

    Returns:
        dict: Query results with rows and metadata
    """
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            rows = cursor.fetchall()

            # 转换为字典列表
            result_rows = [dict(row) for row in rows]

            return {
                "success": True,
                "rows": result_rows,
                "row_count": len(result_rows),
                "query": query,
                "timestamp": datetime.now().isoformat()
            }

    except sqlite3.Error as e:
        return {
            "success": False,
            "error": f"SQLite error: {str(e)}",
            "query": query
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "query": query
        }


@mcp.tool(description="Execute INSERT, UPDATE, DELETE operations on SQLite database")
def execute_modification(
    query: str = Field(description="SQL INSERT/UPDATE/DELETE query"),
    db_path: str = Field(description="Database file path", default=DEFAULT_DB_PATH),
    params: Optional[List] = Field(description="Query parameters", default=None)
) -> dict:
    """
    Execute INSERT, UPDATE, or DELETE operations.

    Args:
        query (str): SQL modification query
        db_path (str): Path to SQLite database file
        params (List): Optional query parameters

    Returns:
        dict: Execution result with affected rows count
    """
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            conn.commit()

            return {
                "success": True,
                "affected_rows": cursor.rowcount,
                "last_row_id": cursor.lastrowid,
                "query": query,
                "timestamp": datetime.now().isoformat()
            }

    except sqlite3.Error as e:
        return {
            "success": False,
            "error": f"SQLite error: {str(e)}",
            "query": query
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "query": query
        }


@mcp.tool(description="Create a new table in SQLite database")
def create_table(
    table_name: str = Field(description="Name of the table to create"),
    columns: dict = Field(description="Column definitions as dict {column_name: column_type}"),
    db_path: str = Field(description="Database file path", default=DEFAULT_DB_PATH)
) -> dict:
    """
    Create a new table with specified columns.

    Args:
        table_name (str): Name of the table
        columns (dict): Column definitions
        db_path (str): Path to SQLite database file

    Returns:
        dict: Creation result
    """
    try:
        # 构建 CREATE TABLE 语句
        column_defs = []
        for col_name, col_type in columns.items():
            column_defs.append(f"{col_name} {col_type}")

        create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(column_defs)})"

        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(create_sql)
            conn.commit()

            return {
                "success": True,
                "table_name": table_name,
                "columns": columns,
                "sql": create_sql,
                "timestamp": datetime.now().isoformat()
            }

    except sqlite3.Error as e:
        return {
            "success": False,
            "error": f"SQLite error: {str(e)}",
            "table_name": table_name
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "table_name": table_name
        }


@mcp.tool(description="Get database schema information")
def get_schema(
    db_path: str = Field(description="Database file path", default=DEFAULT_DB_PATH)
) -> dict:
    """
    Get database schema information including tables and their structures.

    Args:
        db_path (str): Path to SQLite database file

    Returns:
        dict: Database schema information
    """
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # 获取所有表名
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            schema_info = {
                "database_path": db_path,
                "tables": {},
                "table_count": len(tables),
                "timestamp": datetime.now().isoformat()
            }

            # 获取每个表的结构
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()

                schema_info["tables"][table] = {
                    "columns": [
                        {
                            "name": col[1],
                            "type": col[2],
                            "not_null": bool(col[3]),
                            "default_value": col[4],
                            "primary_key": bool(col[5])
                        }
                        for col in columns
                    ],
                    "column_count": len(columns)
                }

            return {
                "success": True,
                "schema": schema_info
            }

    except sqlite3.Error as e:
        return {
            "success": False,
            "error": f"SQLite error: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }


@mcp.tool(description="Insert data into a table")
def insert_data(
    table_name: str = Field(description="Name of the table"),
    data: dict = Field(description="Data to insert as key-value pairs"),
    db_path: str = Field(description="Database file path", default=DEFAULT_DB_PATH)
) -> dict:
    """
    Insert data into a specified table.

    Args:
        table_name (str): Name of the table
        data (dict): Data to insert
        db_path (str): Path to SQLite database file

    Returns:
        dict: Insert operation result
    """
    try:
        columns = list(data.keys())
        values = list(data.values())
        placeholders = ', '.join(['?' for _ in values])

        insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"

        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(insert_sql, values)
            conn.commit()

            return {
                "success": True,
                "table_name": table_name,
                "inserted_data": data,
                "row_id": cursor.lastrowid,
                "timestamp": datetime.now().isoformat()
            }

    except sqlite3.Error as e:
        return {
            "success": False,
            "error": f"SQLite error: {str(e)}",
            "table_name": table_name,
            "data": data
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "table_name": table_name,
            "data": data
        }


@mcp.tool(description="Get table data with optional filtering")
def get_table_data(
    table_name: str = Field(description="Name of the table"),
    limit: int = Field(description="Maximum number of rows to return", default=100),
    offset: int = Field(description="Number of rows to skip", default=0),
    where_clause: Optional[str] = Field(description="WHERE clause (without WHERE keyword)", default=None),
    db_path: str = Field(description="Database file path", default=DEFAULT_DB_PATH)
) -> dict:
    """
    Retrieve data from a table with optional filtering and pagination.

    Args:
        table_name (str): Name of the table
        limit (int): Maximum rows to return
        offset (int): Rows to skip
        where_clause (str): Optional WHERE condition
        db_path (str): Path to SQLite database file

    Returns:
        dict: Table data and metadata
    """
    try:
        base_query = f"SELECT * FROM {table_name}"

        if where_clause:
            query = f"{base_query} WHERE {where_clause}"
        else:
            query = base_query

        query += f" LIMIT {limit} OFFSET {offset}"

        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()

            # 获取总行数
            count_query = f"SELECT COUNT(*) FROM {table_name}"
            if where_clause:
                count_query += f" WHERE {where_clause}"

            cursor.execute(count_query)
            total_rows = cursor.fetchone()[0]

            result_rows = [dict(row) for row in rows]

            return {
                "success": True,
                "table_name": table_name,
                "rows": result_rows,
                "returned_rows": len(result_rows),
                "total_rows": total_rows,
                "limit": limit,
                "offset": offset,
                "where_clause": where_clause,
                "timestamp": datetime.now().isoformat()
            }

    except sqlite3.Error as e:
        return {
            "success": False,
            "error": f"SQLite error: {str(e)}",
            "table_name": table_name
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "table_name": table_name
        }


@mcp.tool(description="Backup database to JSON file")
def backup_database(
    db_path: str = Field(description="Database file path", default=DEFAULT_DB_PATH),
    backup_path: Optional[str] = Field(description="Backup file path", default=None)
) -> dict:
    """
    Backup entire database to a JSON file.

    Args:
        db_path (str): Path to SQLite database file
        backup_path (str): Path for backup file

    Returns:
        dict: Backup operation result
    """
    try:
        if not backup_path:
            backup_path = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        backup_data = {
            "backup_timestamp": datetime.now().isoformat(),
            "source_database": db_path,
            "tables": {}
        }

        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # 获取所有表名
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            # 备份每个表的数据
            for table in tables:
                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()

                backup_data["tables"][table] = {
                    "data": [dict(row) for row in rows],
                    "row_count": len(rows)
                }

        # 写入备份文件
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)

        return {
            "success": True,
            "backup_path": backup_path,
            "source_database": db_path,
            "tables_backed_up": len(backup_data["tables"]),
            "total_rows": sum(table["row_count"] for table in backup_data["tables"].values()),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Backup error: {str(e)}",
            "source_database": db_path
        }


if __name__ == "__main__":
    mcp.run()
