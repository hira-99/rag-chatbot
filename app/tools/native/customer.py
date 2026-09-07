"""Read-only customer lookup tool -- an illustrative SQLite table
(app/database/models.py's customers fixtures), not a real CRM integration.
Returns personal account data, so the registry marks it requires_approval.
"""
from pydantic import BaseModel, Field

from app.database.connection import get_connection
from app.database.models import get_customer


class CustomerLookupInput(BaseModel):
    customer_id: str = Field(description="Customer ID, e.g. 'CUST-1002'")


def lookup_customer(customer_id: str):
    conn = get_connection()
    customer = get_customer(conn, customer_id.upper().strip())
    conn.close()
    if not customer:
        return {"error": f"No customer found with id {customer_id}"}
    return customer
