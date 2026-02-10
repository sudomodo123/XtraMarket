from . import views
from django.urls import path

urlpatterns = [
    path('',views.home),
    path('payment/payment-success/',views.payment_success),
    path('payment/payment-cancel/',views.payment_fail),
]