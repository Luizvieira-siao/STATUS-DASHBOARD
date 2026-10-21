from django.contrib import admin
from .models import Cartorio, Pasta, Assistente, AccessEvent
admin.site.site_header = 'Status Dashboard'
admin.site.site_title = 'Administração'
admin.site.index_title = 'Gerenciamento'

@admin.register(Cartorio, Pasta, Assistente)
class OwnedAdmin(admin.ModelAdmin):
    list_display = ['nome', 'owner']
    search_fields = ['nome', 'owner__username']
    list_filter = ['owner']
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs if request.user.is_superuser else qs.filter(owner=request.user)
    def get_exclude(self, request, obj=None):
        return [] if request.user.is_superuser else ['owner']
    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            obj.owner = request.user
        super().save_model(request, obj, form, change)
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        # Relations always stay inside the record owner's workspace.
        obj_id = request.resolver_match.kwargs.get('object_id')
        owner = self.model.objects.filter(pk=obj_id).values_list('owner_id', flat=True).first() if obj_id else request.user.pk
        kwargs['queryset'] = db_field.remote_field.model.objects.filter(owner_id=owner)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

@admin.register(AccessEvent)
class AccessEventAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'username', 'event', 'ip']
    list_filter = ['event', 'created_at']
    search_fields = ['username', 'ip']
    readonly_fields = ['user', 'username', 'event', 'ip', 'user_agent', 'created_at']
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
    def has_view_permission(self, request, obj=None): return request.user.is_superuser
    def has_module_permission(self, request): return request.user.is_superuser
