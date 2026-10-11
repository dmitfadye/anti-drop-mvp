"""Authenticated optional synthetic communication and advisory routes."""
from fastapi import APIRouter, Depends, HTTPException

from src.advisory import PlannedTransferAdvisoryV1, advise
from src.communication import router as communication_router
from src.flags import current_flags
from src.sandbox import trusted_subject

router = APIRouter()
router.include_router(communication_router)


@router.post('/api/v1/risk/advisory', tags=['Synthetic advisory'])
def pre_transfer_advisory(payload: PlannedTransferAdvisoryV1, subject: str = Depends(trusted_subject)) -> dict:
    flags = current_flags()
    if not flags.demo_mode or not flags.advisory_enabled:
        raise HTTPException(503, 'Учебная проверка перед переводом отключена.')
    if not payload.synthetic:
        raise HTTPException(422, '???????? ?????? ????????????? ??????? ????????.')
    if payload.subject_ref != subject:
        raise HTTPException(403, 'Сценарий принадлежит другому учебному пользователю.')
    result = advise(payload)
    return {**result.model_dump(mode='json'), 'banking_action': 'none', 'synthetic': True}
