import logging
import os

import requests

logger = logging.getLogger(__name__)


def uho_login(username, password, timeout=10):
    """Valida credenciales contra auth.uho.edu.cu; devuelve dict o None."""
    api_key = os.environ.get("UHO_API_KEY")
    if not api_key:
        logger.warning("UHO_API_KEY no configurada; se omite la autenticación universitaria.")
        return None

    origin = os.environ.get("UHO_AUTH_ORIGIN", "https://auth.uho.edu.cu")
    url = os.environ.get("UHO_AUTH_URL", "https://auth.uho.edu.cu/login")
    headers = {
        "Origin": origin,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"AGA {api_key}",
    }

    try:
        response = requests.post(
            url,
            json={"username": username, "password": password},
            headers=headers,
            timeout=timeout,
        )
        data = response.json()
    except Exception as exc:
        logger.warning("Fallo la consulta a auth.uho.edu.cu: %s", exc)
        return None

    if not data.get("OK") or "activeUser" not in data:
        return None

    user = data["activeUser"]
    personal = user.get("personal_information", {})
    account = user.get("account_info", {})

    return {
        "username": user.get("uid"),
        "name": personal.get("given_name"),
        "surname": personal.get("sn"),
        "national_id": personal.get("dni"),
        "user_type": account.get("user_type"),
        "active": user.get("account_state") == "TRUE",
    }
