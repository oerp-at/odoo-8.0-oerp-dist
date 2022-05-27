# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (C) Stephane Wirtel
# Copyright (C) 2011 Nicolas Vanhoren
# Copyright (C) 2011 OpenERP s.a. (<http://openerp.com>).
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met: 
# 
# 1. Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer. 
# 2. Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution. 
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# 
##############################################################################

"""
OpenERP Client Library

Home page: http://pypi.python.org/pypi/openerp-client-lib
Code repository: https://code.launchpad.net/~niv-openerp/openerp-client-lib/trunk
"""

import xmlrpclib
import logging
import json
import urllib2
import urllib
import random
import StringIO
import simplejson
import time
import os
import base64
from urlparse import urlparse    

_logger = logging.getLogger(__name__)

def _getChildLogger(logger, subname):
    return logging.getLogger(logger.name + "." + subname)

POLLING_DELAY = 0.25

# EXCEPTION

class ClientException(Exception):
    def __init__(self, error):
      super(ClientException, self).__init__(error)


# JSON HELPER
   
def json_req(url, params):
    data = {
      "jsonrpc": "2.0",
      "params" : params,
      "id": random.randint(0, 1000000000),
    }
    req = urllib2.Request(url=url, data=json.dumps(data), headers={
        "Content-Type":"application/json",
    })
    result = urllib2.urlopen(req)
    result = json.load(result)
    if result.get("error", None):
        raise JsonRPCException(result["error"])
    return result["result"]
    
def json_rpc(url, fct_name, params):
    data = {
        "jsonrpc": "2.0",
        "method": fct_name,
        "params": params,
        "id": random.randint(0, 1000000000),
    }
    req = urllib2.Request(url=url, data=json.dumps(data), headers={
        "Content-Type":"application/json",
    })
    result = urllib2.urlopen(req)
    result = json.load(result)
    if result.get("error", None):
        raise JsonRPCException(result["error"])
    return result["result"]

def json_dump(v):
    return simplejson.dumps(v, separators=(',', ':'))


# HELPER

def printPdf(data, printer=None, context=None):
    fd = None
    if printer:
        fd = os.popen("lp -d " + printer,"wb")
    else:
        fd = os.popen("lp","wb")

    if fd:
        fd.write(data)
        fd.close()


def printPdfBase64(data, printer=None, context=None):
    if data:
        data = base64.decodestring(data)
        printPdf(data, printer=printer, context=context)


                

# LIB

class Connector(object):
    """
    The base abstract class representing a connection to an OpenERP Server.
    """

    __logger = _getChildLogger(_logger, 'connector')

    def __init__(self, protocol, host, port):
        self.protocol = protocol
        self.host = host
        self.port = port

    def get_service(self, service_name):
        """
        Returns a Service instance to allow easy manipulation of one of the services offered by the remote server.

        :param service_name: The name of the service.
        """
        return Service(self, service_name)
    
    def authenticate(self, db, login, password):
        params = { "db" : db,
                   "login" : login, 
                   "password" : password }
        url = "%s://%s:%s/web/session/authenticate" % (self.protocol, self.host, self.port)
        return json_req(url, params)
    
    def get_changes(self, session_id, models, timeout):
        """
        Returns a changes iterator
        """
        return ChangeIterator(self.protocol, self.host, self.port, session_id, models, timeout)

class XmlRPCConnector(Connector):
    """
    A type of connector that uses the XMLRPC protocol.
    """
    PROTOCOL = 'xmlrpc'
    
    __logger = _getChildLogger(_logger, 'connector.xmlrpc')

    def __init__(self, hostname, port=8069):        
        """
        Initialize by specifying the hostname and the port.
        :param hostname: The hostname of the computer holding the instance of OpenERP.
        :param port: The port used by the OpenERP instance for XMLRPC (default to 8069).
        """
        super(XmlRPCConnector,self).__init__("http", hostname, port)
        self.url = 'http://%s:%d/xmlrpc' % (hostname, port)

    def send(self, service_name, method, *args):
        url = '%s/%s' % (self.url, service_name)
        service = xmlrpclib.ServerProxy(url)
        return getattr(service, method)(*args)

class XmlRPCSConnector(XmlRPCConnector):
    """
    A type of connector that uses the secured XMLRPC protocol.
    """
    PROTOCOL = 'xmlrpcs'

    __logger = _getChildLogger(_logger, 'connector.xmlrpcs')

    def __init__(self, hostname, port=8069):
        super(XmlRPCSConnector, self).__init__(hostname, port)
        self.url = 'https://%s:%d/xmlrpc' % (hostname, port)

class JsonRPCException(Exception):
    def __init__(self, error):      
      super(JsonRPCException, self).__init__(json.dumps(error, indent=4))
      self.error = error
    

class ChangeIterator(object):
    def __init__(self, protocol, hostname, port, session_id, models, timeout):
        params = urllib.urlencode({ "session_id" : session_id, "models": json.dumps(models), "timeout" : timeout })
        url = "%s://%s:%s/web/dataset/_changes?%s" % (protocol, hostname, port, params)
        req = urllib2.Request(url=url)        
        self._result = urllib2.urlopen(req)
        self._buffer = StringIO.StringIO()
        
    def __iter__(self):
        return self
    
    def __next__(self):
        return self.next()
    
    def __del__(self):
        self.close()
    
    def close(self):
        if self._result:
            self._result.close()
            self._result = None
    
    def next(self):
        # check result
        if self._result is None:
            raise StopIteration
        
        # read event
        self._buffer.truncate(0)
        while True:
            c = self._result.read(1)
            if not c:
                self._result.close()
                raise StopIteration
            elif c == "\n":
                break
            self._buffer.write(c)

        #parse event
        event = self._buffer.getvalue()         
        if event:
            res = json.loads(event)         
            return res
        
        #nothing to parse
        return None
    

class MessageIterator(object):
    def __init__(self, con, channels, last=0):
        protocol = "http"
        if con.connector.protocol.endswith("s"):
            protocol = "https"
        self.message_url = "%s://%s:%d/longpolling/poll" % (protocol, con.connector.host, con.connector.port)
        self.channels = channels
        self.last = last
            
    def __iter__(self):
        return self
    
    def __next__(self):
        res = self.next()
        if res is None:
            raise StopIteration
        return res
    
    def next(self):
        messages = json_rpc(self.message_url, "call", {"channels": self.channels, "last":self.last})
        for message in messages:
            self.last = max(self.last, message["id"])        
        return messages
    

class JsonRPCConnector(Connector):
    """
    A type of connector that uses the JsonRPC protocol.
    """
    PROTOCOL = 'jsonrpc'
    
    __logger = _getChildLogger(_logger, 'connector.jsonrpc')

    def __init__(self, hostname, port=8069):
        """
        Initialize by specifying the hostname and the port.
        :param hostname: The hostname of the computer holding the instance of OpenERP.
        :param port: The port used by the OpenERP instance for JsonRPC (default to 8069).
        """        
        super(JsonRPCConnector,self).__init__("http", hostname, port)
        self.url = 'http://%s:%d/jsonrpc' % (hostname, port)

    def send(self, service_name, method, *args):
        return json_rpc(self.url, "call", {"service": service_name, "method": method, "args": args})

class JsonRPCSConnector(Connector):
    """
    A type of connector that uses the JsonRPC protocol.
    """
    PROTOCOL = 'jsonrpcs'
    
    __logger = _getChildLogger(_logger, 'connector.jsonrpc')

    def __init__(self, hostname, port=8069):
        """
        Initialize by specifying the hostname and the port.
        :param hostname: The hostname of the computer holding the instance of OpenERP.
        :param port: The port used by the OpenERP instance for JsonRPC (default to 8069).
        """
        super(JsonRPCSConnector,self).__init__("https", hostname, port)
        self.url = 'https://%s:%d/jsonrpc' % (hostname, port)

    def send(self, service_name, method, *args):
        return json_rpc(self.url, "call", {"service": service_name, "method": method, "args": args})

class Service(object):
    """
    A class to execute RPC calls on a specific service of the remote server.
    """
    def __init__(self, connector, service_name):
        """
        :param connector: A valid Connector instance.
        :param service_name: The name of the service on the remote server.
        """
        self.connector = connector
        self.service_name = service_name
        self.__logger = _getChildLogger(_getChildLogger(_logger, 'service'),service_name or "")
        
    def __getattr__(self, method):
        """
        :param method: The name of the method to execute on the service.
        """
        self.__logger.debug('method: %r', method)
        def proxy(*args):
            """
            :param args: A list of values for the method
            """
            self.__logger.debug('args: %r', args)
            result = self.connector.send(self.service_name, method, *args)
            self.__logger.debug('result: %r', result)
            return result
        return proxy

class Connection(object):
    """
    A class to represent a connection with authentication to an OpenERP Server.
    It also provides utility methods to interact with the server more easily.
    """
    __logger = _getChildLogger(_logger, 'connection')

    def __init__(self, connector,
                 database=None,
                 login=None,
                 password=None,
                 user_id=None):
        """
        Initialize with login information. The login information is facultative to allow specifying
        it after the initialization of this object.

        :param connector: A valid Connector instance to send messages to the remote server.
        :param database: The name of the database to work on.
        :param login: The login of the user.
        :param password: The password of the user.
        :param user_id: The user id is a number identifying the user. This is only useful if you
        already know it, in most cases you don't need to specify it.
        """
        self.connector = connector

        self.set_login_info(database, login, password, user_id)
        self.user_context = None
        self.session_id = None
        
        protocol = "http"
        if self.connector.protocol.endswith("s"):
            protocol = "https"
            
        self.message_url = "%s://%s:%d/longpolling/poll" % (protocol, self.connector.host, self.connector.port)

    def set_login_info(self, database, login, password, user_id=None):
        """
        Set login information after the initialisation of this object.

        :param connector: A valid Connector instance to send messages to the remote server.
        :param database: The name of the database to work on.
        :param login: The login of the user.
        :param password: The password of the user.
        :param user_id: The user id is a number identifying the user. This is only useful if you
        already know it, in most cases you don't need to specify it.
        """
        self.database, self.login, self.password = database, login, password

        self.user_id = user_id
        
    def check_login(self, force=True):
        """
        Checks that the login information is valid. Throws an AuthenticationError if the
        authentication fails.

        :param force: Force to re-check even if this Connection was already validated previously.
        Default to True.
        """
        if self.user_id and not force:
            return
        
        if not self.database or not self.login or self.password is None:
            raise AuthenticationError("Credentials not provided")

        # TODO use authenticate instead of login
        self.user_id = self.get_service("common").login(self.database, self.login, self.password)
        if not self.user_id:
            raise AuthenticationError("Authentication failure")
        self.__logger.debug("Authenticated with user id %s", self.user_id)
        
    def get_user_context(self):
        """
        Query the default context of the user.
        """
        if not self.user_context:
            self.user_context = self.get_model('res.users').context_get()
        return self.user_context
    
    def get_model(self, model_name):
        """
        Returns a Model instance to allow easy remote manipulation of an OpenERP model.

        :param model_name: The name of the model.
        """
        return Model(self, model_name)

    def get_service(self, service_name):
        """
        Returns a Service instance to allow easy manipulation of one of the services offered by the remote server.
        Please note this Connection instance does not need to have valid authentication information since authentication
        is only necessary for the "object" service that handles models.

        :param service_name: The name of the service.
        """
        return self.connector.get_service(service_name)
    
    def get_session_id(self):
        """
        Authenticate and returns the session id
        """
        if not self.session_id:
            res = self.connector.authenticate(self.database, self.login, self.password)
            self.session_id = res["session_id"]
            self.user_id = res["uid"]
            self.user_context= res["user_context"]
        return self.session_id
    
    def get_changes(self, models, timeout=5):
        """
        Returns a changes iterator
        :param models: A list of models where getting changes for. For example:
            [{ "name" : "model.name",
               "domain" : [("name" : "funkring")]}]
        """
        self.check_login(False)
        return self.connector.get_changes(self.get_session_id(), models, timeout)
    
    def get_messages(self, channels, last=0):
        return MessageIterator(self, channels, last=last)
    
    def get_report(self, name, ids, datas=None, context=None):
        if not datas:
            datas = {}
            
        report_svc = self.get_service("report")
        report_id =  report_svc.report(self.database,
                                         self.user_id,
                                         self.password,
                                         name, 
                                         ids, 
                                         datas, 
                                         context)
        
        res = None
        while True:
            res = report_svc.report_get(self.database, 
                                                 self.user_id,
                                                 self.password,
                                                 report_id)
            if res["state"]:
                break
            
            time.sleep(POLLING_DELAY)
        
        return res         
    
    def info(self, msg):
        self.__logger.log(logging.INFO, msg)
    
    def warn(self, msg):
        self.__logger.log(logging.WARN, msg)
        
    def error(self, msg):
        self.__logger.log(logging.ERROR, msg)

class AuthenticationError(Exception):
    """
    An error thrown when an authentication to an OpenERP server failed.
    """
    pass

class Model(object):
    """
    Useful class to dialog with one of the models provided by an OpenERP server.
    An instance of this class depends on a Connection instance with valid authentication information.
    """

    def __init__(self, connection, model_name):
        """
        :param connection: A valid Connection instance with correct authentication information.
        :param model_name: The name of the model.
        """
        self.connection = connection
        self.model_name = model_name
        self.__logger = _getChildLogger(_getChildLogger(_logger, 'object'), model_name or "")

    def __getattr__(self, method):
        """
        Provides proxy methods that will forward calls to the model on the remote OpenERP server.

        :param method: The method for the linked model (search, read, write, unlink, create, ...)
        """
        def proxy(*args, **kw):
            """
            :param args: A list of values for the method
            """
            self.connection.check_login(False)
            self.__logger.debug(args)
            result = self.connection.get_service('object').execute_kw(
                                                    self.connection.database,
                                                    self.connection.user_id,
                                                    self.connection.password,
                                                    self.model_name,
                                                    method,
                                                    args, kw)
            if method == "read":
                if isinstance(result, list) and len(result) > 0 and "id" in result[0]:
                    index = {}
                    for r in result:
                        index[r['id']] = r
                    result = [index[x] for x in args[0] if x in index]
            self.__logger.debug('result: %r', result)
            return result
        return proxy

    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, context=None):
        """
        A shortcut method to combine a search() and a read().

        :param domain: The domain for the search.
        :param fields: The fields to extract (can be None or [] to extract all fields).
        :param offset: The offset for the rows to read.
        :param limit: The maximum number of rows to read.
        :param order: The order to class the rows.
        :param context: The context.
        :return: A list of dictionaries containing all the specified fields.
        """
        record_ids = self.search(domain or [], offset, limit or False, order or False, context or {})
        if not record_ids: return []
        records = self.read(record_ids, fields or [], context or {})
        return records


def get_connector(hostname=None, protocol="xmlrpc", port="auto"):
    """
    A shortcut method to easily create a connector to a remote server using XMLRPC.

    :param hostname: The hostname to the remote server.
    :param protocol: The name of the protocol, must be "xmlrpc", "xmlrpcs", "jsonrpc" or "jsonrpcs".
    :param port: The number of the port. Defaults to auto.
    """
    if port == 'auto':
        port = 8069
    if protocol == "xmlrpc":
        return XmlRPCConnector(hostname, port)
    elif protocol == "xmlrpcs":
        return XmlRPCSConnector(hostname, port)
    if protocol == "jsonrpc":
        return JsonRPCConnector(hostname, port)
    elif protocol == "jsonrpcs":
        return JsonRPCSConnector(hostname, port)
    else:
        raise ValueError("You must choose xmlrpc, xmlrpcs, jsonrpc or jsonrpcs")

def get_connection(hostname=None, protocol="xmlrpc", port='auto', database=None,
                 login=None, password=None, user_id=None, url=None):
  
    """
    A shortcut method to easily create a connection to a remote OpenERP server.

    :param hostname: The hostname to the remote server.
    :param protocol: The name of the protocol, must be "xmlrpc", "xmlrpcs", "jsonrpc" or "jsonrpcs".
    :param port: The number of the port. Defaults to auto.
    :param connector: A valid Connector instance to send messages to the remote server.
    :param database: The name of the database to work on.
    :param login: The login of the user.
    :param password: The password of the user.
    :param user_id: The user id is a number identifying the user. This is only useful if you
    :param url: one url which contain all the data e.g. https://user:password@erp.sunhill-technologies.com:8072/database
    already know it, in most cases you don't need to specify it.
    """
    
    if url:      
      purl = urlparse(url)
      port = None
      if purl.scheme == "http":
        protocol = "jsonrpc"
        port = 80
      elif purl.scheme == "https":
        protocol = "jsonrpcs"
        port = 443
        
      hostname = purl.hostname
      port = port or purl.port
      
      login = urllib.url2pathname(purl.username or "")
      if not login:
        raise ClientException("no username")
      
      database = purl.path[1:]
      if not database:
        raise ClientException("no database")
      
      password = urllib.url2pathname(purl.password or "")
      if not password:
        import keyring
        password = keyring.get_password(database, login)
      
    return Connection(get_connector(hostname, protocol, port), database, login, password, user_id)

def add_args(parser):
    parser.add_argument("url", help="url to odoo server and database e.g. https://user:password@erp.sunhill-technologies.com:8072/database")
  
def parse_args(args=None):
    if not args:
      import argparse
      parser = argparse.ArgumentParser(description="Odoo Client")
      add_args(parser)    
      args = parser.parse_args()
    return get_connection(url=args.url)
