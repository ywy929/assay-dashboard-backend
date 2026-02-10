from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
import models
from routers.dependency import get_current_user
from services.pdf_generator import pdf_generator
from datetime import datetime
import re
from typing import List

router = APIRouter()


def sanitize_filename(filename: str) -> str:
    """
    Remove or replace characters that are problematic in filenames.
    Replaces invalid characters with underscores.
    """
    # Replace invalid filename characters with underscores
    # Invalid chars: / \ : * ? " < > |
    sanitized = re.sub(r'[/\\:*?"<>|]', '_', filename)
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip('. ')
    return sanitized


def build_pdf_filename(customer_name: str, itemcodes: List[str]) -> str:
    """Build PDF filename from customer name and itemcodes: CustomerName_A1_A2.pdf"""
    name_part = sanitize_filename(customer_name or 'assay')
    codes_part = '_'.join(sanitize_filename(code) for code in itemcodes if code)
    if codes_part:
        return f"{name_part}_{codes_part}.pdf"
    return f"{name_part}.pdf"


def format_finalresult(value) -> str:
    if value == -1:
        return "REJ"
    elif value == -2:
        return "REDO"
    elif value == -3:
        return "LOW"
    else:
        return f"{value:.1f}" if value else ""


def build_formcode_item(result) -> dict:
    return {
        'itemcode': result.itemcode or '',
        'sampleweight': f"{result.sampleweight}g" if result.sampleweight else '',
        'samplereturn': f"{result.samplereturn}g" if result.samplereturn else '',
        'finalresult': format_finalresult(result.finalresult),
    }


@router.get("/generate/single/{assay_id}")
def generate_pdf_for_single_assay(
    assay_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Generate PDF for a single assay result
    Returns PDF file
    """
    # Get the specific assay result
    assay_result = db.query(models.AssayResult).filter(
        models.AssayResult.id == assay_id
    ).first()

    if not assay_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assay result not found"
        )

    # Check if user has permission to view this result
    if current_user.role == 'customer':
        if assay_result.customer != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this result"
            )
        # Customers can only access ready results
        if not assay_result.ready:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Assay result not found"
            )

    # Get customer information
    customer = db.query(models.User).filter(
        models.User.id == assay_result.customer
    ).first()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    # Format date
    date = assay_result.created.strftime("%d %b %Y")

    formcode_items = [build_formcode_item(assay_result)]

    # Generate PDF
    pdf_buffer = pdf_generator.generate_pdf(
        customer_name=customer.name,
        date=date,
        formcode_items=formcode_items
    )

    # Return PDF as streaming response
    filename = build_pdf_filename(customer.name, [assay_result.itemcode or 'assay'])
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@router.get("/generate/selected")
def generate_pdf_for_selected(
    ids: str = Query(..., description="Comma-separated assay result IDs"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Generate PDF for selected assay results by IDs.
    """
    try:
        assay_ids = [int(id.strip()) for id in ids.split(",") if id.strip()]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID format. Expected comma-separated integers.",
        )

    if not assay_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No assay IDs provided.",
        )

    # Get the requested assay results
    assay_results = (
        db.query(models.AssayResult)
        .filter(models.AssayResult.id.in_(assay_ids))
        .order_by(models.AssayResult.created)
        .all()
    )

    if not assay_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No assay results found for the given IDs",
        )

    # Permission checks
    if current_user.role == "customer":
        if any(r.customer != current_user.id for r in assay_results):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access these results",
            )
        if any(not r.ready for r in assay_results):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No assay results found for the given IDs",
            )

    # Get customer information from the first result
    first_result = assay_results[0]
    customer = db.query(models.User).filter(
        models.User.id == first_result.customer
    ).first()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    date = first_result.created.strftime("%d %b %Y")
    formcode_items = [build_formcode_item(r) for r in assay_results]

    pdf_buffer = pdf_generator.generate_pdf(
        customer_name=customer.name,
        date=date,
        formcode_items=formcode_items,
    )

    itemcodes = [r.itemcode or "" for r in assay_results]
    filename = build_pdf_filename(customer.name, itemcodes)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        },
    )


@router.get("/generate/{formcode}")
def generate_pdf_for_formcode(
    formcode: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Generate PDF for a specific formcode (grouped assay results)
    Returns PDF file
    """
    # Get all assay results for this formcode
    assay_results = db.query(models.AssayResult).filter(
        models.AssayResult.formcode == formcode
    ).order_by(models.AssayResult.created).all()

    if not assay_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No assay results found for this formcode"
        )

    # Check if user has permission to view these results
    # Customers can only view their own results
    if current_user.role == 'customer':
        if any(result.customer != current_user.id for result in assay_results):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access these results"
            )
        # Customers can only access ready results
        if any(not result.ready for result in assay_results):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No assay results found for this formcode"
            )

    # Get customer information from the first result
    first_result = assay_results[0]
    customer = db.query(models.User).filter(
        models.User.id == first_result.customer
    ).first()

    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )

    # Format date
    date = first_result.created.strftime("%d %b %Y")

    # Prepare formcode items
    formcode_items = [build_formcode_item(r) for r in assay_results]

    # Generate PDF
    pdf_buffer = pdf_generator.generate_pdf(
        customer_name=customer.name,
        date=date,
        formcode_items=formcode_items
    )

    # Return PDF as streaming response
    itemcodes = [r.itemcode or '' for r in assay_results]
    filename = build_pdf_filename(customer.name, itemcodes)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )
