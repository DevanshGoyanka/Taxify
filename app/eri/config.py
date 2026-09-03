"""
ERI environment-scoped credential resolver.

Provides a single ``get_eri_credentials()`` entry point that returns the
correct credential bundle for the active ``(ERI_MODE, ERI_ENV)`` pair.

All ERI credentials live exclusively in ``.env`` as suffix-qualified
variables (``*_TYPE2_UAT``, ``*_TYPE2_PRODUCTION``, ``*_TYPE3_UAT``,
``*_TYPE3_PRODUCTION``). They are NEVER stored in ``app/vault.py`` —
that module is a taxpayer-PII store and must not be repurposed for ERI
operator credentials.

Four distinct credential sets are supported:
  - Type-2 UAT        (API integration, UAT gateway, AWS UAT IP)
  - Type-2 Production (API integration, prod gateway, AWS prod IP)
  - Type-3 UAT        (offline utility, UAT SW_ID + UAT digest secret)
  - Type-3 Production (offline utility, prod SW_ID + prod digest secret)

Critical invariant: the ``SWCreatedBy`` stamped in ``CreationInfo`` and
the ``(secret_key, iterations)`` used by ``_compute_digest`` MUST come
from the SAME ``(mode, environment)`` suffix. The resolver enforces this
by reading both from the same suffix.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Literal, Optional


Mode = Literal["type2", "type3"]
Environment = Literal["uat", "production"]


class ERIConfigurationError(RuntimeError):
    """Raised when ERI credentials are unavailable for JSON generation.

    The ITR JSON's ``CreationInfo`` (``SWCreatedBy``, ``JSONCreatedBy``)
    and the ``Digest`` MUST always flow from the selected ERI credential
    bundle for the active ``(ERI_MODE, ERI_ENV)`` pair. There is no
    non-ERI source for these identity fields. If the resolver cannot
    supply them, JSON generation must fail loudly rather than stamp a
    hardcoded placeholder identity — a placeholder would produce a JSON
    whose CreationInfo does not match the ERI type that generated it.
    """


@dataclass(frozen=True)
class ERICredentials:
    """A resolved ERI credential bundle for one (mode, environment) pair.

    Attributes:
        mode: "type2" (official API integration) or "type3" (offline utility).
        environment: "uat" or "production".
        sw_id: The ERI software identifier stamped in CreationInfo.SWCreatedBy.
            Present for both Type-2 and Type-3.
        digest_secret_key: HMAC-SHA256 secret key (UTF-8 string) used by
            ``_compute_digest``. Present for both modes (Type-3 needs it too).
        digest_iterations: Iteration count for the HMAC loop.
        client_id: Type-2 only. ERI Client ID (from ITD registration).
        client_secret: Type-2 only. ERI Client Secret.
        eri_user_id: Type-2 only. ERI User ID for login.
        eri_password: Type-2 only. ERI plaintext password (encrypted via
            symmetric key before transmission).
        base_url: Type-2 only. ITD gateway base URL (env-scoped).
        dsc_signing_mode: Type-2 only. One of "token" | "file" | "ngrok" | "mock".
        aws_ssh_host: Type-2 only. The whitelisted-IP AWS jump host.
        aws_ssh_user: Type-2 only. SSH user on the AWS host.
        aws_ssh_key_path: Type-2 only. Path to the SSH private key file.
    """

    mode: Mode
    environment: Environment
    sw_id: str
    digest_secret_key: Optional[str]
    digest_iterations: Optional[int]
    # Type-2 only (None for Type-3):
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    eri_user_id: Optional[str] = None
    eri_password: Optional[str] = None
    base_url: Optional[str] = None
    dsc_signing_mode: Optional[str] = None
    aws_ssh_host: Optional[str] = None
    aws_ssh_user: Optional[str] = None
    aws_ssh_key_path: Optional[str] = None


def _env_suffix(environment: Environment) -> str:
    """Return the env-var suffix for a given environment (UAT or PRODUCTION)."""
    return "UAT" if environment == "uat" else "PRODUCTION"


def _read_env(name: str) -> Optional[str]:
    """Read an environment variable, stripping whitespace; None if unset/empty."""
    raw = os.getenv(name)
    if raw is None:
        return None
    stripped = raw.strip()
    return stripped or None


def _read_int_env(name: str, default: int = 1) -> Optional[int]:
    """Read an integer env var; returns default if unset, raises if non-numeric."""
    raw = _read_env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {name!r} must be an integer, got {raw!r}."
        ) from exc


def get_eri_credentials() -> ERICredentials:
    """Resolve the active ERI credential bundle from ``.env``.

    Reads ``ERI_MODE`` and ``ERI_ENV`` to select the suffix, then reads the
    suffixed variables for that ``(mode, environment)`` pair. Neither has a
    default: all four (mode, environment) credential sets coexist in the
    same ``.env`` (see the module docstring), so silently guessing either
    one wrong would resolve real credentials for the wrong pair rather than
    failing to resolve at all -- the same "a wrong gateway must fail, not
    be guessed" principle :func:`get_eri_base_url` already applies. This
    matters concretely: a prior incident (Dual-Mode ERI Integration Plan
    §"Recovery incident") blanked several `.env` secrets via a careless
    full-file rewrite; had ``ERI_ENV`` been blanked the same way while a
    default of "production" was in effect, credential resolution would have
    silently targeted production instead of failing loudly.

    Returns:
        The resolved :class:`ERICredentials`.

    Raises:
        ValueError: If ``ERI_MODE``/``ERI_ENV`` is unset or not one of
            their two valid values, or if a digest-iteration value is
            non-numeric.
    """
    mode_raw = (os.getenv("ERI_MODE") or "").strip().lower()
    env_raw = (os.getenv("ERI_ENV") or "").strip().lower()

    if mode_raw not in ("type2", "type3"):
        raise ValueError(
            f"ERI_MODE must be 'type2' or 'type3', got {mode_raw!r}. "
            "It is never defaulted -- an unset or blank ERI_MODE must fail "
            "loudly rather than silently resolve credentials for a guessed mode."
        )
    if env_raw not in ("uat", "production"):
        raise ValueError(
            f"ERI_ENV must be 'uat' or 'production', got {env_raw!r}. "
            "It is never defaulted -- an unset or blank ERI_ENV must fail "
            "loudly rather than silently resolve credentials for a guessed "
            "environment (all four (mode, environment) credential sets "
            "coexist in .env, so guessing wrong would resolve real "
            "credentials for the wrong pair)."
        )

    mode: Mode = mode_raw  # type: ignore[assignment]
    environment: Environment = env_raw  # type: ignore[assignment]
    suffix = f"{mode.upper()}_{_env_suffix(environment)}"

    sw_id = _read_env(f"ERI_SW_ID_{suffix}")
    digest_secret = _read_env(f"ERI_DIGEST_SECRET_KEY_{suffix}")
    digest_iterations = _read_int_env(f"ERI_DIGEST_ITERATIONS_{suffix}", default=1)

    if not sw_id:
        raise ValueError(
            f"ERI_SW_ID_{suffix} is not set in .env (required for "
            f"{mode}/{environment})."
        )

    creds = ERICredentials(
        mode=mode,
        environment=environment,
        sw_id=sw_id,
        digest_secret_key=digest_secret,
        digest_iterations=digest_iterations,
    )

    if mode == "type2":
        creds = replace(
            creds,
            client_id=_read_env(f"ERI_CLIENT_ID_{suffix}"),
            client_secret=_read_env(f"ERI_CLIENT_SECRET_{suffix}"),
            eri_user_id=_read_env(f"ERI_USER_ID_{suffix}"),
            eri_password=_read_env(f"ERI_PASSWORD_{suffix}"),
            base_url=_read_env(f"ERI_BASE_URL_{suffix}"),
            dsc_signing_mode=(os.getenv("ERI_DSC_SIGNING_MODE", "token") or "token").lower(),
            aws_ssh_host=_read_env(f"ERI_AWS_SSH_HOST_{suffix}"),
            aws_ssh_user=_read_env(f"ERI_AWS_SSH_USER_{suffix}", ) or "ec2-user",
            aws_ssh_key_path=_read_env(f"ERI_AWS_SSH_KEY_PATH_{suffix}"),
        )
    return creds


def get_eri_base_url() -> str:
    """Resolve the ITD gateway base URL for the active (mode, environment).

    Every Type-2 module used to capture ``os.getenv("ERI_BASE_URL", <UAT
    default>)`` into a module constant at import time. ``ERI_BASE_URL`` is not
    a variable this project sets — the env-scoped ``ERI_BASE_URL_TYPE2_UAT`` /
    ``ERI_BASE_URL_TYPE2_PRODUCTION`` pair is — so every call silently went to
    the hardcoded UAT default, and switching ``ERI_ENV`` to production would
    have kept sending live requests to UAT without a word.

    Resolution order: the env-scoped value for the active pair, then the
    unsuffixed ``ERI_BASE_URL`` as a legacy escape hatch, then an error. There
    is deliberately no default — a wrong gateway must fail, not be guessed.

    Raises:
        ERIConfigurationError: If no base URL is configured for the active pair.
    """
    creds = get_eri_credentials()
    if creds.base_url:
        return creds.base_url
    legacy = _read_env("ERI_BASE_URL")
    if legacy:
        return legacy
    suffix = f"{creds.mode.upper()}_{_env_suffix(creds.environment)}"
    raise ERIConfigurationError(
        f"ERI_BASE_URL_{suffix} is not set. The ITD gateway URL must be "
        f"configured for the active ERI pair ({creds.mode}/{creds.environment}); "
        "it is never defaulted, because a wrong gateway would send live "
        "requests to the wrong environment."
    )


def get_eri_user_id() -> Optional[str]:
    """Resolve the ERI User ID for the active (mode, environment).

    Same defect as the base URL: the Type-2 modules read an unsuffixed
    ``ERI_USER_ID`` that this project does not set, so the configured
    ``ERI_USER_ID_TYPE2_UAT`` was never read by anything and every Type-2 call
    failed with "ERI_USER_ID environment variable not set" while the value sat
    in ``.env``.

    Returns None rather than raising so the callers' own guards keep their
    existing exception types and control flow.
    """
    try:
        user_id = get_eri_credentials().eri_user_id
    except Exception:
        user_id = None
    return user_id or _read_env("ERI_USER_ID")


def get_eri_password() -> Optional[str]:
    """Resolve the ERI password for the active (mode, environment)."""
    try:
        password = get_eri_credentials().eri_password
    except Exception:
        password = None
    return password or _read_env("ERI_PASSWORD")


def get_eri_symmetric_key() -> Optional[str]:
    """Resolve the symmetric key used to encrypt the ERI password.

    ``ERI_SYMMETRIC_KEY`` is global rather than env-scoped. There is
    deliberately no default: ``login.py`` used to fall back to a hardcoded
    placeholder key, which encrypts the password into something the gateway
    cannot decrypt and reports as an ordinary auth failure — a placeholder
    that produces a wrong answer is worse than no value at all.
    """
    return _read_env("ERI_SYMMETRIC_KEY")


def assert_credentials_at_startup() -> None:
    """Startup guard: validate the active credential bundle is sane.

    Call once from ``app/main.py`` lifespan. Raises ``RuntimeError`` if a
    production deployment is misconfigured (mock DSC, missing digest secret
    in production).

    Note: this previously also required ``ERI_AWS_SSH_HOST_TYPE2_PRODUCTION``
    for Type-2 production, because egress had to leave from an IP that ITD had
    whitelisted, via an SSH jump host. That whitelisting requirement no longer
    applies — ERI endpoints accept the deployment IP directly — so the check
    was removed rather than left demanding a jump host that is never used.
    """
    creds = get_eri_credentials()

    if creds.environment == "production":
        if creds.mode == "type2":
            if creds.dsc_signing_mode == "mock":
                raise RuntimeError(
                    "ERI_DSC_SIGNING_MODE=mock is forbidden in Type-2 production."
                )
        if not creds.digest_secret_key:
            raise RuntimeError(
                f"ERI_DIGEST_SECRET_KEY_{creds.mode.upper()}_PRODUCTION must be "
                "set in production (cannot compute Digest without it)."
            )
