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
    readonly_fields = ['owner']
    def save_model(self, request, obj, form, change):
        if not change:
            obj.owner = request.user
        super().save_model(request, obj, form, change)

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
