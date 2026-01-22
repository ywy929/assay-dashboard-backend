from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
import models
from routers.dependency import get_current_user
from services.pdf_generator import pdf_generator
from datetime import datetime
import os
import re

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

    # Prepare single item
    if assay_result.finalresult == -1:
        finalresult_display = "REJ"
    elif assay_result.finalresult == -2:
        finalresult_display = "REDO"
    elif assay_result.finalresult == -3:
        finalresult_display = "LOW"
    else:
        finalresult_display = f"{assay_result.finalresult:.1f}" if assay_result.finalresult else ""

    formcode_items = [{
        'itemcode': assay_result.itemcode or '',
        'sampleweight': f"{assay_result.sampleweight}g" if assay_result.sampleweight else '',
        'samplereturn': f"{assay_result.samplereturn}g" if assay_result.samplereturn else '',
        'finalresult': finalresult_display
    }]

    # Generate PDF
    pdf_buffer = pdf_generator.generate_pdf(
        customer_name=customer.name,
        date=date,
        formcode_items=formcode_items
    )

    # Return PDF as streaming response
    sanitized_itemcode = sanitize_filename(assay_result.itemcode or 'assay')
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=assay_result_{sanitized_itemcode}.pdf"
        }
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
    formcode_items = []
    for result in assay_results:
        # Format finalresult: if -1, show "Reject", otherwise show the value
        if result.finalresult == -1:
            finalresult_display = "REJ"
        elif result.finalresult == -2:
            finalresult_display = "REDO"
        elif result.finalresult == -3:
            finalresult_display = "LOW"
        else:
            finalresult_display = f"{result.finalresult:.1f}" if result.finalresult else ""

        formcode_items.append({
            'itemcode': result.itemcode or '',
            'sampleweight': f"{result.sampleweight}g" if result.sampleweight else '',
            'samplereturn': f"{result.samplereturn}g" if result.samplereturn else '',
            'finalresult': finalresult_display
        })

    # Generate PDF
    pdf_buffer = pdf_generator.generate_pdf(
        customer_name=customer.name,
        date=date,
        formcode_items=formcode_items
    )

    # Return PDF as streaming response
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=assay_result_{formcode}.pdf"
        }
    )
