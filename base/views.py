from django.shortcuts import render,redirect
from django.http import HttpResponse

def home(request):
    return HttpResponse("Hello")

def payment_success(request):
    return HttpResponse("Payment Done")

def payment_fail(request):
    return HttpResponse("Payment Failed")
