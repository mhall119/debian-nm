from django.shortcuts import redirect

def login_redirect(request):
    url = request.GET.get("url", None)
    if url is None:
        return redirect('home')
    else:
        return redirect(url)

