from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# A Decimal from PostgreSQL that is sent to the frontend as a normal JSON number
# (Pydantic would otherwise send it as a string like "60000.00").
Number = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]
