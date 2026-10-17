from django.conf import settings


def demo_login(request):
    return {"demo_mode": settings.DEMO_MODE}
