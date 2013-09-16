from django.shortcuts import redirect

def login_redirect(request):
    url = request.GET.get("url", None)
    if not url:
        return redirect('/')
    else:
        return redirect(url)

