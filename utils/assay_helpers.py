"""
Assay result helper utilities.
"""
from typing import Dict, Any
import models


def build_assay_response(result: models.AssayResult) -> Dict[str, Any]:
    """
    Build a dictionary response from an AssayResult model.
    Includes customer_name from the relationship.
    """
    return {
        "id": result.id,
        "customer": result.customer,
        "customer_name": result.customer_user.name if result.customer_user else None,
        "itemcode": result.itemcode,
        "formcode": result.formcode,
        "collector": result.collector,
        "incharge": result.incharge,
        "color": result.color,
        "sampleweight": result.sampleweight,
        "samplereturn": result.samplereturn,
        "fwa": result.fwa,
        "fwb": result.fwb,
        "lwa": result.lwa,
        "lwb": result.lwb,
        "silverpct": result.silverpct,
        "resulta": result.resulta,
        "resultb": result.resultb,
        "preresult": result.preresult,
        "loss": result.loss,
        "finalresult": result.finalresult,
        "ready": result.ready,
        "created": result.created,
        "modified": result.modified,
        "returndate": result.returndate,
    }
