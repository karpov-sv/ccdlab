from django.db import connections, transaction
import posixpath

from django.contrib.auth.decorators import permission_required, user_passes_test, PermissionDenied

#@transaction.commit_on_success
def db_query(string, params, db='archive', debug=False, simplify=True):
    connection = connections[db]

    cursor = connection.cursor()
    result = None

    if debug:
        print (cursor.mogrify(string, params))

    try:
        cursor.execute(string, params)
        try:
            result = cursor.fetchall()

            if simplify and len(result) == 1:
                if len(result[0]) == 1:
                    result = result[0][0]
                else:
                    result = result[0]
        except:
            # No data returned
            result = None
    except:
        import traceback
        traceback.print_exc()
        pass
    finally:
        cursor.close()

    return result

def permission_required_or_403(perm, login_url=None):
    """
    Decorator for views that checks whether a user has a particular permission
    enabled, redirecting to the log-in page if neccesary.
    If the raise_exception parameter is given the PermissionDenied exception
    is raised.
    """
    def check_perms(user):
        # First check if the user has the permission (even anon users)
        if user.has_perm(perm):
            return True
        # In case the 403 handler should be called raise the exception
        if user.is_authenticated():
            raise PermissionDenied
        # As the last resort, show the login form
        return False
    return user_passes_test(check_perms, login_url=login_url)

def permission_denied():
    raise PermissionDenied

def has_permission(request, perm):
    return request.user.has_perm(perm)

def assert_permission(request, perm):
    if not request.user.has_perm(perm):
        raise PermissionDenied

def assert_is_staff(request):
    if not request.user.is_staff:
        raise PermissionDenied
