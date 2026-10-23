import base64
import os
import time
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st
import streamlit.components.v1 as components
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import options_to_json
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    UserVerificationRequirement,
    ResidentKeyRequirement,
)

from database import InventoryRepository


_component = components.declare_component(
    "inventory_passkey",
    path=str(Path(__file__).parent / "components" / "passkey"),
)
CHALLENGE_TTL_SECONDS = 120


def obtener_url_app() -> str | None:
    return st.context.url or os.environ.get("PASSKEY_APP_URL")


def _contexto_webauthn(app_url: str | None) -> tuple[str, str]:
    if not app_url:
        raise ValueError("No se pudo detectar la URL de la aplicación.")

    parsed = urlparse(app_url)
    hostname = parsed.hostname
    if not hostname or not parsed.netloc:
        raise ValueError("La URL configurada para passkeys no es válida.")
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and hostname == "localhost"
    ):
        raise ValueError(
            "Las passkeys requieren HTTPS. En desarrollo, usa http://localhost."
        )
    return f"{parsed.scheme}://{parsed.netloc}", hostname


def crear_opciones_registro(usuario: dict, app_url: str | None) -> dict:
    origin, rp_id = _contexto_webauthn(app_url)
    opciones = generate_registration_options(
        rp_id=rp_id,
        rp_name="Verde Inventario",
        user_id=str(usuario["id"]).encode("utf-8"),
        user_name=usuario["email"],
        user_display_name=usuario["email"],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    return {
        "options_json": options_to_json(opciones),
        "challenge": opciones.challenge,
        "expected_origin": origin,
        "expected_rp_id": rp_id,
        "expires_at": time.time() + CHALLENGE_TTL_SECONDS,
        "user_id": int(usuario["id"]),
        "email": str(usuario["email"]),
    }


def crear_opciones_autenticacion(
    usuario_y_passkeys: dict | None, app_url: str | None
) -> dict:
    if usuario_y_passkeys is None or not usuario_y_passkeys["passkeys"]:
        raise ValueError("Esta cuenta todavía no tiene una passkey registrada.")

    origin, rp_id = _contexto_webauthn(app_url)
    descriptores = []
    for passkey in usuario_y_passkeys["passkeys"]:
        transports = []
        for transport in passkey["transports"]:
            try:
                transports.append(AuthenticatorTransport(transport))
            except ValueError:
                continue
        descriptores.append(
            PublicKeyCredentialDescriptor(
                id=passkey["credential_id"], transports=transports or None
            )
        )

    opciones = generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=descriptores,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return {
        "options_json": options_to_json(opciones),
        "challenge": opciones.challenge,
        "expected_origin": origin,
        "expected_rp_id": rp_id,
        "expires_at": time.time() + CHALLENGE_TTL_SECONDS,
        "user_id": int(usuario_y_passkeys["user_id"]),
        "email": str(usuario_y_passkeys["email"]),
    }


def _validar_desafio(pending: dict) -> None:
    if time.time() > pending["expires_at"]:
        raise ValueError("El desafío expiró. Inicia el proceso de nuevo.")


def completar_registro(
    repository: InventoryRepository, pending: dict, result: dict
) -> None:
    _validar_desafio(pending)
    credential = result.get("credential")
    if not isinstance(credential, dict):
        raise ValueError("El navegador no devolvió una credencial válida.")

    verified = verify_registration_response(
        credential=credential,
        expected_challenge=pending["challenge"],
        expected_rp_id=pending["expected_rp_id"],
        expected_origin=pending["expected_origin"],
        require_user_verification=True,
    )
    if not verified.user_verified:
        raise ValueError("El dispositivo no confirmó la verificación biométrica.")

    response = credential.get("response", {})
    transports = response.get("transports", [])
    repository.guardar_passkey(
        user_id=pending["user_id"],
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        transports=[str(transport) for transport in transports],
    )


def completar_autenticacion(
    repository: InventoryRepository, pending: dict, result: dict
) -> dict[str, int | str]:
    _validar_desafio(pending)
    credential = result.get("credential")
    if not isinstance(credential, dict):
        raise ValueError("El navegador no devolvió una credencial válida.")

    raw_id = credential.get("rawId")
    if not isinstance(raw_id, str):
        raise ValueError("La respuesta passkey no contiene un identificador válido.")
    credential_id = base64.urlsafe_b64decode(raw_id + "=" * (-len(raw_id) % 4))
    registered = repository.obtener_passkey_por_email(
        pending["email"], credential_id
    )
    if registered is None or registered["user_id"] != pending["user_id"]:
        raise ValueError("La passkey no corresponde a esta cuenta.")

    verified = verify_authentication_response(
        credential=credential,
        expected_challenge=pending["challenge"],
        expected_rp_id=pending["expected_rp_id"],
        expected_origin=pending["expected_origin"],
        credential_public_key=registered["public_key"],
        credential_current_sign_count=registered["sign_count"],
        require_user_verification=True,
    )
    if not verified.user_verified:
        raise ValueError("El dispositivo no confirmó la verificación biométrica.")

    repository.actualizar_contador_passkey(
        registered["user_id"], credential_id, verified.new_sign_count
    )
    return {"id": registered["user_id"], "email": registered["email"]}


def mostrar_componente_passkey(
    action: str, options_json: str, component_key: str
) -> dict | None:
    result = _component(
        action=action,
        options_json=options_json,
        key=component_key,
        default=None,
    )
    return result if isinstance(result, dict) else None
