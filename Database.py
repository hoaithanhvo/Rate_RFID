import pymssql
import pymysql
#import psycopg2
import sqlalchemy
import sqlalchemy.sql.default_comparator
import sys
import json
import requests
from enum import Enum

class DBType(Enum):
    SQLSERVER = 0
    MYSQL = 1
    POSTGRESQL = 2
    RESTAPI = 3
    
class Database:
    
    def __init__(self, dbType, ip, port, user, password, db):
        self.dbType = dbType
        self.dbIp = ip
        self.dbPort = port
        self.dbUser = user
        self.dbPass = password
        self.dbDb = db
        
    def set_dbType(self, dbType):
        self.dbType = dbType

    def check_dbserver_alive(self) -> bool:
        if self.dbType == DBType.SQLSERVER:
            return self.check_sqlserver_alive()
        elif self.dbType == DBType.MYSQL:
            return self.check_mysql_alive()
                
    def check_sqlserver_alive(self) -> bool:
        try:
            server = "{0}:{1}".format(self.dbIp, self.dbPort)
            with pymssql.connect(server, self.dbUser, self.dbPass, self.dbDb, 0) as conn:
                return True
        except Exception as ex:
            return False
            
    def check_mysql_alive(self) -> bool:
        connection = pymysql.connect( host = self.dbIp, user = self.dbUser, password = self.dbPass,
                                      db = self.dbDb, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
        try:
            with connection.cursor() as cursor:
                return True
        except Exception as ex:
            return False
        finally:
            connection.close()
        
    # Insert
    def insert(self, table, tagDict):
        if self.dbType == DBType.RESTAPI:
            return self.insert_RestfulApi(table, tagDict)
        
        placeholders = ','.join(['%s'] * len(tagDict))
        columns = ','.join(tagDict.keys())
        command = "INSERT INTO %s ( %s ) VALUES ( %s )" % (table, columns, placeholders)
        if self.dbType == DBType.SQLSERVER:
            return self.insert_sqlserver(command, tagDict)
        elif self.dbType == DBType.MYSQL:
            return self.insert_mysql(command, tagDict)
        elif self.dbType == DBType.POSTGRESQL:
            return self.insert_PostgreSql(command, tagDict)
            
    
    def insert_sqlserver(self, command, tagDict):
        server = "{0}:{1}".format(self.dbIp, self.dbPort)
        try:
            with pymssql.connect(server, self.dbUser, self.dbPass, self.dbDb, 2) as connection:
                with connection.cursor(as_dict=True) as cursor:
                    cursor.execute(command, tuple(tagDict.values()))
                    connection.commit()
                    return 1
        except Exception as ex:
            print ('Insert SQLSERVER Error: {0}'.format(ex))
            print (sys.exc_info())
            return 0
    
    def insert_mysql(self, command, tagDict):
        try:
            connection = pymysql.connect( host = self.dbIp, user = self.dbUser,
                                          password = self.dbPass, db = self.dbDb, port=int(self.dbPort))

            with connection.cursor() as cursor:
                cursor.execute(command, tuple(tagDict.values()))
                connection.commit()
            return True
        except Exception as ex:
            print ('Insert MYSQL Error: {0}'.format(ex))
            return False
        finally:
            connection.close()
            
    def insert_PostgreSql(self, command, tagDict):
        return 0
        """
        try:
            with psycopg2.connect(host = self.dbIp, user = self.dbUser,
                                  password = self.dbPass, database = self.dbDb) as connection:
                connection.autocommit = True
                with connection.cursor(as_dict=True) as cursor:
                    cursor.execute(command, list(tagDict.values()))
                    connection.commit()
                    return 1
        except Exception as ex:
            print ('Insert POSTGRESQL Error: {0}'.format(ex))
            print (sys.exc_info())
            return 0
        """
    
    def insert_RestfulApi(self, url, epc):
        try:
            parameters = {"EPC":epc}
            print (url)
            response = requests.get(url, params=parameters)
            if response.status_code == 200:
                if response.text == "Put - OK":
                    return 'Success'
                else:
                    return response.text
            else:
                err = f"Request failed with status code: {response.status_code}"
                print(err)
                return err
        except Exception as ex:
            err = f"Insert RESTFUL API Error: {format(ex)}"
            print (err)
            print (sys.exc_info())
            return err

    def select_sqlserver(self, storedprocedure, epc):
        server = "{0}:{1}".format(self.dbIp, self.dbPort)
        query = "EXEC %s '%s'" %(storedprocedure, epc)
        try:
            with pymssql.connect(server, self.dbUser, self.dbPass, self.dbDb, 2) as connection:
                with connection.cursor(as_dict=True) as cursor:
                    cursor.execute(query)
                    result = cursor.fetchall()
                    connection.commit()
                    if (len(result) > 0):
                        return result
                    else:
                        return 'NOT FOUND'
        except Exception as ex:
            print ('SQLSERVER Error: {0}'.format(ex))
            print (sys.exc_info())
            return 'ERROR'

    def assignlocation_sqlserver(self, storedprocedure, epc):
        server = "{0}:{1}".format(self.dbIp, self.dbPort)
        query = """\
        DECLARE @b_Success INT;
        DECLARE @n_err INT;
        DECLARE @c_errmsg nvarchar(250);
        EXEC %s '%s', @b_Success = @b_Success OUTPUT, @n_err = @n_err OUTPUT, @c_errmsg = @c_errmsg OUTPUT;
        """%(storedprocedure, epc,)
        try:
            with pymssql.connect(server, self.dbUser, self.dbPass, self.dbDb, 2) as connection:
                with connection.cursor(as_dict=True) as cursor:
                    cursor.execute(query)
                    result = cursor.fetchall()
                    connection.commit()
                    return result
        except Exception as ex:
            print ('SQLSERVER Error: {0}'.format(ex))
            print (sys.exc_info())
            return 'ERROR'

    def inserterror_sqlserver(self, storedprocedure, lists):
        server = "{0}:{1}".format(self.dbIp, self.dbPort)
        query = """\
        DECLARE @b_Success INT;
        DECLARE @n_err INT;
        DECLARE @c_errmsg nvarchar(250);
        EXEC %s '%s','%s','%s',
        @b_Success = @b_Success OUTPUT, @n_err = @n_err OUTPUT, @c_errmsg = @c_errmsg OUTPUT;
        """%(storedprocedure, lists[0], lists[1], lists[2],)
        try:
            with pymssql.connect(server, self.dbUser, self.dbPass, self.dbDb, 2) as connection:
                with connection.cursor(as_dict=True) as cursor:
                    cursor.execute(query)
                    result = cursor.fetchall()
                    connection.commit()
                    return result
        except Exception as ex:
            print ('SQLSERVER Error: {0}'.format(ex))
            print (sys.exc_info())
            return 'ERROR'