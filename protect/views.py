from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import HttpResponse

class IndexView(LoginRequiredMixin, TemplateView):
    template_name = 'protect/index.html'

    def get_context_data(self, **kwargs):
        context=super().get_context_data(**kwargs)
        context['is_author']=self.request.user.groups.filter(name='authors').exists()
        return context

    def test(self, request, *args, **kwargs):
        return HttpResponse('Test view task')


# Create your views here.
