from zope.interface import implements
from twisted.internet.defer import succeed, fail
from twisted.cred.error import UnauthorizedLogin
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.portal import IRealm, Portal
from twisted.web.resource import IResource
from twisted.web.guard import BasicCredentialFactory, HTTPAuthSessionWrapper
from twisted.web.static import File


class PublicHTMLRealm(object):
    implements(IRealm)

    def __init__(self, resource):
        self._resource = resource

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IResource in interfaces:
            return (IResource, self._resource, lambda: None)
        raise NotImplementedError()


class PasswordDictCredentialChecker(object):
    implements(ICredentialsChecker)
    credentialInterfaces = (IUsernamePassword,)

    def __init__(self, passwords):
        self.passwords = passwords

    def requestAvatarId(self, credentials):
        matched = self.passwords.get(credentials.username, None)
        if matched and matched == credentials.password:
            return succeed(credentials.username)
        else:
            return fail(UnauthorizedLogin("Invalid username or password"))


def wrap_with_auth(resource, passwords, realm="Auth"):
    """
    @param resource: resource to protect
    @param passwords: a dict-like object mapping usernames to passwords
    """
    portal = Portal(PublicHTMLRealm(resource),
                    [PasswordDictCredentialChecker(passwords)])
    credentialFactory = BasicCredentialFactory(realm)
    return HTTPAuthSessionWrapper(portal, [credentialFactory])
