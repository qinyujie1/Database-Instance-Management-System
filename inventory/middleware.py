import logging
from time import perf_counter
logger = logging.getLogger("inventory.requests")

class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = perf_counter()
        status = 500
        try:
            response = self.get_response(request)
            status = response.status_code
            response["X-Request-Duration-Ms"] = f"{(perf_counter() - started) * 1000:.3f}"
            return response
        finally:
            route = getattr(getattr(request, "resolver_match", None), "route", "unmatched")
            logger.info("method=%s route=%s status=%s duration_ms=%.3f", request.method, route, status, (perf_counter() - started) * 1000)
