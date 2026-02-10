from rest_framework.decorators import api_view,permission_classes
from rest_framework.response import Response
from django.db import transaction
import time
from datetime import timedelta
import datetime
from django.utils import timezone
from django.db.models.functions import TruncMonth
from django.db.models import Count,F,Avg,Sum,Prefetch
from rest_framework import status
from .permissions import UnAuthenticated
from django.db.models.functions import Coalesce
from rest_framework.permissions import IsAdminUser,IsAuthenticated,AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from base import models
from django.db import IntegrityError
from . serializers import ProductSerializer,RecentReviewSerializer,CartItemSerializer,WishListSerializer,OrderSerializer,AddProductSerializer,LowProductSerializer,DetailProductSerializer
from . import serializers
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
from rest_framework.pagination import PageNumberPagination
from django.db import connection
import stripe
from django.conf import settings
from django.http import JsonResponse

############################### Product
@api_view(['GET'])
@permission_classes([AllowAny])
def get_all_products(request):
    products = (
        models.Product.objects
        .prefetch_related('categories', 'tags')
        .annotate(average_rating=Avg('reviews__rating'))
    )
    serializer = ProductSerializer(products, many=True)
    return Response({"products": serializer.data,"query":len(connection.queries)}, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_product_info(request):
    product_id = request.data.get('product_id')
    product = models.Product.objects.get(id=product_id)
    serializer = ProductSerializer(product)
    return Response({"product":serializer.data},status=status.HTTP_200_OK)
#################################



################################# Auth
@api_view(['POST'])
@permission_classes([UnAuthenticated])
def register(request):
    email = request.data.get('email').strip()
    password1 = request.data.get('password1').strip()
    password2 = request.data.get('password2').strip()
    username = request.data.get('username').strip()

    if password1 != password2:
        return Response({"error":"passwords doesn't match"},status=status.HTTP_400_BAD_REQUEST)
    
    if models.User.objects.filter(username=username).exists():
        return Response({"error":"Registeration failed,Try again"},status=status.HTTP_400_BAD_REQUEST)
    
    if models.User.objects.filter(email=email).exists():
        return Response({"error":"Registeration failed,Try again"},status=status.HTTP_400_BAD_REQUEST)


    try:
        user = models.User.objects.create_user(
        username = username,
        email = email,
        password= password1,
        )

        return Response({"message":"user created"},status=status.HTTP_201_CREATED)
    
    except:
        return Response({"error":"error occurred try again"})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response({"error": "Refresh token required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({"message": "Logout successful"}, status=status.HTTP_205_RESET_CONTENT)
    except Exception:
        return Response({"error": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user
    return Response({
        "email": user.email,
        "is_admin": user.is_staff,
    })


####################################



################################ Cart
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_item_to_cart(request):
    user = request.user
    product_id = request.data.get('product_id')
    quantity = int(request.data.get('quantity'))
    if quantity < 0 :
        return Response({"error":"quantity can't be negative"},status=status.HTTP_400_BAD_REQUEST) 

    product = models.Product.objects.get(id = product_id)
    
    cart,cart_created = models.Cart.objects.get_or_create(customer = user)
    cart_item,item_created = models.CartItem.objects.get_or_create(cart = cart,product=product,defaults={"quantity":quantity,"price":product.final_price})

    if not item_created:
        cart_item.quantity += quantity
        cart_item.save()

    return Response({"message":"item added to cart"},status=status.HTTP_201_CREATED)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def edit_cart(request):
    user = request.user
    product_id = request.data.get('product_id')
    quantity = int(request.data.get('quantity'))

    if quantity < 0 :
        return Response({"error":"quantity can't be negative"},status=status.HTTP_400_BAD_REQUEST) 
    try:
        cartitem = models.CartItem.objects.get(product_id = product_id,cart__customer = user )
    except:
        return Response({"error":"Cart item not found for this user and product"},status=status.HTTP_404_NOT_FOUND)
    
    cartitem.quantity = quantity
    cartitem.save()
    return Response({"message":"cart edited successfully"},status=status.HTTP_200_OK)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_item_from_cart(request):
    user = request.user
    product_id = request.data.get('product_id')
    if not product_id:
        return Response({"error": "Product ID is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        cart_item = models.CartItem.objects.get(product_id = product_id,cart__customer = user )
    except:
        return Response({"error":"Cart item not found for this user and product"},status=status.HTTP_404_NOT_FOUND)
    
    cart_item.delete()
    return Response({"message":"item deleted successfully"},status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def clear_cart(request):
    cart = get_object_or_404(models.Cart, customer=request.user)
    cart.items.all().delete()
    return Response({"message": "All items removed from cart"}, 
        status=status.HTTP_204_NO_CONTENT)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def show_cart_items(request):
    user = request.user
    cart_items = models.CartItem.objects.filter(cart__customer = user).order_by('id')
    serializer = CartItemSerializer(cart_items,many=True)
    return Response({"items":serializer.data},status=status.HTTP_200_OK)
#####################################



############################# Wishlist
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_item_to_wishlist(request): 
    product_id = request.data.get('product_id')
    user = request.user
    try:
        product = models.Product.objects.get(id=product_id)
    except:
        return Response({"error":"product not found"},status=status.HTTP_404_NOT_FOUND)
    
    wishlist,created = models.WishList.objects.get_or_create(customer = user)

    if created:
        wishlist.products.add(product)
        return Response({"message":"item added to wishlist"},status=status.HTTP_200_OK)
    else:
        if wishlist.products.filter(id=product_id).exists():
            return Response({"message":"Item already in your wishlist"},status=status.HTTP_409_CONFLICT)
        else:
            wishlist.products.add(product)
            return Response({"message":"item added to wishlist"},status=status.HTTP_200_OK)
        
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_item_from_wishlist(request):
    user = request.user
    product_id = request.data.get('product_id')
    try:
        product = models.Product.objects.get(id=product_id)
        
    except models.Product.DoesNotExist:
        return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
    
    try:
        wishlist = models.WishList.objects.get(customer=user)
        
    except models.WishList.DoesNotExist:
        return Response({"error": "Wishlist not found"}, status=status.HTTP_404_NOT_FOUND)


    if not wishlist.products.filter(id=product_id).exists():
        return Response({"error": "Item not in wishlist"}, status=status.HTTP_400_BAD_REQUEST)
    
    wishlist.products.remove(product) # auto saves no need to save maniually
    return Response({"message":"item deleted from wishlist"},status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def show_wishlist_items(request):
    user = request.user
    wishlist = models.WishList.objects.get(customer = user)
    serializer = WishListSerializer(wishlist)
    return Response({"wishlist":serializer.data},status=status.HTTP_200_OK)
######################################


############################ Reviews
@api_view(['GET'])
@permission_classes([AllowAny])
def get_recent_reviews(request):
    reviews = models.Review.objects.all()[0:11]
    serializer = RecentReviewSerializer(reviews,many=True)
    return Response({"reviews":serializer.data},status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_review(request):
    user = request.user
    comment = request.data.get('comment')
    product_id = request.data.get('product_id')
    rating = request.data.get('rating')
    product = models.Product.objects.get(id=product_id)
    
    has_bought = True if models.Order.objects.filter(customer=user,items__product = product).exists() else False

    if has_bought:
        try:
            review = models.Review.objects.create(customer=user,comment=comment,rating=rating,product=product)
            return Response({"message":"review created successfully"},status=status.HTTP_201_CREATED)
        
        except IntegrityError:
            return Response({"error":"you already reviewed this item"}, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e :
            return Response({"error": f"unexpected error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        return Response({"error":"you can't review an item that you didn't buy"},status=status.HTTP_400_BAD_REQUEST)
####################################



############################# Order

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic  # Ensures Order and OrderItems are created together or not at all
def place_order(request):
    user = request.user
    
    # 1. Prevent Double Submission (Lag Protection)
    # Check if this user created an order in the last 10 seconds
    time_threshold = timezone.now() - timedelta(seconds=30)
    if models.Order.objects.filter(customer=user, created__gte=time_threshold).exists():
        return Response(
            {"error": "Please wait a moment before placing another order."}, 
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )

    # billing details
    billing_details = {
        "customer": user,
        "full_name": request.data.get('full_name'),
        "full_address": request.data.get('full_address'),
        "country": request.data.get('country'),
        "phone_number": request.data.get('phone_number'),
        "order_notes": request.data.get('order_notes'),
    }

    items = request.data.get('items')

    try:
        # 2. Use create() instead of get_or_create()
        order = models.Order.objects.create(**billing_details)
        
        # Create items
        order_items = []
        for order_item in items:
            product = models.Product.objects.get(id=order_item["product_id"])
            order_items.append(
                models.OrderItem(
                    order=order,
                    product=product,
                    quantity=order_item["quantity"],
                    price=product.final_price
                )
            )
        
        # Bulk create is faster and more efficient
        models.OrderItem.objects.bulk_create(order_items)

        return Response(
            {"message": "Order placed successfully", "order_id": order.id}, 
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        # Because of transaction.atomic, the Order will be rolled back automatically if this fails
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def cancel_order(request):
    user = request.user
    order_id = request.data.get('order_id')
    order = get_object_or_404(models.Order,id=order_id,customer=user)
    if order.customer == user:
        if order.status != 'cancelled':
            order.status = "cancelled"
            order.save()
            return Response({"message":"order cancelled"},status = status.HTTP_200_OK)
        else:
            return Response({"error":"order is already cancelled"},status =status.HTTP_400_BAD_REQUEST)

    else:
        return Response({"error":"you can't delete someone's else order"},status = status.HTTP_403_FORBIDDEN)
###################################



# ############################### Payment
stripe.api_key = settings.STRIPE_SECRET_KEY

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_checkout_session(request):
    """
    Create a Stripe Checkout Session for an order.
    Expects: { "order_id": <order_id>, "success_url": "...", "cancel_url": "..." }
    """
    user = request.user
    order_id = request.data.get('order_id')
    
    if not order_id:
        return Response({"error": "order_id is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        order = models.Order.objects.get(id=order_id, customer=user)
    except models.Order.DoesNotExist:
        return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
    
    # Check if payment already exists for this order
    if hasattr(order, 'payment'):
        return Response({"error": "Payment already exists for this order"}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get success and cancel URLs from request or use defaults
    success_url = request.data.get('success_url', 'https://vegecommerce2.vercel.app/payment-success/')
    cancel_url = request.data.get('cancel_url', 'https://vegecommerce2.vercel.app/payment-cancel/')
    
    # Build line items from order items
    line_items = []
    for item in order.items.all():
        line_items.append({
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': item.product.name,
                    'description': item.product.description[:200] if item.product.description else '',
                },
                # Price must be in cents
                'unit_amount': int(Decimal(str(item.price)) * 100), 
            },
            'quantity': item.quantity,
        })
    
    if not line_items:
        return Response({"error": "Order has no items"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Create the Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            # Store order ID in client_reference_id for webhook
            client_reference_id=str(order.id),
            success_url=success_url + f'?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=cancel_url,
            metadata={
                'order_id': str(order.id),
                'customer_id': str(user.id),
            }
        )

        return Response({
            'session_id': checkout_session.id,
            'url': checkout_session.url,
            'order_id': order.id
        }, status=status.HTTP_200_OK)

    except stripe.error.StripeError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def stripe_webhook(request):

    """
    Handle Stripe webhook events.
    This endpoint is exempt from CSRF protection as Stripe sends requests from external servers.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', None)
    
    if not webhook_secret:
        return JsonResponse({"error": "Webhook secret not configured"}, status=500)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        return JsonResponse({"error": f"Invalid payload: {str(e)}"}, status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return JsonResponse({"error": f"Invalid signature: {str(e)}"}, status=400)

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        try:
            order_id = session.get('client_reference_id') or session.get('metadata', {}).get('order_id')
            if not order_id:
                return JsonResponse({"error": "Order ID not found in session"}, status=400)
            
            # Convert to int if it's a string
            try:
                order_id = int(order_id)
            except (ValueError, TypeError):
                return JsonResponse({"error": "Invalid order ID format"}, status=400)
            
            order = models.Order.objects.get(id=order_id)
            
            # Check if payment already exists
            if hasattr(order, 'payment'):
                return JsonResponse({"message": "Payment already exists"}, status=200)
            
            # Get payment intent details
            payment_intent_id = session.get('payment_intent')
            amount_total = Decimal(session.get('amount_total', 0)) / Decimal(100)  # Convert from cents to dollars
            
            # Create Payment record
            payment = models.Payment.objects.create(
                customer=order.customer,
                order=order,
                amount=amount_total,
                method='stripe',
                transaction_id=payment_intent_id or session.get('id', '')
            )
            
            # Update order status to paid
            order.status = 'paid'
            order.save()
            
            return JsonResponse({"message": "Payment processed successfully", "payment_id": payment.id}, status=200)
            
        except models.Order.DoesNotExist:
            return JsonResponse({"error": "Order not found"}, status=404)
        except Exception as e:
            return JsonResponse({"error": f"Error processing payment: {str(e)}"}, status=500)
    
    elif event['type'] == 'payment_intent.succeeded':
        # Handle successful payment intent
        payment_intent = event['data']['object']
        return JsonResponse({"message": "Payment intent succeeded"}, status=200)
    
    else:
        # Unhandled event type
        return JsonResponse({"message": f"Unhandled event type: {event['type']}"}, status=200)



############### DASHBOARD ##################



@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_total_sales(request):
    total_sales_value = models.Payment.objects.aggregate(total_sales = Sum('amount'))['total_sales']
    return Response({'total_sales':total_sales_value},status=status.HTTP_200_OK) if total_sales_value is not None else 0


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_all_orders_num(request):
    orders_num = models.Order.objects.count()
    orders_num_pending = models.Order.objects.filter(status = 'pending').count()
    orders_num_paid = models.Order.objects.filter(status = 'paid').count()
    orders_num_delivered = models.Order.objects.filter(status = 'delievered').count()
    orders_num_shipped = models.Order.objects.filter(status = 'shipped').count()
    orders_num_cancelled = models.Order.objects.filter(status = 'cancelled').count()
    return Response({'orders':orders_num,
                     'shipped':orders_num_shipped,
                     'delivered':orders_num_delivered,
                     'paid':orders_num_paid,
                     'pending':orders_num_pending,
                     'cancelled':orders_num_cancelled},status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_all_products_num(request):
    products_num = models.Product.objects.count()
    return Response({'total_products':products_num},status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_all_users_num(request):
    users_num = models.User.objects.count()
    return Response({'users':users_num},status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_total_stock(request):
    stock_count = models.Product.objects.aggregate(total_stock = Sum('stock'))['total_stock']
    return Response({'total_stock':stock_count},status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_latest_orders(request):
    orders = (
    models.Order.objects
    .select_related('customer') # fixes customer.email
    .prefetch_related(
        Prefetch(
            'items',
            queryset=models.OrderItem.objects.select_related('product')
        )
    )
    .order_by('-id')
)
    paginator = PageNumberPagination()
    paginator.page_size = 10  # Set how many orders you want per page
    
    # 3. Create the "Page" (slice the queryset based on the URL ?page=x)
    result_page = paginator.paginate_queryset(orders, request)

    # 4. Serialize ONLY the data for the current page
    serializer = OrderSerializer(result_page, many=True)

    # 5. Return the response with pagination metadata (Next, Previous, Count)
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_all_reviews(request):
    reviews = models.Review.objects.prefetch_related('customer','product')
    serializer = serializers.ReviewSerializer(reviews,many=True)
    return Response(serializer.data,status=status.HTTP_200_OK)


@api_view(['GET','PATCH'])
@permission_classes([IsAdminUser])
def order_detail_action(request,pk):
    if request.method == 'GET':
        order = get_object_or_404(models.Order.objects.prefetch_related('items__product'),id=pk)
        serializer = serializers.OrderSerializer(order)
        return Response({'data':serializer.data},status=status.HTTP_200_OK)
        
    elif request.method == 'PATCH':
        order = models.Order.objects.get(id=pk)
        order_status = order.status
        new_status = request.data.get('status')
        if order_status == new_status:
            return Response({"message":"status is already the same"},status=status.HTTP_400_BAD_REQUEST)
        
        if new_status == 'paid':
            return Response({"message":"paid can only be put with payment not manually"},status=status.HTTP_402_PAYMENT_REQUIRED)
        else:
            if order_status != 'paid':
                if new_status not in ["cancelled","delivered",'shipped','paid','pending']:
                    return Response({"message":"error in status name"},status=status.HTTP_400_BAD_REQUEST)
                order.status = new_status
                order.save()  
                return Response({'message': 'Order status updated', 'new_status': order.status},status=status.HTTP_200_OK)
            
            return Response ({"message":"you can't change paid orders status"},status=status.HTTP_400_BAD_REQUEST)
            



@api_view(['POST'])
@permission_classes([IsAdminUser])
def create_product(request):
    print(request.data) # Debugging: See what the frontend sent
    # 1. Pass the data (text + image) to the serializer
    serializer = AddProductSerializer(data=request.data)

    # 2. Validate
    if serializer.is_valid():
        serializer.save()
        # Return the new product data (including the new Cloudinary URL)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # If data is bad (missing name, invalid price, etc.)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT','GET','DELETE'])
@permission_classes([IsAdminUser])
def product_detail_action(request, pk):
    # 1. Get the specific product from the DB using the ID (pk)
    product = get_object_or_404(models.Product, id=pk)
    if request.method == 'PUT':
        serializer = DetailProductSerializer(instance=product, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=400)
    
    elif request.method == 'GET':
        serializer = ProductSerializer(product)
        return Response(serializer.data)
    
    else:
        # 2. Delete the object from the database
        product.delete()
        # 3. Return a success message
        return Response({'message': 'Product was deleted successfully!'}, status=200)


### Dashboard Charts
@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_low_chart_info(request):
    #low products in stock < 20
    low_products = models.Product.objects.filter(stock__lte = 20).only('stock','name').order_by('stock')
    serializer = serializers.LowProductSerializer(low_products,many=True)
    return Response({"products":serializer.data},status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_top_sales_chart_info(request):
    top_products = models.Product.objects.filter(
    orderitem__order__status='paid'  # Only count paid orders
    ).annotate(
    sales=Coalesce(Sum('orderitem__quantity'), 0)
    ).order_by('-sales')[:5]

    serializer = serializers.TopSalesSerializer(top_products,many=True)
    return Response({"topSelling":serializer.data},status=status.HTTP_200_OK)
    

@api_view(['GET'])
@permission_classes([IsAdminUser])
def get_sales_orders_chart(request):

# 1. Date Calculation (Same as before)
    six_months_ago = timezone.now() - datetime.timedelta(days=185)
    
    # 2. Database Query
    orders = (
        models.Order.objects
        .filter(created__gte=six_months_ago)
        .annotate(month=TruncMonth('created'))
        .values('month')
        .annotate(
            total_orders=Count('id'),
            total_sales=Sum(F('items__quantity') * F('items__price')) # <--- Change 'total_price' to your field name
        )
        .order_by('month')
    )

    # 3. Create Dictionary for Lookup
    # Structure: {'2025-10': {'count': 50, 'sales': 5000}, ...}
    orders_dict = {}
    for item in orders:
        key = item['month'].strftime('%Y-%m')
        orders_dict[key] = {
            'orders': item['total_orders'],
            'sales': item['total_sales'] or 0 # Handle None if price is null
        }

    # 4. Fill in the "0" Gaps
    final_data = []
    today = timezone.now().date()

    for i in range(5, -1, -1):
        target_month = today.month - i
        target_year = today.year

        if target_month <= 0:
            target_month += 12
            target_year -= 1

        temp_date = datetime.date(target_year, target_month, 1)
        lookup_key = temp_date.strftime('%Y-%m')
        display_name = temp_date.strftime('%B %Y')

        # Get data from dict, OR return default zeros
        stats = orders_dict.get(lookup_key, {'orders': 0, 'sales': 0})

        final_data.append({
            "month": display_name,
            "orders": stats['orders'],
            "sales": stats['sales']
        })

    return Response(final_data)

