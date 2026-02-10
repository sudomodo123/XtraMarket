from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from base.models import Product,Review,WishList,CartItem,OrderItem,Order,Category,Tag

class ProductSerializer(ModelSerializer):
    img_url = serializers.CharField(source='img.url', read_only=True)
    average_rating = serializers.FloatField(read_only=True)
    categories = serializers.StringRelatedField(many=True)  # uses __str__ from Category
    tags = serializers.StringRelatedField(many=True)   # uses __str__ from Tag
    class Meta:
        model = Product
        exclude = ['img']
    


class ProductSerializerForWishlist(ModelSerializer):
    average_rating = serializers.FloatField(read_only = True)
    img_url = serializers.SerializerMethodField()
    product_id = serializers.SerializerMethodField()
    class Meta:
        model = Product
        fields = ['final_price','original_price','discount','img_url','average_rating','product_id']
    
    def get_product_id(self,obj):
        return obj.id if obj else None

    def get_img_url(self, obj):
        return obj.img.url if obj.img else None



class WishListSerializer(ModelSerializer):
    products = ProductSerializerForWishlist(many=True,read_only = True)
    class Meta:
        model = WishList
        fields = "__all__"



class RecentReviewSerializer(ModelSerializer):
    customer = serializers.StringRelatedField()
    product = serializers.StringRelatedField()
    class Meta:
        model = Review
        fields = '__all__'



class CartItemSerializer(ModelSerializer):
    subtotal = serializers.FloatField(read_only = True)
    product_name = serializers.SerializerMethodField()
    img_url = serializers.SerializerMethodField()
    product_id = serializers.SerializerMethodField()
    class Meta:
        model = CartItem
        exclude = ['product','cart','id']
    
    def get_product_name(self,obj):
        return obj.product.name if obj.product else None
    
    def get_img_url(self,obj):
        return obj.product.img.url if obj.product.img else None
    
    def get_product_id(self,obj):
        return obj.product.id if obj.product else None



# class OrderSerializer(ModelSerializer):
#     customer = serializers.StringRelatedField()
#     class Meta:
#         model = Order
#         fields = ['id','customer','status','total_price']



class AddProductSerializer(ModelSerializer):
    img_url = serializers.SerializerMethodField()
    categories = serializers.ListField(
        child=serializers.CharField(), write_only=True
    )
    tags = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )
    class Meta:
        model = Product
        fields = ['id','name','description','original_price','discount','stock','img','img_url','categories','tags']

    def create(self, validated_data):
        # 1. Remove categories and tags from the main data
        categories_data = validated_data.pop('categories', [])
        tags_data = validated_data.pop('tags', [])

        # 2. Create the Product first
        product = Product.objects.create(**validated_data)

        # 3. Handle Categories (Assumes categories must exist)
        for cat_name in categories_data:
            # Try to get the category by name
            category,created = Category.objects.get_or_create(name=cat_name)
            product.categories.add(category)

        # 4. Handle Tags (Create if they don't exist - "Get or Create")
        for tag_name in tags_data:
            tag, created = Tag.objects.get_or_create(name=tag_name)
            product.tags.add(tag)

        return product
    
    def get_img_url(self,obj):
        return obj.img.url if obj.img else None
    


class DetailProductSerializer(ModelSerializer):
    img_url = serializers.SerializerMethodField()
    categories = serializers.ListField(
        child=serializers.CharField(), write_only=True
    )
    tags = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False
    )

    class Meta:
        model = Product
        fields = ['id','name','description','original_price','discount','stock','img','img_url','categories','tags']

    def update(self,instance, validated_data):
        # We use .pop() with a default of None to check if the user actually sent this data
        categories_data = validated_data.pop('categories', None)
        tags_data = validated_data.pop('tags', None)

        # 2. Update the standard fields (name, price, stock, etc.)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # 3. Save the main instance updates
        instance.save()

        # 4. Handle Categories (If user provided a new list)
        if categories_data is not None:
            instance.categories.clear() # Clear existing relationships
            for cat_name in categories_data:
                category, _ = Category.objects.get_or_create(name=cat_name)
                instance.categories.add(category)

        # 5. Handle Tags (If user provided a new list)
        if tags_data is not None:
            instance.tags.clear() # Clear existing tags
            for tag_name in tags_data:
                tag, _ = Tag.objects.get_or_create(name=tag_name)
                instance.tags.add(tag)

        return instance

    def get_img_url(self,obj):
        return obj.img.url if obj.img else None



class LowProductSerializer(ModelSerializer):
    class Meta:
        model = Product
        fields = ['id','name','stock']
    


class TopSalesSerializer(ModelSerializer):
    sales = serializers.IntegerField(read_only=True)
    class Meta:
        model = Product
        fields = ['id','name','sales']



class OrderItemSerializer(ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    class Meta:
        model = OrderItem
        fields = ['id', 'product_name', 'quantity', 'price', 'subtotal']



class OrderSerializer(ModelSerializer):
    items = OrderItemSerializer(read_only=True,many=True)
    email = serializers.EmailField(source='customer.email', read_only=True)
    customer = serializers.StringRelatedField()
    
    # 2. Get Total Price: This looks for the 'total_price' property on your Order model
    total_price = serializers.ReadOnlyField(read_only=True)

    class Meta:
        model = Order
        fields = '__all__'
    



class ReviewSerializer(ModelSerializer):
    customer_name = serializers.CharField(source = 'customer.username')
    customer_email = serializers.CharField(source = 'customer.email')
    product_name = serializers.CharField(source = 'product.name')
    class Meta:
        model = Review
        fields = '__all__'

