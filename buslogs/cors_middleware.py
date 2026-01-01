from django.http import HttpResponse

class CustomCorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin")

        if request.method == "OPTIONS":
            response = HttpResponse()
            if origin:
                response["Access-Control-Allow-Origin"] = origin
                response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
                response["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
                response["Vary"] = "Origin"
            return response

        response = self.get_response(request)

        if origin:
            response["Access-Control-Allow-Origin"] = origin
            response["Vary"] = "Origin"

        return response
