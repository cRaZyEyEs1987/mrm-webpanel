try:
    from .db import fetch_one
    from flask import jsonify, request
except ImportError:
    from db import fetch_one
    try:
        from flask import jsonify, request
    except ImportError:
        pass

class RBAC:
    """Role-Based Access Control for MRM Webpanel."""
    
    @staticmethod
    def is_superadmin(user):
        """Check if user is superadmin."""
        return user.get('role') == 'superadmin'
    
    @staticmethod
    def is_admin(user):
        """Check if user is admin."""
        return user.get('role') in ('admin', 'superadmin')
    
    @staticmethod
    def owns_domain(user_id, domain_id):
        """Check if user owns a domain."""
        domain = fetch_one(
            "SELECT owner_user FROM domains WHERE id=%s",
            (domain_id,)
        )
        
        if not domain:
            return False
        
        return domain['owner_user'] == user_id
    
    @staticmethod
    def can_access_domain(user, domain_id):
        """Check if user can access a domain (owns it or is superadmin)."""
        if RBAC.is_superadmin(user):
            return True
        
        return RBAC.owns_domain(user['user_id'], domain_id)
    
    @staticmethod
    def enforce_domain_ownership(f):
        """Decorator to enforce domain ownership."""
        def wrapper(*args, **kwargs):
            # Expects domain_id in kwargs or request args
            domain_id = kwargs.get('domain_id')
            
            if not domain_id:
                return jsonify({'error': 'domain_id required'}), 400
            
            if not RBAC.can_access_domain(getattr(request, 'current_user', {}), domain_id):
                return jsonify({'error': 'Access denied'}), 403
            
            return f(*args, **kwargs)
        
        return wrapper
