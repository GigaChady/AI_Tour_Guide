from pydantic import BaseModel, Field


def _image_files() -> dict[str, str]:
    return {
        "building": "def_building.jpg",
        "district": "def_district.jpg",
        "landscape": "def_landscape.jpg",
        "default": "def_default.jpg",
    }


def _category_mapping() -> dict[str, str]:
    return {
        "museum": "building",
        "castle": "building",
        "fort": "landscape",
        "ruins": "landscape",
        "monument": "building",
        "memorial": "district",
        "artwork": "default",
        "viewpoint": "landscape",
        "attraction": "district",
    }


class PhotoConfig(BaseModel):
    default_image_type: str = "default"
    image_files: dict[str, str] = Field(default_factory=_image_files)
    category_mapping: dict[str, str] = Field(default_factory=_category_mapping)
