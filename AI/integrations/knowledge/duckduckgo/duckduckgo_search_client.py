from __future__ import annotations

import logging

from langchain_core.tools import BaseTool, ToolException


logger = logging.getLogger(__name__)


class DuckDuckGoSearchClient:
    def __init__(self, search_tool: BaseTool):
        self.search_tool = search_tool

    def search(self, query: str) -> str:
        logger.info('Starting query execution "%s"', query)

        try:
            result = self.search_tool.run(query)
        except ToolException as e:
            logger.error('Error executing query "%s": %s', query, e)
            return ""

        logger.info('Finished query execution "%s"', query)
        return result or ""
