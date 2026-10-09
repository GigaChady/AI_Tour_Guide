from pydantic import BaseModel


class FilteringConfig(BaseModel):
    include_prompt: bool = False
