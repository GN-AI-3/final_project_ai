"""
LangGraph Supervisor

A package for building agent workflows using LangGraph.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

# Set up logging
logger = logging.getLogger("langgraph_supervisor")
logger.setLevel(logging.INFO)

# Check if handlers are already configured
if not logger.handlers:
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    try:
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, "langgraph_supervisor.log"),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.INFO)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not set up file logging: {str(e)}")

# Import main components - modified to avoid circular imports
from langgraph_supervisor.supervisor import Supervisor

# Initialize nodes
import langgraph_supervisor.nodes

# Version
__version__ = "0.1.0"

logger.info(f"Initialized LangGraph Supervisor v{__version__}") 