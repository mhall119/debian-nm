from django.contrib import admin
from django.db import models
import django.contrib.admin.widgets as adminwidgets
import backend.models as bmodels


class PersonAdmin(admin.ModelAdmin):
    exclude = ("user",)

admin.site.register(bmodels.Person, PersonAdmin)

class AMAdmin(admin.ModelAdmin):
    pass
admin.site.register(bmodels.AM, AMAdmin)

class LogInline(admin.TabularInline):
    model = bmodels.Log

class ProcessAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.ManyToManyField: { 'widget': adminwidgets.FilteredSelectMultiple("Advocates", False, attrs=dict(rows=10)) }
    }
admin.site.register(bmodels.Process, ProcessAdmin)

class LogAdmin(admin.ModelAdmin):
    exclude = ("changed_by", "process")
admin.site.register(bmodels.Log, LogAdmin)
