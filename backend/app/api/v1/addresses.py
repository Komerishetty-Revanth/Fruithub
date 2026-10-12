import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_customer
from app.models import User
from app.schemas.address import AddressCreate, AddressOut, AddressUpdate
from app.services import address_service

router = APIRouter(prefix="/addresses", tags=["Addresses"])


@router.get("", response_model=list[AddressOut])
def my_addresses(user: User = Depends(require_customer), db: Session = Depends(get_db)):
    return address_service.list_addresses(db, user)


@router.post("", response_model=AddressOut, status_code=201)
def add_address(data: AddressCreate, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Save a map pin. Street, city and pincode are optional and can be added later."""
    return address_service.create_address(db, user, data)


@router.patch("/{address_id}", response_model=AddressOut)
def edit_address(address_id: uuid.UUID, data: AddressUpdate,
                 user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """Add the main address later, or move the pin."""
    return address_service.update_address(db, user, address_id, data)


@router.post("/{address_id}/default", response_model=AddressOut)
def make_default(address_id: uuid.UUID, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    return address_service.set_default(db, user, address_id)


@router.delete("/{address_id}")
def remove_address(address_id: uuid.UUID, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    address_service.delete_address(db, user, address_id)
    return {"success": True}