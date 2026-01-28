import importlib
import pkgutil
from rest_framework.routers import DefaultRouter

def register_all_viewsets(router, viewsets_package):
    """
    Escanea un paquete de ViewSets y registra cada clase terminada en 'ViewSet'
    en el router de DRF de forma automática.
    """
    # Iterar sobre todos los módulos (.py) en el paquete
    for loader, module_name, is_pkg in pkgutil.iter_modules(viewsets_package.__path__):
        # Importar el módulo: api.Viewsets.user_viewset
        module = importlib.import_module(f"{viewsets_package.__name__}.{module_name}")
        
        # Buscar clases dentro del módulo
        for name, cls in vars(module).items():
            if isinstance(cls, type) and name.endswith('ViewSet') and name != 'ModelViewSet':
                # Generar el endpoint: UserViewSet -> users
                # Se puede personalizar la lógica de plurales aquí
                base_name = name.replace('ViewSet', '').lower()
                
                # Manejo básico de plurales (ej: Blitz -> blitzes)
                if base_name.endswith('z'):
                    endpoint = f"{base_name}es"
                elif base_name.endswith('y'):
                    endpoint = f"{base_name[:-1]}ies"
                else:
                    endpoint = f"{base_name}s"
                
                router.register(endpoint, cls, basename=base_name)
    
    return router