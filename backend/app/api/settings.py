from fastapi import APIRouter, Depends
from .. import schemas
from ..utils import settings as settings_util

router = APIRouter()

@router.get("/", response_model=schemas.Settings)
def read_settings():
    return settings_util.get_settings()

@router.post("/", response_model=schemas.Settings)
def update_settings(settings: schemas.Settings):
    settings_util.save_settings(settings.dict())
    return settings

@router.post("/reset", response_model=schemas.Settings)
def reset_settings():
    settings_util.save_settings(settings_util.DEFAULT_SETTINGS)
    return settings_util.DEFAULT_SETTINGS
