from __future__ import absolute_import, division, print_function, unicode_literals

# from zope.interface import implements
from zope.interface import implementer
from twisted.cred.portal import IRealm, Portal
from twisted.web.guard import BasicCredentialFactory, HTTPAuthSessionWrapper
from twisted.web.resource import IResource
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.checkers import ICredentialsChecker
from twisted.internet.defer import succeed, fail
import crypt
from twisted.cred.error import UnauthorizedLogin

@implementer(IRealm)
class PublicHTMLRealm(object):
    def __init__(self, resource):
        self._resource = resource

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IResource in interfaces:
            return (IResource, self._resource, lambda: None)
        raise NotImplementedError()

@implementer(ICredentialsChecker)
class PasswordDictCredentialChecker(object):
    credentialInterfaces = (IUsernamePassword,)

    def __init__(self, passwords_file):
        pwdf = open(passwords_file)
        self.passwords = {}
        for line in pwdf.readlines():
            self.passwords[line.split(':')[0]] = line.split(':')[1][:-1]
        pwdf.close()

    def requestAvatarId(self, credentials):
        matched = self.passwords.get(credentials.username.decode('ascii'), None)
        if matched and matched == crypt.crypt(credentials.password.decode('ascii'), matched[:2]):
            return succeed(credentials.username)
        else:
            return fail(UnauthorizedLogin("Invalid username or password"))

# compare password,
def cmp_pass(uname, password, storedpass):
    return crypt.crypt(password, storedpass.split('$')[2])

def wrap_with_auth(resource, passwdF, realm="Auth"):
    """
    @param resource: resource to protect
    """
    checkers = [PasswordDictCredentialChecker(passwdF)]

    return HTTPAuthSessionWrapper(Portal(PublicHTMLRealm(resource), checkers), [BasicCredentialFactory(realm)])
