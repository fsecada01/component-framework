"""Views for Django component demo."""

from django.shortcuts import render

from .models import Customer, Order


def index(request):
    """Homepage with overview."""
    return render(request, "index.html")


def form_demo(request):
    """Form component demo."""
    return render(request, "form_demo.html")


def model_demo(request):
    """Model-bound component demo."""
    # Create sample data if needed
    if not Order.objects.exists():
        customer = Customer.objects.create(
            name="John Doe", email="john@example.com"
        )
        Order.objects.create(
            customer=customer, status="pending", total=99.99, notes="Test order"
        )

    orders = Order.objects.select_related("customer").all()[:5]
    return render(request, "model_demo.html", {"orders": orders})


def websocket_demo(request):
    """WebSocket component demo."""
    return render(request, "websocket_demo.html")
