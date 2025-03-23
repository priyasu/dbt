import os
import json
import yaml
import networkx as nx
import re

# Define parent directory where all dbt projects are stored
DBT_PARENT_DIR = "C:/Users/karak/dbt_cursor"

def find_dbt_projects(parent_dir):
    """Find all subdirectories containing a dbt project (with a target/manifest.json file)."""
    projects = {}
    
    # List all items in the parent directory
    for item in os.listdir(parent_dir):
        item_path = os.path.join(parent_dir, item)
        
        # Check if it's a directory
        if os.path.isdir(item_path):
            # Check if it contains a target directory with manifest.json
            target_dir = os.path.join(item_path, "target")
            manifest_path = os.path.join(target_dir, "manifest.json")
            
            if os.path.isdir(target_dir) and os.path.exists(manifest_path):
                projects[item] = target_dir
                print(f"Found dbt project: {item}")
    
    print(f"Found {len(projects)} dbt projects: {', '.join(projects.keys())}")
    return projects

def strip_column_descriptions(columns_data):
    """Remove descriptions from column metadata while keeping column names."""
    if not columns_data:
        return {}
        
    stripped_columns = {}
    for col_name, col_data in columns_data.items():
        # Just keep the column name without any descriptions
        stripped_columns[col_name] = {"name": col_data.get("name", col_name)}
    
    return stripped_columns

def load_metadata(project_name, project_path, metadata):
    """Loads manifest.json from a dbt project and extracts metadata."""
    manifest_path = os.path.join(project_path, "manifest.json")

    if not os.path.exists(manifest_path):
        print(f"Warning: No manifest.json found for {project_name}")
        return
    
    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        
        # Process models
        for node_name, node_data in manifest.get("nodes", {}).items():
            try:
                if node_data.get("resource_type") == "model":
                    model_name = node_data.get("name", "")
                    # Remove project prefix for cleaner output
                    metadata["models"][model_name] = {
                        "schema": node_data.get("schema", ""),
                        "database": node_data.get("database", ""),
                        "description": node_data.get("description", ""),
                        "columns": strip_column_descriptions(node_data.get("columns", {})),
                        "original_id": node_name,  # Store the original node id for later reference
                        "project": project_name  # Keep track of which project this came from
                    }

                    # Extract dependencies for lineage tracking
                    if "depends_on" in node_data and "nodes" in node_data["depends_on"]:
                        for dep in node_data["depends_on"]["nodes"]:
                            metadata["lineage"].add_edge(dep, model_name)
            except Exception as e:
                print(f"Error processing node {node_name}: {e}")

        # Process sources - need different approach depending on manifest structure
        try:
            # First attempt: Normal structure with 'sources' as objects
            if isinstance(manifest.get("sources", {}), dict):
                for source_id, source_data in manifest.get("sources", {}).items():
                    try:
                        source_name = source_data.get("name", "")
                        
                        # Check if tables is a dict (newer format) or list (older format)
                        tables_data = source_data.get("tables", {})
                        
                        if isinstance(tables_data, dict):
                            # Format: {"table_name": {table_details}}
                            for table_name, table_info in tables_data.items():
                                metadata["sources"][table_name] = {
                                    "schema": source_data.get("schema", ""),
                                    "database": source_data.get("database", ""),
                                    "description": table_info.get("description", ""),
                                    "columns": strip_column_descriptions(table_info.get("columns", {})),
                                    "source_name": source_name,
                                    "original_id": f"source.{project_name}.{source_name}.{table_name}",
                                    "project": project_name
                                }
                        elif isinstance(tables_data, list):
                            # Format: [{"name": "table_name", ...}, {...}]
                            for table in tables_data:
                                table_name = table.get("name", "")
                                if table_name:
                                    metadata["sources"][table_name] = {
                                        "schema": source_data.get("schema", ""),
                                        "database": source_data.get("database", ""),
                                        "description": table.get("description", ""),
                                        "columns": strip_column_descriptions(table.get("columns", {})),
                                        "source_name": source_name,
                                        "original_id": f"source.{project_name}.{source_name}.{table_name}",
                                        "project": project_name
                                    }
                    except Exception as e:
                        print(f"Error processing source {source_id}: {e}")
            
            # Alternative: Look for source refs in parsed node details for older formats
            # Find all source nodes in child_map
            for node_id, edges in manifest.get("child_map", {}).items():
                if node_id.startswith("source."):
                    parts = node_id.split(".")
                    if len(parts) >= 4:
                        source_project = parts[1]
                        source_name = parts[2]
                        table_name = parts[3]
                        
                        # Only add if not already added
                        if table_name not in metadata["sources"]:
                            metadata["sources"][table_name] = {
                                "schema": "",  # Can't determine schema from this structure
                                "database": "", # Can't determine database from this structure 
                                "description": "",
                                "columns": {},
                                "source_name": source_name,
                                "original_id": node_id,
                                "project": project_name
                            }
                        
                        # Add lineage: this source is used by these models
                        for target in edges:
                            if target.startswith("model."):
                                target_model = extract_model_name(target)
                                metadata["lineage"].add_edge(table_name, target_model)
                                
        except Exception as e:
            print(f"Error processing sources: {e}")
                
    except Exception as e:
        print(f"Error loading manifest for {project_name}: {e}")

def extract_model_name(node_id):
    """Extract just the model name from a node ID."""
    if node_id.startswith("model."):
        parts = node_id.split(".")
        if len(parts) >= 3:
            return parts[2]  # Return just the model name
    elif node_id.startswith("source."):
        parts = node_id.split(".")
        if len(parts) >= 4:
            return parts[3]  # Return just the table name
    return node_id

def unify_lineage(metadata):
    """Create unified lineage by resolving cross-project references."""
    original_lineage = metadata["lineage"]
    unified_lineage = nx.DiGraph()
    
    # Build a mapping from original node IDs to simplified model names
    node_mapping = {}
    for model_name, model_data in metadata["models"].items():
        if "original_id" in model_data:
            node_mapping[model_data["original_id"]] = model_name
    
    # Add source mappings
    for source_name, source_data in metadata["sources"].items():
        if "original_id" in source_data:
            node_mapping[source_data["original_id"]] = source_name
    
    # Process each edge in the original lineage
    for source, target in original_lineage.edges():
        source_simplified = node_mapping.get(source, extract_model_name(source))
        target_simplified = node_mapping.get(target, extract_model_name(target))
        
        # Add the edge to the unified lineage
        if source_simplified and target_simplified:
            unified_lineage.add_edge(source_simplified, target_simplified)
    
    return unified_lineage

def unify_metadata():
    """Scans all dbt projects and aggregates metadata into a unified format."""
    dbt_projects = find_dbt_projects(DBT_PARENT_DIR)

    unified_metadata = {
        "models": {},
        "sources": {},
        "lineage": nx.DiGraph()
    }

    for project, path in dbt_projects.items():
        print(f"Processing project: {project}")
        load_metadata(project, path, unified_metadata)
    
    # Create a unified lineage graph that resolves cross-project references
    print("Creating unified lineage...")
    unified_lineage = unify_lineage(unified_metadata)
    
    # Convert lineage graph to a serializable format
    try:
        lineage_edges = list(unified_lineage.edges())
        # Create a simple lineage representation without labels
        unified_metadata["lineage"] = []
        for src, dst in lineage_edges:
            unified_metadata["lineage"].append({
                "from": src,
                "to": dst
            })
            
        # Remove original_id from models and sources, but keep project info
        for model_name in unified_metadata["models"]:
            if "original_id" in unified_metadata["models"][model_name]:
                del unified_metadata["models"][model_name]["original_id"]
                
        for source_name in unified_metadata["sources"]:
            if "original_id" in unified_metadata["sources"][source_name]:
                del unified_metadata["sources"][source_name]["original_id"]
                
    except Exception as e:
        print(f"Error converting lineage graph: {e}")
        unified_metadata["lineage"] = []

    # Save unified metadata directly in the parent directory
    # Save as JSON
    json_path = os.path.join(DBT_PARENT_DIR, "unified_metadata.json")
    with open(json_path, "w") as f:
        json.dump(unified_metadata, f, indent=4)

    # Save as YAML
    yaml_path = os.path.join(DBT_PARENT_DIR, "unified_metadata.yml") 
    with open(yaml_path, "w") as f:
        yaml.dump(unified_metadata, f, default_flow_style=False)

    print(f"Unified metadata successfully generated in {DBT_PARENT_DIR}")

if __name__ == "__main__":
    unify_metadata()
