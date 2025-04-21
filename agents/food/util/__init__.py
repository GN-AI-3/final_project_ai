"""
AI 기반 식단 추천 시스템 - util
"""

from agents.food.util.sql_utils import fetch_table_data
from agents.food.util.table_schema import table_schema

__all__ = [
    'fetch_table_data',
    'table_schema'
] 