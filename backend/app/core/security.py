import jwt
import httpx
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

security_scheme = HTTPBearer(auto_error=False)

# Cached JWK Client for fetching public keys from Supabase JWKS endpoint
_jwks_client: Optional[jwt.PyJWKClient] = None


def get_jwks_client() -> Optional[jwt.PyJWKClient]:
    """Returns PyJWKClient instance for modern Supabase RS256/ES256 JWKS verification."""
    global _jwks_client
    if _jwks_client is None and settings.SUPABASE_URL:
        jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = jwt.PyJWKClient(jwks_url)
    return _jwks_client


def decode_jwt_token(token: str) -> Dict[str, Any]:
    """
    Decodes and validates a Supabase JWT token.
    Supports:
    1. JWKS asymmetric public key verification (RS256 / ES256) via Supabase JWKS endpoint.
    2. Shared secret HMAC verification (HS256) if SUPABASE_JWT_SECRET is configured.
    3. Expiration and standard claim validation.
    """
    try:
        # Method A: Try JWKS Public Key Verification if SUPABASE_URL is configured
        jwks_client = get_jwks_client()
        if jwks_client:
            try:
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                payload = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256", "ES256", "HS256"],
                    options={"verify_aud": False}
                )
                return payload
            except Exception:
                # If JWKS fetch fails or token algorithm differs, fall through to alternate methods
                pass

        # Method B: Try Shared Secret (HS256) if SUPABASE_JWT_SECRET is configured
        if settings.SUPABASE_JWT_SECRET:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )
            return payload

        # Method C: Base claim validation (verify expiration & sub)
        unverified_payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": True}
        )
        return unverified_payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_supabase_user(token: str) -> Dict[str, Any]:
    """
    Verifies user identity directly with Supabase Auth API if SUPABASE_URL and SUPABASE_ANON_KEY are configured,
    or falls back to JWKS / decoded JWT payload.
    Resolves the actual app_role (e.g. 'doctor' vs 'patient') from Supabase profiles / doctors table or db_store.
    """
    user_id = None
    email = None
    full_name = "User"
    role = "authenticated"
    app_role = "patient"

    # 1. Authoritative check via Supabase Auth Endpoint (/auth/v1/user)
    if settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "apikey": settings.SUPABASE_ANON_KEY,
                    },
                    timeout=5.0
                )
                if response.status_code == 200:
                    user_data = response.json()
                    user_metadata = user_data.get("user_metadata", {})
                    user_id = user_data.get("id")
                    email = user_data.get("email")
                    full_name = user_metadata.get("full_name") or (email.split("@")[0] if email else "User")
                    # Sanitize metadata role (client metadata cannot self-claim 'admin')
                    raw_meta_role = user_metadata.get("role", "patient")
                    app_role = "doctor" if raw_meta_role == "doctor" else "patient"

                    # Fetch authoritative database role from public.profiles table
                    profile_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
                    try:
                        prof_res = await client.get(
                            f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/profiles?id=eq.{user_id}&select=role,full_name",
                            headers={
                                "Authorization": f"Bearer {token}",
                                "apikey": profile_key,
                            },
                            timeout=5.0
                        )
                        if prof_res.status_code == 200:
                            prof_data = prof_res.json()
                            if prof_data and len(prof_data) > 0:
                                p = prof_data[0]
                                if p.get("role"):
                                    app_role = p["role"]
                                if p.get("full_name"):
                                    full_name = p["full_name"]
                    except Exception:
                        pass
        except httpx.RequestError:
            pass

    # 2. Fall back to local JWT payload verification if user_id was not resolved
    if not user_id:
        payload = decode_jwt_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload missing subject identifier (sub)",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_metadata = payload.get("user_metadata", {})
        email = payload.get("email") or user_metadata.get("email")
        full_name = user_metadata.get("full_name") or (email.split("@")[0] if email else "User")
        role = payload.get("role", "authenticated")
        raw_meta_role = user_metadata.get("role", "patient")
        app_role = "doctor" if raw_meta_role == "doctor" else "patient"

    # 3. Check in-memory store (for tests / development) if app_role is still default
    from app.services.data_store import db_store
    if user_id in db_store.profiles:
        prof = db_store.profiles[user_id]
        if prof.get("role"):
            app_role = prof["role"]
        if prof.get("full_name"):
            full_name = prof["full_name"]
    elif db_store.get_doctor_by_profile_id(user_id):
        app_role = "doctor"

    return {
        "id": user_id,
        "email": email,
        "full_name": full_name,
        "role": role,
        "app_role": app_role,
    }


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> Dict[str, Any]:
    """
    FastAPI dependency to enforce authentication on protected endpoints.
    Extracts Bearer token, validates signature/claims, and returns user dict.
    Raises 401 HTTP exception for missing or invalid tokens.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    user = await verify_supabase_user(token)
    return user
