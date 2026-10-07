import copy
import math

from .native import REVISION

PARAMS = {
    "ev": (-3, 3, 0), "temperature": (2000, 12000, 6504), "tint": (-100, 100, 0),
    "highlights": (-1, 1, 0), "shadows": (-1, 1, 0), "saturation": (0, 2, 1),
    "vibrance": (-1, 1, 0), "grain": (0, 2, 1),
    "gradeShadowsWarmth": (-1, 1, 0), "gradeHighlightsWarmth": (-1, 1, 0),
}
PROFILE = {"halation": (-6, 6, 0), "screenGrade": (0, 5, 2),
           "screenExposure": (-3, 3, 0)}


def bounded(value, low, high, label):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{label} must be between {low} and {high}.")
    return value


def validate_recipe(value):
    if not isinstance(value, dict) or value.get("version") != 2 or value.get("engine") != REVISION:
        raise ValueError("This recipe requires Film Finish v2 and Fotufilm 1.11.")
    recipe = copy.deepcopy(value)
    stock = recipe.get("stock", "")
    if not isinstance(stock, str) or not stock or not stock.replace("-", "").replace("_", "").isalnum():
        raise ValueError("Invalid film stock.")
    if recipe.get("format") not in ("super8", "16mm", "super35", "35mm", "120"):
        raise ValueError("Unsupported film format.")
    if recipe.get("medium") not in ("screen", "vision-2383", "vision-2393"):
        raise ValueError("Unsupported output medium.")
    if recipe.get("digitalReference") not in ("reference-exposure", "graded-print"):
        raise ValueError("Video recipes use fixed exposure conversion.")
    for section, schema in (("params", PARAMS), ("profile", PROFILE)):
        values = recipe.get(section, {})
        if not isinstance(values, dict) or set(values) != set(schema):
            raise ValueError(f"Invalid {section} controls.")
        for key, (low, high, _) in schema.items():
            bounded(values[key], low, high, key)
    seed = recipe.get("seed")
    if seed is not None:
        bounded(seed, 0, 2147483647, "Grain seed")
        if not isinstance(seed, int):
            raise ValueError("Grain seed must be an integer.")
    return recipe


def render_request(recipe, seed, handle=None, time=0, edge=960):
    recipe = validate_recipe(recipe)
    request = {
        "edit": {"stock": recipe["stock"], "params": recipe["params"], "seed": seed,
                 "gradeSpace": False, "localTone": False, "halationModel": "legacy"},
        "profileRequest": {"controls": {**recipe["profile"], "digitalReference": recipe["digitalReference"],
                                        "hdrRange": 1, "hdrRollOff": 0},
                           "format": recipe["format"], "medium": recipe["medium"]},
        "maxEdge": edge, "videoTime": time, "original": True, "previewQuality": "still",
    }
    if handle is not None:
        request["handle"] = handle
    return request
