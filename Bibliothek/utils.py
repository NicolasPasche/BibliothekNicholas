"""
Utility functions for the Book Search Engine application.
"""

import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any


def load_json_data(file_path: str) -> pd.DataFrame:
    """
    Load JSON data from file and convert to pandas DataFrame.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        DataFrame with book data
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Normalize column names (handle German field names)
        if 'titel' in df.columns:
            df = df.rename(columns={'titel': 'title', 'autor': 'author', 
                                   'sprache': 'language', 'schlagwörter': 'tags'})
        
        # Ensure tags is always a list
        df['tags'] = df['tags'].apply(lambda x: x if isinstance(x, list) else [])
        
        return df
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
        return pd.DataFrame()
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {file_path}.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()


def export_to_csv(df: pd.DataFrame, file_path: str) -> bool:
    """
    Export DataFrame to CSV file.
    
    Args:
        df: DataFrame to export
        file_path: Output file path
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert tags list to string for CSV
        df_export = df.copy()
        df_export['tags'] = df_export['tags'].apply(lambda x: ', '.join(x) if isinstance(x, list) else str(x))
        df_export.to_csv(file_path, index=False, encoding='utf-8')
        return True
    except Exception as e:
        print(f"Error exporting to CSV: {e}")
        return False


def export_to_json(df: pd.DataFrame, file_path: str) -> bool:
    """
    Export DataFrame to JSON file.
    
    Args:
        df: DataFrame to export
        file_path: Output file path
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert DataFrame to list of dicts
        records = df.to_dict('records')
        
        # Convert tags back to lists if they're strings
        for record in records:
            if isinstance(record.get('tags'), str):
                record['tags'] = [tag.strip() for tag in record['tags'].split(',')]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error exporting to JSON: {e}")
        return False


def get_unique_values(df: pd.DataFrame, column: str) -> List[str]:
    """
    Get unique values from a DataFrame column.
    
    Args:
        df: DataFrame
        column: Column name
        
    Returns:
        List of unique values, sorted
    """
    if column not in df.columns:
        return []
    
    if column == 'tags':
        # For tags, get all unique tags from all lists
        all_tags = []
        for tags_list in df[column]:
            if isinstance(tags_list, list):
                all_tags.extend(tags_list)
        return sorted(list(set(all_tags)))
    else:
        return sorted(df[column].dropna().unique().tolist())

