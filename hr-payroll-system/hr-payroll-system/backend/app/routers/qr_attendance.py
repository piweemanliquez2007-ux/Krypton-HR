"""ROUTER layer: QR attendance HTTP endpoints.

Two worlds live behind this router:

* the KIOSK endpoints (/scan, /scan/confirm) are called by the tablet at the
  entrance. They do not use a user JWT: the tablet proves who it is with
  the X-Device-Id / X-Device-Secret headers, and the employee proves who
  they are with the signed QR code plus their PIN.
* the MANAGEMENT endpoints (/qr/*, /kiosks, /events, /audit, /shifts) are
  called by HR/Admin with the normal bearer token.
"""
from datetime import date

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import BusinessRuleError, ForbiddenError, UnauthorizedError
from app.schemas.qr_attendance import (
    AttendanceEventOut,
    KioskOut,
    KioskRegisterRequest,
    QrCredentialOut,
    QrIssueRequest,
    QrRotateRequest,
    QrScanConfirmRequest,
    QrScanRequest,
    QrScanResponse,
    ShiftCreate,
    ShiftHoursOut,
    ShiftOut,
)
from app.security import ADMIN_HR, get_current_user, require_role
from app.services import qr_service

router = APIRouter(prefix="/api/attendance", tags=["QR Attendance"])


# ----------------------------------------------------------------- helpers
def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _kiosk_identity(
    x_device_id: str | None = Header(None, alias="X-Device-Id"),
    x_device_secret: str | None = Header(None, alias="X-Device-Secret"),
    x_kiosk_key: str | None = Header(None, alias="X-Kiosk-Key"),
) -> dict:
    """
    Reads the kiosk identity from the request headers.

    The device id alone is not enough: the secret is checked against the
    SHA-256 digest stored for that device, so a stolen device id is useless.
    """
    device_id = (x_device_id or "").strip()
    secret = (x_device_secret or x_kiosk_key or "").strip()
    if not device_id:
        raise UnauthorizedError("Missing kiosk device id")
    if not secret:
        raise UnauthorizedError("Missing kiosk device secret")
    return {"device_id": device_id, "secret": secret}


# ------------------------------------------------------------------ kiosk
@router.post("/scan", response_model=QrScanResponse)
def scan(
    body: QrScanRequest,
    request: Request,
    kiosk: dict = Depends(_kiosk_identity),
    db: Session = Depends(get_db),
):
    """
    Step 1 of the kiosk handshake: the employee holds their QR up to the tablet.

    Returns status="pin_required" when a PIN is needed (nothing is written
    yet), or status="punched" when the punch was recorded straight away.
    """
    return qr_service.scan(
        db,
        qr_payload=body.qr_payload,
        device_id=kiosk["device_id"],
        pin=body.pin,
        kiosk_key=kiosk["secret"],
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/scan/confirm", response_model=QrScanResponse)
def confirm_scan(
    body: QrScanConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Step 2 of the kiosk handshake: the employee typed their PIN.

    The challenge carries the employee, the day and the punch type, so the
    client cannot turn a time-in into a time-out.
    """
    return qr_service.confirm_scan(
        db,
        challenge_id=body.challenge_id,
        pin=body.pin,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


# ------------------------------------------------------- QR credentials
@router.post("/qr/issue", response_model=QrCredentialOut, status_code=status.HTTP_201_CREATED)
def issue_qr(
    body: QrIssueRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """Issues (or re-issues) the QR badge of an employee and returns the payload."""
    return qr_service.issue_credential(db, body.employee_id, body.mode,
                                       body.require_pin, body.pin)


@router.post("/qr/rotate", response_model=QrCredentialOut)
def rotate_qr(
    body: QrRotateRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """Revokes the current credential of an employee and issues a fresh one."""
    return qr_service.rotate_credential(db, body.employee_id, body.mode, body.reason)


@router.post("/qr/pin")
def set_qr_pin(
    body: QrIssueRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """Sets (or changes) the kiosk PIN that goes with the QR badge."""
    if not body.pin:
        raise BusinessRuleError("A PIN is required")
    return qr_service.set_employee_pin(db, body.employee_id, body.mode, body.pin)


@router.get("/qr/my-qr", response_model=QrCredentialOut)
def my_qr(
    mode: str = Query("static", pattern="^(static|dynamic)$"),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Self-service: the signed QR payload of the signed-in employee.

    A dynamic QR is re-signed on every call, so a screenshot of it stops
    working as soon as the employee refreshes it.
    """
    employee_id = user.get("employee_id")
    if not employee_id:
        raise UnauthorizedError("This account is not linked to an employee record")
    return qr_service.get_employee_qr(db, employee_id, mode)


@router.get("/qr/{employee_id}", response_model=QrCredentialOut)
def employee_qr(
    employee_id: int,
    mode: str = Query("static", pattern="^(static|dynamic)$"),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """HR view of the QR badge of one employee."""
    return qr_service.get_employee_qr(db, employee_id, mode)


# ---------------------------------------------------------------- kiosks
@router.get("/kiosks", response_model=list[KioskOut])
def list_kiosks(
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """All registered kiosk tablets."""
    return qr_service.list_kiosks(db)


@router.post("/kiosks", response_model=KioskOut, status_code=status.HTTP_201_CREATED)
def register_kiosk(
    body: KioskRegisterRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """
    Enrolls a kiosk tablet. The device secret is returned exactly once:
    it is stored on the tablet and only its SHA-256 digest is kept here.
    """
    return qr_service.register_kiosk(db, body.device_id, body.label, body.location)


# ---------------------------------------------------------------- events
@router.get("/events", response_model=list[AttendanceEventOut])
def list_events(
    employee_id: int | None = None,
    work_date: date | None = None,
    device_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """The append-only punch log."""
    return qr_service.list_events(db, employee_id=employee_id, work_date=work_date,
                                  device_id=device_id, limit=limit, skip=skip)


@router.get("/audit", response_model=list[dict])
def list_audit(
    employee_id: int | None = None,
    device_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """Every scan attempt, accepted or rejected (fraud trail)."""
    return qr_service.list_audit(db, employee_id=employee_id, device_id=device_id,
                                 limit=limit)


# ---------------------------------------------------------------- shifts
@router.get("/shifts", response_model=list[ShiftOut])
def list_shifts(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """The shift definitions with the employees rostered on them."""
    return qr_service.list_shifts(db)


@router.post("/shifts", status_code=status.HTTP_201_CREATED)
def create_shift(
    body: ShiftCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_role(*ADMIN_HR)),
):
    """Creates a shift and optionally assigns employees to it."""
    return qr_service.create_shift(db, body)


@router.get("/shift-hours/{employee_id}", response_model=list[ShiftHoursOut])
def shift_hours(
    employee_id: int,
    work_date: date,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Worked hours per shift for one employee on one day, calculated from the
    punch log (each time-in paired with the next time-out).
    """
    if user["role"] not in ADMIN_HR and user.get("employee_id") != employee_id:
        raise ForbiddenError("You can only see your own shift hours")
    return qr_service.shift_hours_for(db, employee_id, work_date)
