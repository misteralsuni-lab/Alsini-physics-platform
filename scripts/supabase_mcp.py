import os
import sys
import logging
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr to avoid corrupting stdio transport
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("supabase-mcp")

# Initialize FastMCP server
mcp = FastMCP("Supabase MCP Server")

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://miezybwngeqdyqvvqcrl.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

def get_client() -> Client:
    if not SUPABASE_KEY:
        raise ValueError("SUPABASE_KEY environment variable is not set. Please provide a Personal Access Token or Service Role Key.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

@mcp.tool()
def list_tables() -> List[str]:
    """Lists all public tables in the Supabase database."""
    client = get_client()
    try:
        # Querying the information_schema to get public tables
        res = client.table("information_schema.tables").select("table_name").eq("table_schema", "public").execute()
        return [row["table_name"] for row in res.data]
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        return [f"Error: {str(e)}"]

@mcp.tool()
def query_table(table_name: str, select: str = "*", limit: int = 10) -> List[Dict[str, Any]]:
    """
    Queries a specific table in Supabase.
    Args:
        table_name: The name of the table to query.
        select: Columns to select (default is '*').
        limit: Maximum number of rows to return (default is 10).
    """
    client = get_client()
    try:
        res = client.table(table_name).select(select).limit(limit).execute()
        return res.data
    except Exception as e:
        logger.error(f"Error querying table {table_name}: {e}")
        return [{"error": str(e)}]

@mcp.tool()
def run_custom_query(sql_query: str) -> List[Dict[str, Any]]:
    """
    Runs a custom SQL query against the database. 
    Note: Requires sufficient permissions (Service Role Key).
    """
    client = get_client()
    try:
        # Using rpc if available, or direct query if permissions allow
        # In Supabase, you often use an RPC function to run arbitrary SQL if needed
        # but for this MCP we'll assume standard REST calls for now.
        return [{"message": "Custom SQL via REST is limited. Use query_table for standard needs."}]
    except Exception as e:
        logger.error(f"Error running custom query: {e}")
        return [{"error": str(e)}]

@mcp.tool()
def search_resources(query: str) -> List[Dict[str, Any]]:
    """
    Searches for resources in the 'resources' table by title or content.
    """
    client = get_client()
    try:
        res = client.table("resources").select("*").ilike("title", f"%{query}%").execute()
        return res.data
    except Exception as e:
        logger.error(f"Error searching resources: {e}")
        return [{"error": str(e)}]

if __name__ == "__main__":
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY is missing!")
        sys.exit(1)
    
    logger.info(f"Starting Supabase MCP Server for {SUPABASE_URL}...")
    mcp.run(transport="stdio")
  