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

            # Bounded local history. Monitoring failures must not fail a request.
            from django.db import DatabaseError
            from .models import RequestMetric
            try:
                RequestMetric.objects.create(method=request.method, route=(route or "unmatched")[:255], status_code=status, duration_ms=round((perf_counter() - started) * 1000, 3))
                cutoff = list(RequestMetric.objects.values_list("id", flat=True)[999:1000])
                if cutoff:
                    RequestMetric.objects.filter(id__lt=cutoff[0]).delete()
            except DatabaseError:
                logger.warning("Request metrics persistence unavailable")
