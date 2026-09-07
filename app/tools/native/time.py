"""Current-time tool -- no input needed."""
from datetime import datetime, timezone

from pydantic import BaseModel


class TimeInput(BaseModel):
    pass


def get_current_time():
    now = datetime.now(timezone.utc)
    return {"utc_datetime": now.isoformat(), "day_of_week": now.strftime("%A")}
