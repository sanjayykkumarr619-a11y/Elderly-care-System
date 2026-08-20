"""
A tiny regex-based route registry shared by every api/*.py module and by
server.py. Deliberately minimal (this is a "basic Python HTTP backend",
not a framework): each handler is a plain function

    handler(conn, match, query, body, patient_id) -> (status_code, response_dict)

registered against an HTTP method, a compiled path regex, and (for
protected routes) the set of account roles allowed to call it.

`patient_id` is the *effective patient* the request operates on: for a
PATIENT account that's their own id, for a linked CARETAKER/FAMILY/DOCTOR
account it's the patient they're linked to (see database.resolve_actor).
It's None for public routes such as login/register.
"""

import re

ROUTES = []

ALL_ROLES = ("PATIENT", "CARETAKER", "FAMILY", "DOCTOR")


class ApiError(Exception):
    """Raise inside a handler to return a specific status code + message."""

    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def route(method, pattern, public=False, roles=None, scope="patient"):
    """`roles`: iterable of account roles allowed to call this route.
    Defaults to every role when the route is protected; ignored for
    public routes. Server.py rejects any other role with 403 before the
    handler ever runs.

    `scope`: which id gets passed as the handler's last argument.
      - "patient" (default): the effective patient id (own id for a
        PATIENT account, the linked patient's id for Caretaker/Family/
        Doctor) - used by every data-owning module (medicines, cameras,
        devices, ...).
      - "self": the token owner's own account id, unaffected by linking -
        used by api/auth_api.py, which manages the account itself rather
        than patient-scoped data.
    """
    compiled = re.compile(pattern)
    allowed_roles = tuple(roles) if roles is not None else ALL_ROLES

    def decorator(func):
        ROUTES.append((method.upper(), compiled, func, public, allowed_roles, scope))
        return func

    return decorator
