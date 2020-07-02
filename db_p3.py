#!/usr/bin/env python

import psycopg2, psycopg2.extras
import datetime

class DB:
    """Class encapsulating the connection to PostgreSQL database"""
    def __init__(self, dbname='ccdlab', dbhost='', dbport=0, dbuser='', dbpassword='', readonly=False):
        connstring = "dbname=" + dbname
        if dbhost:
            connstring += " host="+dbhost
        if dbport:
            connstring += " port=%d" % dbport
        if dbuser:
            connstring += " user="+dbuser
        if dbpassword:
            connstring += " password='%s'" % dbpassword

        self.connect(connstring, readonly)

    def connect(self, connstring, readonly=False):
        self.conn = psycopg2.connect(connstring)
        self.conn.autocommit = True
        self.conn.set_session(readonly=readonly)
        psycopg2.extras.register_default_jsonb(self.conn)
        # FIXME: the following adapter is registered globally!
        psycopg2.extensions.register_adapter(dict, psycopg2.extras.Json)

        self.connstring = connstring
        self.readonly = readonly

    def query(self, string="", data=(), simplify=True, debug=False, array=False):
        if self.conn.closed:
            print("Re-connecting to DB")
            self.connect(self.connstring, self.readonly)

        cur = self.conn.cursor(cursor_factory = psycopg2.extras.DictCursor)

        if debug:
            print(cur.mogrify(string, data))

        if data:
            cur.execute(string, data)
        else:
            cur.execute(string)

        try:
            result = cur.fetchall()
            # Simplify the result if it is simple
            if array:
                # Code from astrolibpy, https://code.google.com/p/astrolibpy
                strLength = 10
                __pgTypeHash = {
                    16:bool,18:str,20:'i8',21:'i2',23:'i4',25:'|S%d'%strLength,700:'f4',701:'f8',
                    1042:'|S%d'%strLength,#character()
                    1043:'|S%d'%strLength,#varchar
                    1700:'f8' #numeric
                }

                desc = cur.description
                names = [d.name for d in desc]
                formats = [__pgTypeHash.get(d.type_code, '|O') for d in desc]

                table = np.recarray(shape=(cur.rowcount,), formats=formats, names=names)

                for i,v in enumerate(result):
                    table[i] = tuple(v)

                return table
            elif simplify and len(result) == 1:
                if len(result[0]) == 1:
                    return result[0][0]
                else:
                    return result[0]
            else:
                return result
        except:
            # Nothing returned from the query
            return None

    def log(self, message, time=None, source=None, type='info'):
        """Store message to log table. Time is assumed to be in UTC scale, default to present moment."""
        if time is None:
            time = datetime.datetime.utcnow()

        if not source:
            source = ''

        self.query('INSERT INTO log (time, source, type, message) VALUES (%s, %s, %s, %s);', (time, source, type, message))
