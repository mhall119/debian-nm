from django.contrib import admin
import backend.models as bmodels


class PersonAdmin(admin.ModelAdmin):
    pass
admin.site.register(bmodels.Person, PersonAdmin)

class AMAdmin(admin.ModelAdmin):
    pass
admin.site.register(bmodels.AM, AMAdmin)

class LogInline(admin.TabularInline):
    model = bmodels.Log

class ProcessAdmin(admin.ModelAdmin):
    inlines = [
        LogInline
    ]
admin.site.register(bmodels.Process, ProcessAdmin)

#admin.site.register(bmodels.Log, LogAdmin)
