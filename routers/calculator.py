from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from database import get_db
import models, schemas
from routers.dependency import get_current_user

router = APIRouter()


@router.get("/recipes", response_model=list[schemas.MixRecipeResponse])
def get_recipes(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get all saved recipes for the current user"""
    recipes = (
        db.query(models.MixRecipe)
        .filter(models.MixRecipe.user_id == current_user.id)
        .order_by(models.MixRecipe.created.desc())
        .all()
    )
    return recipes


@router.post("/recipes", response_model=schemas.MixRecipeResponse)
def save_recipe(
    request: schemas.CreateMixRecipeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Save a new mix recipe"""
    recipe = models.MixRecipe(
        user_id=current_user.id,
        name=request.name,
        input_weight=request.input_weight,
        input_purity=request.input_purity,
        desired_purity=request.desired_purity,
        output_weight=request.output_weight,
        material_to_add=request.material_to_add,
        material_type=request.material_type,
        total_alloy=request.total_alloy,
        alloy_mix=[m.model_dump() for m in request.alloy_mix],
        created=datetime.now(),
    )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


@router.delete("/recipes/{recipe_id}")
def delete_recipe(
    recipe_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Delete a saved recipe (owner only)"""
    recipe = (
        db.query(models.MixRecipe)
        .filter(
            models.MixRecipe.id == recipe_id,
            models.MixRecipe.user_id == current_user.id,
        )
        .first()
    )

    if not recipe:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found",
        )

    db.delete(recipe)
    db.commit()
    return {"message": "Recipe deleted successfully"}
