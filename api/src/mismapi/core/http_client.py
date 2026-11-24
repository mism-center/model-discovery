import httpx


def error_from_downstream_response(
    response: httpx.Response,
    fallback_code: str,
    fallback_detail: str,
) -> tuple[int, str, str]:
    status = response.status_code
    if 400 <= status < 500:
        try:
            body = response.json()
        except ValueError:
            body = {}
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                code = error.get("code") or fallback_code
                detail = error.get("detail") or fallback_detail
                return (status, str(code), str(detail))
            detail = body.get("detail") or body.get("message") or fallback_detail
            return (status, fallback_code, str(detail))
        return (status, fallback_code, fallback_detail)
    return (502, fallback_code, fallback_detail)
