"""選択中のプロファイルの使用率だけを返す。API から取得処理を起動しない。"""
import json

from fastapi import APIRouter
from hermes_constants import get_hermes_home

router = APIRouter()


@router.get('/quota')
def get_quota():
    try:
        state = json.loads((get_hermes_home() / 'cache/quota-routing-state.json').read_text(encoding='utf-8'))
        if isinstance(state, dict) and 'accounts' in state:
            return state
    except (OSError, ValueError):
        pass
    return {'available': False}
