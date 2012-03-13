from django.contrib import admin
from django.db import models
import django.contrib.admin.widgets as adminwidgets
import backend.models as bmodels


class PersonAdmin(admin.ModelAdmin):
    exclude = ("user",)
    search_fields = ("cn", "sn", "email", "uid")

admin.site.register(bmodels.Person, PersonAdmin)

class AMAdmin(admin.ModelAdmin):
    search_fields = ("person__cn", "person__sn", "person__email", "person__uid")
admin.site.register(bmodels.AM, AMAdmin)

class LogInline(admin.TabularInline):
    model = bmodels.Log

class ProcessAdmin(admin.ModelAdmin):
    raw_id_fields = ('manager',)
    filter_horizontal = ("advocates",)
admin.site.register(bmodels.Process, ProcessAdmin)

class LogAdmin(admin.ModelAdmin):
    exclude = ("changed_by", "process")
admin.site.register(bmodels.Log, LogAdmin)
