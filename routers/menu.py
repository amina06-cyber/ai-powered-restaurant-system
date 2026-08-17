from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
 
import database
import models
import schemas
 
router = APIRouter()
 
 
@router.get("/menu")
def get_menu(db: Session = Depends(database.get_db)):
    items = db.query(models.MenuItem).all()
    return items
 
 
@router.post("/menu")
def create_menu_item(item: schemas.MenuItemCreate, db: Session = Depends(database.get_db)):
    new_item = models.MenuItem(**item.dict())
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item
