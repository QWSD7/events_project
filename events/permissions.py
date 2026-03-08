from rest_framework import permissions

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Разрешает редактирование только суперпользователю.
    Остальным - только безопасные методы (GET, HEAD, OPTIONS).
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_superuser)

class IsSuperUser(permissions.BasePermission):
    """
    Разрешает редактирование только суперпользователю.
    Остальным - запрещены любые методы
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_superuser)
