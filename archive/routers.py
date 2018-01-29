class ArchiveRouter(object):
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'ccdlab':
            return 'ccdlab'
        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'ccdlab':
            return 'ccdlab'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        # Allow is both in our app
        if obj1._meta.app_label == 'ccdlab' and obj2._meta.app_label == 'ccdlab':
            return True
        # Allow if neither is our app
        elif 'ccdlab' not in [obj1._meta.app_label, obj2._meta.app_label]:
            return True
        return False

    def allow_syncdb(self, db, model):
        if db == 'ccdlab' or model._meta.app_label == "ccdlab":
            return False # we're not using syncdb on our legacy database
        else: # but all other models/databases are fine
            return True
