# file : db.py

import psycopg2 as psycopg
import psycopg2.extras as psyext
import sqlalchemy.pool as pool
import sys
import simplejson as json #plays nice with named tuples from psycopg2
import uuid
import datetime
import os
import textwrap
from collections import defaultdict

dbdebug=False


#  list of valid query fields and their mapped name in the table, Use
#  of a dictionary permits different fields in the query than are in
#  the database tables query_map is a dictionary of dictionaries
#  indexed by the table name. The first field is the query string and
#  the second is the table column name. Technically, this can support
#  aliases by providing a second index that maps to the same column
#  name. If it is not is this dictionary, it is ignored. This provides
#  some protection from SQL injection

query_map = {'workflow':{'name':'name', 'description':'description',
                         'uid':'w_guid','user_uid':'u_guid',
                         'composite_seq':'comp_seq', 'time':'creation_time',
                         },
             'collection':{'name':'name', 'description':'description', 'uid':'c_guid',
                           'user_uid':'u_guid', 'time':'creation_time'},
             'collection_elements':{'parent_uid':'c_guid','uid':'e_guid',
                                    'user_uid':'u_guid', 'time':'creation_time'},
             'comment' : {'content':'content', 'uid':'cm_guid', 'time':'creation_time',
                          'type':'comment_type', 'parent_uid':'parent_GUID',
                          'ptype':'parent_type','user_uid':'u_guid'},
             'mpousers' : {'username':'username', 'uid':'uuid', 'firstname': 'firstname',
                           'lastname':'lastname','email':'email','organization':'organization',
                           'phone':'phone','dn':'dn','time':'creation_time'},
             'activity' : {'name':'name', 'description':'description', 'uid':'a_guid',
                           'work_uid':'w_guid', 'time':'creation_time','user_uid':'u_guid',
                           'start':'start_time','end':'end_time', 'uri':'uri',
                           'status':'completion_status'},
             'activity_short' : {'w':'w_guid'},
             'dataobject' : {'name':'name', 'description':'description','uri':'uri','uid':'do_guid',
                             'source_uid':'source_guid','time':'creation_time', 'user_uid':'u_guid'},
             'dataobject_instance' : {'do_uid':'do_guid', 'uid':'doi_guid',
                                      'time':'creation_time', 'user_uid':'u_guid','work_uid':'w_guid'},
             'dataobject_instance_short': {'w':'w_guid'},
             'metadata' : {'key':'name', 'uid':'md_guid', 'value':'value', 'key_uid':'type',
                           'user_uid':'u_guid', 'time':'creation_time',
                           'parent_uid':'parent_guid', 'parent_type':'parent_type'},
             'metadata_short' : {'n':'name', 'v':'value', 't':'type', 'c':'creation_time' },
             'ontology_terms' : {'uid':'ot_guid','name':'name', 'description':'description',
                                 'parent_uid':'parent_guid', 'type':'value_type',
                                 'units':'units','specified':'specified',
                                 'user_uid':'added_by','time':'date_added'},
             'ontology_instances' : {'uid':'oi_guid','parent_uid':'target_guid','value':'value',
                                     'term_uid':'term_guid','time':'creation_time','user_uid':'u_guid'}
         }


conn_string=""
mypool=None

def init(conn_str):
    global conn_string,mypool
    conn_string=conn_str
    print('DB in init connection made: ',conn_string)
    mypool  = pool.QueuePool(get_conn, max_overflow=10, pool_size=25)#,echo='debug')



def get_conn():
    c = psycopg.connect(conn_string)
    return c


def processArgument(a):
    """
    Handle arguments in GET queries. If in double quotes, strip quotes and pass as literal search.
    Otherwise interpret possible wildcards. Spaces between words are treated as wildcards.
    """
    #protect against empty input
    if not a: return a

    if (not isinstance(a,str)) and (not isinstance(a,unicode)):
        print('DBERROR: processArgument called with non-string argument. Converting to string.',str(a),str(type(a)) )
        a=str(a)

    if a[0]=='"' and a[-1]=='"':
        qa=a[1:-1]
    else:
        qa=a.replace(' ','%')
        qa=a.replace('&','\&')
        qa=a.replace('\\','\\\\')

    return qa


def echo(table,queryargs={}, dn=None):
    """
    Dummy function to test route and api method construction
    """
    queryargs['table']=table
    return json.dumps(queryargs)

def getRecordTable(id, dn=None):
    '''
    Given a record id return the table that record is in.
    '''
    if not id: return None
    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    # conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)

    q=''
    v=()
    for k,l in query_map.iteritems():
        if l.has_key('uid') and k!='collection_elements':
            q+="select distinct %s as table from "+k+" where "+l['uid']+"=%s"
            v+=k,id
            q+=' union '

    q=q[:-7]
    # execute our Query
    cursor.execute(q,v)
    # retrieve the records from the database
    table = cursor.fetchone()['table']
    # Close communication with the database
    cursor.close()
    conn.close()

    return table

def deleteCollection(queryargs={}, dn=None):
    '''
    Given a collection id delete it and its associated elements from the db
    '''
     # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    # conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)
    #delete the collection elements (could be none)
    cursor.execute('delete from collection_elements where '+query_map['collection_elements']['parent_uid']+'=%s',(queryargs['uid'],))
    #delete the collection
    cursor.execute('delete from collection where '+query_map['collection']['uid']+'=%s',(queryargs['uid'],))
    rc = cursor.rowcount

    conn.commit()
    cursor.close()
    conn.close()

    if rc and rc != -1:
        return {'uid':queryargs['uid']}
    else:
        return {}


def deleteCollectionElement(queryargs={}, dn=None):
    '''
    Given a collection element id delete it from the db
    '''
     # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    # conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)
    #delete the collection element
    cursor.execute('delete from collection_elements where '+query_map['collection_elements']['parent_uid']+'=%s and '+query_map['collection_elements']['uid']+'=%s',(queryargs['parent_uid'],queryargs['uid']))
    rc = cursor.rowcount

    conn.commit()
    cursor.close()
    conn.close()

    if rc and rc != -1:
        return {'uid':queryargs['uid']}
    else:
        return {}


def deleteOntologyTerms(queryargs={}, dn=None):
    '''
    Given a record id delete the record from the db.
    '''
    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    # conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)
    if queryargs.has_key('uid'):
        cursor.execute('select * from ontology_terms where '+query_map['ontology_terms']['uid']+'=%s',(queryargs['uid'],))
    else:
        if queryargs.has_key('path'):
            cursor.execute('select * from ontology_terms where '+query_map['ontology_terms']['uid']+"=getTermUidByPath('"+processArgument(queryargs['path'])+"')")
    if cursor.rowcount and cursor.rowcount != -1:
        # retrieve the records from the database
        r = cursor.fetchone()
        print(r)
    else:
        r=[]
    # Close communication with the database
    cursor.close()
    conn.close()

    return r


def getRecord(table,queryargs={}, dn=None):
    '''
    Generic record retrieval. Handles GET requests for all tables.
    Use as a template for route specific behavior.

    Retrieve a record based on join of restrictions in query arguments.
    To get a specific record, call with {'uid':id}.
    id overrides any query arguments since it specifies an exact record. You can get an empty
    replay with conflicting restrictions in queryargs. This function should be called with either
    id or queryarg arguments.
    '''

    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    # conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)

    q = 'SELECT'
    qm = query_map[table]
    for key in qm:
        q+=' a.'+qm[key]+' AS '+key+','

    # do we want this line now? username is not in the API interface
    # except for mpousers this line adds a username field to each
    # record returned in addition to the user_uid currently, this is
    # not defined in the API
    q=q[:-1]+', b.username' #remove trailing comma

    ##COMMENT and METADATA special handling
    if (table == 'comment' or table == 'metadata') and queryargs.has_key('uid') and type(queryargs['uid']) == 'uuid':
        q+=', work_uid'

    q+=' FROM '+table+' a, mpousers b '
    if (table == 'comment' or table == 'metadata') and queryargs.has_key('uid')  and type(queryargs['uid']) == 'uuid':
        q+=", getWID('"+processArgument(queryargs['uid'])+"') as work_uid "

    #map user and filter by query
    q+="where a."+qm['user_uid']+"=b.uuid"
    v=()
    for key in query_map[table]:
        #handle time specially
        if key == 'time': continue
        if queryargs.has_key(key):
            qa=processArgument(queryargs[key])
            if not qa or qa == 'None':
                q+=" and CAST("+qm[key]+" as text) is Null"
            else:
                q+=" and CAST("+qm[key]+" as text) ILIKE %s"
                v+=('%'+qa+'%',)
    if queryargs.has_key('time'):
        try:
            (start,end)=tuple(queryargs['time'].split(','))
            if start:
                q+=' and a.creation_time >= %s'
                v+=(start,)
            if end:
                q+=' and a.creation_time <= %s'
                v+=(end,)
        except ValueError:
            pass

    ##ONTOLOGY/TERMS handling
    ontology_terms = []
    if table == 'ontology_terms' and queryargs.has_key('path'):
        q+= " and ot_guid=getTermUidByPath('"+processArgument(queryargs['path'])+"')"
    if table != 'mpousers':
        if queryargs.has_key('username'):
            q+=' and b.username ilike %s'
            v+=('%'+queryargs['username']+'%',)
        if queryargs.has_key('lastname'):
            q+=' and b.lastname ilike %s'
            v+=('%'+queryargs['lastname']+'%',)
        if queryargs.has_key('firstname'):
            q+=' and b.firstname ilike %s'
            v+=('%'+queryargs['firstname']+'%',)
    if queryargs.has_key('term'):
        (s,t) = getSelectionByTerms(json.loads(queryargs['term']))
        q+=' and '+query_map[table]['uid']+' in '+s
        v+=t

    if dbdebug:
        print('get query for route '+table+': '+q)

    # execute our Query
    cursor.execute(q,v)
    # retrieve the records from the database
    if queryargs.has_key('uri'):
        records = [x for x in cursor.fetchall() if x.get('uri') == queryargs.get('uri')]
    else:
        records = cursor.fetchall()
    # Close communication with the database
    cursor.close()
    conn.close()

    if table == 'ontology_terms' and len(ontology_terms):
        terms=[x for x in records if not x.parent_uid]
        #terms = []  #JCW the following returns a [None] list. harmless but should be fixed.
        #[terms.append(x) for x in records if not x.parent_uid]
        if len(terms) != 1:
            return None

        parent = terms[0]

        for i,o in list(enumerate(ontology_terms[1:])):
            terms=[x for x in records if x.name == o and x.parent_uid == parent.uid]
            #terms = []
            #[terms.append(x) for x in records if x.name == o and x.parent_uid == parent.uid]
            if len(terms) != 1:
                return None
            parent = terms[0]

        records = parent

    return records


def getWorkflowType(id,queryargs={},dn=None):
    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    # conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)

    cursor.execute("select value from ontology_instances where target_guid=%s and term_guid=getTermUidByPath('/Workflow/Type')",(id,))
    records = cursor.fetchone()
    # Close communication with the database
    cursor.close()
    conn.close()

    return records['value']


def getSelectionByTerms(terms):
    conn = mypool.connect()
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)
    v=()
    q='('
    d = defaultdict(list)
    for key in terms:
        if key.has_key('uid'):
            d[key['uid']].append(key['value'])
        elif key.has_key('path'):
            cursor.execute('select getTermUidByPath(%s) as uid',(key['path'],))
            d[cursor.fetchone()['uid']].append(key['value'])
    for k,l in d.iteritems():
        s = 'select target_guid from ontology_terms a, ontology_instances c where c.term_guid=a.ot_guid and ('
        for m in l:
            s+= '('+query_map['ontology_terms']['uid']+'=%s'+' and '+query_map['ontology_instances']['value']+'=%s) or '
            v+=(k,m)
        q+=s[:-4]+') intersect '
    q=q[:-11]+')'
    cursor.close()
    conn.close()

    return (q,v)

def getOntologyTermCount(table=None,queryargs={},dn=None):
    """
    Returns the count of ontology terms by instance values.
    """

    #Construct query for database
    q = 'SELECT a.ot_guid AS uid, a.parent_guid AS parent_uid, a.name AS name, c.value, count(*) FROM ontology_terms a, mpousers b, ontology_instances c'

    if table and query_map.has_key(table) and table not in ('ontology_terms','mpousers','ontology_instances'):
        q+=', '+table+' d where c.term_guid=a.ot_guid and c.target_guid=d.'+query_map[table]['uid']+' and d.'+query_map[table]['user_uid']+'=b.uuid'
    else:
        q+=' where c.term_guid=a.ot_guid'
    v=()
    if table and query_map.has_key(table) and table not in ('ontology_terms','mpousers','ontology_instances'):
        for key in query_map[table]:
            #handle time specially
            if key == 'time': continue
            if queryargs.has_key(key):
                q+=' and CAST(d.'+query_map[table][key]+' as text) ilike %s'
                v+=('%'+queryargs[key]+'%',)
    elif not table:
        for key in query_map['ontology_instances']:
            #handle time specially
            if key == 'time': continue
            if queryargs.has_key(key):
                q+=' and CAST(c.'+query_map['ontology_instances'][key]+' as text) ilike %s'
                v+=('%'+queryargs[key]+'%',)
    for key in query_map['mpousers']:
        if key == 'time': continue
        if queryargs.has_key(key):
            q+=' and CAST(b.'+query_map['mpousers'][key]+' as text) ilike %s'
            v+=('%'+queryargs[key]+'%',)
    if queryargs.has_key('time'):
        try:
            (start,end)=tuple(queryargs['time'].split(','))
            t='d' if table and query_map.has_key(table) and table not in ('ontology_terms','mpousers','ontology_instances') else 'c'
            if start:
                q+=' and '+t+'.creation_time >= %s'
                v+=(start,)
            if end:
                q+=' and '+t+'.creation_time <= %s'
                v+=(end,)
        except ValueError:
            pass
    if queryargs.has_key('term'):
        (s,t) = getSelectionByTerms(json.loads(queryargs['term']))
        q+=' and target_guid in '+s
        v+=t

    q+=' group by uid, parent_uid, a.name, c.term_guid,value order by a.name,c.value'
    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    # conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)
    # execute our Query
    cursor.execute(q,v)
    # retrieve the records from the database
    records = cursor.fetchall()
    # Close communication with the database
    cursor.close()
    conn.close()

    return records


def getOntologyTermTree(id='0',dn=None):
    """
    Constructs a tree from the ontology terms and returns
    structure suitable for parsing into graph or menu.
    Return is as a python dictionary (not JSON).
    """
    try:
        import treelib as t
    except Exception as e:
        print('Tree generation requires treelib.py')
        return {'status':'Not supported','error_message':str(e)}

    import types #for patching method

    #method patch dictionary method in treelib for this object only to provide data info as well
    def to_dict(self, nid=None, key=None, reverse=False):
        """transform self into a dict"""

        nid = self.root if (nid is None) else nid
        #print('adding',nid,self[nid].data)
        tree_dict = {self[nid].tag: { "children":[] , "data":self[nid].data } }

        if self[nid].expanded:
            queue = [self[i] for i in self[nid].fpointer]
            key = (lambda x: x) if (key is None) else key
            queue.sort(key=key, reverse=reverse)

            for elem in queue:
                tree_dict[self[nid].tag]["children"].append(
                    self.to_dict(elem.identifier))

            if tree_dict[self[nid].tag]["children"] == []:
                tree_dict = {self[nid].tag: { "data":self[nid].data } }

            return tree_dict


    ###Unfortunately, it is necessary to retrieve the entire ontology table
    ###to construct even partial trees because the order is unknown
    ###perhaps some research on tree representations in SQL would help

    #Construct query for database
    q = 'SELECT name as name, ot_guid as uid, parent_guid as parent_uid from ontology_terms'

    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    # conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)
    # execute our Query
    cursor.execute(q)
    # retrieve the records from the database
    records = cursor.fetchall()
    # Close communication with the database
    cursor.close()
    conn.close()

    #cursor.fetchall always returns a list
    if isinstance(records,list):
        if len(records)==0: #throw error
            print('query error in Getontologytermtree, no records returned')
            r={"status"    : "error",
               "error_mesg": "query error in Getontologytermtree, no records returned"}
            return r

    ###Create tree structure for each head of the ontology
    #may be multiple trees, they have parent as None
    #we will place them under 'root' node if the whole tree is requested
    ot_tree=t.Tree()
    ot_tree.create_node('root','0')

    #make sure parents always occur before children
    #try to insert, if parent is not in tree, skip
    #repeat until all records are inserted
    while len(records)>0:
        for o in records:
            pid=o['parent_uid']
            if pid==None:
                pid='0'
            try:
                ot_tree.create_node(o['name'],o['uid'],parent=pid,data=o)
                records.remove(o)
            except t.tree.NodeIDAbsentError, e:
                pass #should test for NodeIDAbsentError

    ot_subtree=ot_tree.subtree(id) #get partial tree specified by uid
    #patch the method now for this instance only
    ot_subtree.to_dict=types.MethodType(to_dict, ot_subtree)

    return ot_subtree.to_dict()


def getUser(queryargs={},dn=None):
    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()

    # conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)

    #    q = "select username,uuid,firstname,lastname,email,organization,phone,dn from mpousers"
    #    q = "select * from mpousers"
    # translate field names
    q = "select "
    qm = query_map['mpousers']
    for key in qm:
        q += ' aa.'+qm[key]+' AS '+key+','
    q =  q[:-1] + ' from mpousers as aa '

    #translate query fields
    s=""
    for key in query_map['mpousers']:
        if queryargs.has_key(key):
            qa=processArgument(queryargs[key])
            if (s):
                s+=" and "+ "CAST(%s as text) iLIKE '%%%s%%'" % (query_map['mpousers'][key],qa)
            else:
                s+=" where "+ "CAST(%s as text) iLIKE '%%%s%%'" % (query_map['mpousers'][key],qa)

    if (s): q+=s
    # execute our Query
    if dbdebug:
        print('get query for route '+'user'+': '+q)

    cursor.execute(q)
    # retrieve the records from the database
    records = cursor.fetchall()
    # Close communication with the database
    cursor.close()
    conn.close()

    return records


def addUser(json_request,submitter_dn):
    #The submitter dn will likely be the UI. Of course, this is not the dn we want to add.
    #it should already be in the json_request. Eventually, some ACL should be applied here
    #to determine submitter dn permissions and submitter should be a field in user records. --jcw APR 2015
    objs = json.loads(json_request)
    objs['uid']=str(uuid.uuid4())
    objs['time']=datetime.datetime.now()
#    objs['dn']=dn

    #Check for valid keys against query map, we require all fields for user creation
    reqkeys=sorted([x.lower() for x in  query_map['mpousers'].keys() ] )
    objkeys= sorted([x.lower() for x in  objs.keys() ] )
    if reqkeys != objkeys:
        return '{"status":"error","error_mesg":"invalid or missing fields"}'

    if dbdebug:
        print('adding user:',objs['dn'],'by dn',submitter_dn)

    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)

    # if the dn is already in the db we shouldn't even be here. make sure the
    #  username doesn't exist already
    cursor.execute("select username from mpousers where username=%s",(objs['username'],))
    username = cursor.fetchone()
    if (username):
        msg ={"status":"error","error_mesg":"username already exists", "username":username}

        if dbdebug:
            print(msg)
        return json.dumps(msg)

    q = ("insert into mpousers (" + ",".join([query_map['mpousers'][x] for x in reqkeys]) +
         ") values ("+",".join(["%s" for x in reqkeys])+")")
    v= tuple([objs[x] for x in reqkeys])
    cursor.execute(q,v)
    # add a record in the mpoauth table for this user
    q = "insert into mpoauth (u_guid, read, write) values('%s', true, true)"%objs['uid']
    cursor.execute(q)
    #JCW Example of returning created record. By calling get getUser()
    #method we also get translation to api labels.
    #       cursor.execute('select * from mpousers where uuid=%s ',(objs['uid'],) )
    #records = cursor.fetchone()
    conn.commit()
    cursor.close()
    conn.close()

    #Retrieve the just created record to return it.
    #must close cursor BEFORE invoking another db method.
    #JCW for some strange reason, this only works with a unicode string
    records = getUser( {'uid':unicode(objs['uid'])} )
    #get methods always return a list, but we 'know' this should be one item
    if isinstance(records,list):
        if len(records)==1:
            records = records[0]
        else:
            print('DB ERROR: in addUser, record retrieval failed')
            msg ={"status":"error","error_mesg":"record retrieval failed",
                  "username":username,"uid":objs['uid']}
            print(msg)
            return None

    if dbdebug:
        print('query is ',q,str(v))
        print('uid is ', objs['uid'])
        print('adduser records',records)


    return records


def validReader(dn):
    return checkAccess(dn, read=True)

def validWriter(dn):
    return checkAccess(dn, read=True, write=True)

def checkAccess(dn, read=False, write=False):
    #make sure the user exists in the db and is a reader return true/false
    conn = mypool.connect()

    # conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)

    cursor.execute("select b.read,b.write from mpousers a, mpoauth b where a.dn=%s and a.uuid=b.u_guid",(dn,))
    records = cursor.fetchone()

    if dbdebug:
        print('DBDEBUG:: validuser','conn string', conn_string, 'dn',str(type(dn)),dn,'records',records)
    try:
	if read and write:
            return records['read'] and records['write']
	elif read:
            return records['read']
	else:
            return True
    except:
	return False

def validUser(dn):
    #make sure the user exists in the db. return true/false
    conn = mypool.connect()

    # conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)

    cursor.execute("select username from mpousers where dn=%s",(dn,))
    records = cursor.fetchone()
    if dbdebug:
        print('DBDEBUG:: validuser','conn string', conn_string, 'dn',str(type(dn)),dn,'records',records)
    if (records):
        return True
    else:
        return False


def getWorkflow(queryargs={},dn=None):
    """
    Processes the /workflow route. Handles get query arguments.
    """
    # 'user' requires a join with USER table

    if dbdebug:
        print('DDEBUG getworkflow query ',queryargs)
        if queryargs.has_key('range'):
            therange=queryargs['range']
            print('DDEBUG range is', therange,str(therange))
            qa= tuple(map(int, therange[1:-1].split(',')))
            print('DDEBUG tuple range is',qa)

    #build our Query, base query is a join between the workflow and user tables to get the username
    q = textwrap.dedent("""\
                SELECT a.w_guid as uid, a.name, a.description, a.creation_time as time,
                a.comp_seq as composite_seq, b.firstname, b.lastname, b.username, b.uuid as userid,
                c.value as w_type FROM workflow a, mpousers b, ontology_instances c """)

    #join with ontology_instance table to get workflow type
    q += " WHERE a.u_guid=b.uuid and a.w_guid=c.target_guid and c.term_guid=getTermUidByPath('/Workflow/Type')"
    v=()
    # add extra query filter on workflow type (which is stored in a separate table)
    if queryargs.has_key('type'):
        #q+= " and a.w_guid=c.target_guid and c.value='"+processArgument(queryargs['type'])+"'"
        q+= " and c.value=%s"
        v+=(processArgument(queryargs['type']),)


    #logic here to convert queryargs to additional WHERE constraints
    #query is built up from getargs keys that are found in query_map
    #JCW SEP 2013, would be preferable to group queryargs in separate value tuple
    #to protect from sql injection
    for key in query_map['workflow']:
        if key == 'time': continue
        if dbdebug:
            print ('DBDEBUG workflow key',key,queryargs.has_key(key),queryargs.keys())
        if queryargs.has_key(key):
            qa=processArgument(queryargs[key])
            q+=' and CAST(a.'+query_map['workflow'][key]+' as text) iLIKE %s'
            v+= ('%'+qa+'%',)
    if queryargs.has_key('time'):
        try:
            (start,end)=tuple(queryargs['time'].split(','))
            if start:
                q+=' and a.creation_time >= %s'
                v+=(start,)
            if end:
                q+=' and a.creation_time <= %s'
                v+=(end,)
        except ValueError:
            pass

    if queryargs.has_key('alias'):  #handle composite id queries
    #logic here to extract composite_seq,user, and workflow name from composite ID
    #       q+=" and a.composite_seq='%s'"
        compid =  queryargs['alias']
        if dbdebug:
            print('compid: username/workflow_type/seq:',compid,compid.split('/'))
        compid = compid.split('/')
        q+=" and b.username=%s and c.value=%s and a.comp_seq=%s"
        v+=tuple(compid)

#    if queryargs.has_key('username'): #handle username queries
#        q+=" and b.username='%s'" % queryargs['username']

    if queryargs.has_key('username'):
        q+=' and b.username ilike %s'
        v+=('%'+queryargs['username']+'%',)
    if queryargs.has_key('lastname'):
        q+=' and b.lastname ilike %s'
        v+=('%'+queryargs['lastname']+'%',)
    if queryargs.has_key('firstname'):
        q+=' and b.firstname ilike %s'
        v+=('%'+queryargs['firstname']+'%',)
    if queryargs.has_key('term'):
        (s,t) = getSelectionByTerms(json.loads(queryargs['term']))
        q+=' and w_guid in '+s
        v+=t

    # order by date
    q+=" order by time desc"

    if queryargs.has_key('range'): # return a range
        therange=queryargs['range']
        qa= tuple(map(int, therange[1:-1].split(',')))
        q+=" limit %s offset %s"
        v+=((qa[1]-qa[0]+1),(qa[0]-1),)

    # execute our Query
    if dbdebug:
        print('workflows q',q)

    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    # conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)

    cursor.execute(q,v)

    # retrieve the records from the database and rearrange
    records = cursor.fetchall()
    if dbdebug:
        print('get workflow records',records)
    for r in records:
        r['user']={'firstname':r['firstname'], 'lastname':r['lastname'],
               'userid':r['userid'],'username':r['username']}
        r.pop('firstname')
        r.pop('lastname')
        r.pop('userid')
        #JCW 9 SEP 2014, also add workflow type

        r['type'] = r['w_type']
        r.pop('w_type')

    # Close communication with the database
    cursor.close()
    conn.close()

    return records


def getWorkflowCompositeID(id, dn=None):
    "Returns composite id of the form user/workflow_name/composite_seq"
    wf=getWorkflow({'uid':id})
    compid=''
    #catch exception here if thrown by getWorkflow?
    if len(wf) == 1: #record found
        wf=wf[0] #getWorkflow always returns a list
        compid = {'alias':wf['user']['username']+'/'+wf['type']+'/'+str(wf['composite_seq']),'uid':id}
    if dbdebug:
        print('DBDEBUG: compid ',wf,compid)
    return compid


def getWorkflowElements(id,queryargs={},dn=None):
    """
    Returns datastructure {connectivity: [{parent_uid:, parent_type:, child_uid:, child_type:}... ],
    nodes: [{type:, name:, time:}... ] }
    That describes the workflow as a complete DAG.
    """
    from dateutil import parser

    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    # conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)

    if dbdebug:
        print('DDBEBUG workflowelements query ',queryargs)
        if queryargs.has_key('after'):
            after=queryargs['after']
            print('DDEBUG after value is', after,str(after))
            print('DDEBUG timestamp for after is',parser.parse(after))

    records = {}
    # fetch the nodes from the database
    cursor.execute("select w_guid as uid, name, 'workflow' as type, creation_time from workflow a "+
                   "where w_guid=%s union select doi_guid as uid, b2.name as name, 'dataobject_instance' as type, b1.creation_time "+
                   "from dataobject_instance b1, dataobject b2 where w_guid=%s and b1.do_guid = b2.do_guid union select "+
                   "a_guid as uid, name, 'activity' as type, creation_time from activity c "+
                   "where w_guid=%s order by creation_time desc",(id,id,id))
    r = cursor.fetchall()
    nodes={}
    for n in r:
        nodes[n['uid']]={'type':n['type'],'name':n['name'],'time':n['creation_time']}
    records['nodes']=nodes
    # fetch connectors from the database
    cursor.execute("select parent_guid as parent_uid, parent_type, child_guid as child_uid, "+
                   "creation_time as time, child_type from workflow_connectivity "+
                   "where w_guid=%s order by creation_time", (id,) )
    records['connectivity']=cursor.fetchall()
    # Close communication with the database
    cursor.close()
    conn.close()

    return records


def getWorkflowComments(id,queryargs={},dn=None):
    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    # conn.cursor will return a cursor object, you can use this cursor to perform queries
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)
    q = "select "
    qm = query_map['comment']
    for key in qm:
        q += ' a.'+qm[key]+' AS '+key+','
    q = q[:-1] + (" from comment as a where a.parent_guid in "+
                  "(select w_guid as uid from workflow where w_guid=%s "+
                  "union "+
                  "select doi_guid as uid from dataobject_instance where w_guid=%s "+
                  "union " +
                  "select a_guid as uid from activity where w_guid=%s)" )
    cursor.execute(q,(id,id,id))
    records = cursor.fetchall()
    # get all the comments recursively
    parents = []
    for x in records:
        parents.append(x['uid'])
    #recursively get comments on comments
    while len(parents):
        q = "select "
        for key in qm:
            q+=' a.'+qm[key]+' AS '+key+','
        q=q[:-1]+" from comment as a where a.parent_guid in ( "
        for i in parents:
            q+="%s,"

        q=q[:-1]+")"
        v = tuple(x for x in parents)
        cursor.execute(q,v)
        children = cursor.fetchall()
        parents = []
        for x in children:
            records.append(x)
            parents.append(x['uid'])

    cursor.close()
    conn.close()

    return records


def addRecord(table,request,dn):
    objs = json.loads(request)
    if not objs.has_key('uid'): objs['uid']=str(uuid.uuid4())
    objs['time']=datetime.datetime.now()

    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)
    #get the user id
    cursor.execute("select uuid from mpousers where dn=%s", (dn,))

    objs['user_uid'] = cursor.fetchone()['uuid']
    objkeys= [x.lower() for x in query_map[table] if x in objs.keys() ]
    if dbdebug: print('APIDEBUG: addrecord', objs,objkeys)

    q = ( "insert into "+table+" (" + ",".join([query_map[table][x] for x in objkeys]) +
          ") values ("+",".join(["%s" for x in objkeys])+")" )

    v = tuple(objs[x] for x in objkeys)
    if dbdebug:
        print('DDBEBUG addRecord to ',table)
        print(q,v)

    cursor.execute(q,v)
    #it turns out every object has a parent_uid. i know my fault.
    #if objs.has_key('parent_uid') and objs.has_key('work_uid'):
    if table == 'workflow' or table=='dataobject_instance' or table=='activity':
    #connectivity table
        for parent in objs['parent_uid']:
            wc_guid = str(uuid.uuid4())
            cursor.execute("insert into workflow_connectivity "+
                           "(wc_guid, w_guid, parent_guid, parent_type, child_guid, child_type, creation_time) "+
                           "values (%s,%s,%s,%s,%s,%s,%s)",
                           (wc_guid, objs['work_uid'], parent, getRecordTable(parent), objs['uid'],
                            table, datetime.datetime.now()))
    # Make the changes to the database persistent
    conn.commit()

    records = {}
    records['uid'] = objs['uid']
    # Close communication with the database
    cursor.close()
    conn.close()

    return records


def addCollection(request,dn):
    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)
    c_guid = str(uuid.uuid4())

    #get the user id

    cursor.execute("select uuid from mpousers where dn=%s", (dn,))
    user_id = cursor.fetchone()['uuid']

    p = json.loads(request)
    q = ("insert into collection (c_guid, name, description, u_guid, creation_time) " +
         "values (%s,%s,%s,%s,%s)")
    v= (c_guid, p['name'], p['description'], user_id, datetime.datetime.now())
    if dbdebug:
        print ('DBDEBUG:: addcollection: ',q, v)
    cursor.execute(q,v)

    for e in p['elements']:
        q = ("insert into collection_elements (c_guid, e_guid, u_guid, creation_time) " +
             "values (%s,%s,%s,%s)")
        v= (c_guid, e, user_id, datetime.datetime.now())
        cursor.execute(q,v)

    # Make the changes to the database persistent
    conn.commit()
    cursor.close()
    conn.close()

    records = {} #JCW we are not returning the full record here.
    records['uid'] = c_guid

    return records


def addWorkflow(request,dn):
    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)
    w_guid = str(uuid.uuid4())

    #get the user id
    cursor.execute("select uuid from mpousers where dn=%s", (dn,))
    user_id = cursor.fetchone()['uuid']

    #determine max composite sequence for incrementing.
    #  find all workflows of this type that the users already has and increament the largest composite seq number
    cursor.execute("select MAX(comp_seq) from workflow a, ontology_instances c WHERE c.value=%s and a.U_GUID=%s and c.target_guid=a.w_guid",
               (request['value'], user_id ) )
    count=cursor.fetchone()

    if dbdebug:
        print ("#############count is",str(count),str(count['max']))

    if count['max']:
        seq_no=count['max']+1
    else:
        seq_no=1

    q = ("insert into workflow (w_guid, name, description, u_guid, creation_time, comp_seq) " +
         "values (%s,%s,%s,%s,%s,%s)")
    v= (w_guid, request['name'], request['description'], user_id, datetime.datetime.now(),seq_no)
    cursor.execute(q,v)

    # add the workflow type to the ontology_instance table
    q = ("insert into ontology_instances (oi_guid,target_guid,term_guid,value,creation_time,u_guid) "+
         "values (%s,%s,%s,%s,%s,%s)")
    v=(str(uuid.uuid4()),w_guid,request['type_uid'],request['value'],datetime.datetime.now(),user_id)
    cursor.execute(q,v)

    # Make the changes to the database persistent
    conn.commit()
    records = {} #JCW we are not returning the full record here.
    records['uid'] = w_guid

    # Close communication with the database
    cursor.close()
    conn.close()

    return records


def addMetadata(json_request,dn):
    objs = json.loads(json_request)
    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)
    #get the user id
    cursor.execute("select uuid from mpousers where dn=%s", (dn,))
    user_id = cursor.fetchone()['uuid']

    #get parent object type
    q=textwrap.dedent("""\
             SELECT w_guid  AS uid, 'workflow'   AS type FROM workflow   WHERE w_guid=%s UNION
             SELECT a_guid  AS uid, 'activity'   AS type FROM activity   WHERE a_guid=%s UNION
             SELECT do_guid  AS uid, 'dataobject' AS type FROM dataobject   WHERE do_guid=%s UNION
             SELECT doi_guid AS uid, 'dataobject_instance' AS type FROM dataobject_instance
             WHERE doi_guid=%s
              """)
    pid=objs['parent_uid']
    v=(pid,pid,pid,pid)
    cursor.execute(q,v)
    records = cursor.fetchone()
    if not records: raise ValueError('No record found for adding metadata.')

    #insert record
    md_guid = str(uuid.uuid4())
    q = ("insert into metadata (md_guid,name,value,type,parent_guid,parent_type,creation_time,u_guid) "+
         "values (%s,%s,%s,%s,%s,%s,%s,%s)")
    v= (md_guid, objs['key'], objs['value'], 'text', records['uid'], records['type'],
        datetime.datetime.now(), user_id)
    cursor.execute(q,v)
    # Make the changes to the database persistent
    conn.commit()

    records = {}
    records['uid'] = md_guid
    # Close communication with the database
    cursor.close()
    conn.close()
    return records


def addOntologyClass(json_request,dn):
    objs = json.loads(json_request)
    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)
    #get the user id
    cursor.execute("select uuid from mpousers where dn=%s", (dn,))
    user_id = cursor.fetchone()['uuid']

    oc_uid = str(uuid.uuid4())
    q = ("insert into ontology_classes (oc_uid, name, description, parent_guid, added_by, date_added) "+
         "values (%s,%s,%s,%s,%s,%s,%s)")
    v=(oc_uid,objs['name'],objs['description'],objs['parent_uid'],user_id,datetime.datetime.now())
    cursor.execute(q,v)
    # Make the changes to the database persistent
    conn.commit()

    records = {}
    records['uid'] = oc_guid
    # Close communication with the database
    cursor.close()
    conn.close()
    return records


def addOntologyInstance(json_request,dn):
    objs = json.loads(json_request)
    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)
    #get the user id
    cursor.execute("select uuid from mpousers where dn=%s", (dn,))
    user_id = cursor.fetchone()['uuid']

    oi_guid = str(uuid.uuid4())
    # get the ontology term
    term = getRecord('ontology_terms', {'path':processArgument(objs['path'])}, dn )[0]
    if term['specified']:
        vocab = getRecord('ontology_terms', {'parent_uid':term['uid']}, dn )
        #added term has to exist in the controlled vocabulary.
        valid= tuple(x['name'] for x in vocab)
        if objs['value'] not in valid:
            return None

    # make sure the instance doesn't already exist.
    cursor.execute("select oi_guid from ontology_instances where term_guid=%s and "+
                   "target_guid=%s",(term['uid'],objs['parent_uid']))
    if cursor.fetchone():
        return {}

    q=("insert into ontology_instances (oi_guid,target_guid,term_guid,value,creation_time,u_guid) "+
       "values(%s,%s,%s,%s,%s,%s)")
    v=(oi_guid,objs['parent_uid'],term['uid'],objs['value'],datetime.datetime.now(),user_id)
    cursor.execute(q,v)
    # Make the changes to the database persistent
    conn.commit()
    records = {}
    records['uid'] = oi_guid
    # Close communication with the database
    cursor.close()
    conn.close()

    return records


def modifyOntologyInstance(json_request,dn):
    objs = json.loads(json_request)
    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)
    #get the user id
    cursor.execute("select uuid from mpousers where dn=%s", (dn,))
    user_id = cursor.fetchone()['uuid']

    # get the ontology term
    term = getRecord('ontology_terms', {'path':processArgument(objs['path'])}, dn )
    if not term:
        return {}

    # make sure the instance exists already.
    cursor.execute("select oi_guid from ontology_instances where term_guid=%s and "+
                   "target_guid=%s",(term[0]['uid'],objs['parent_uid']))
    oi_guid=cursor.fetchone()['oi_guid']
    if not oi_guid:
        return {}

    q=("update ontology_instances set value=%s, creation_time=%s, u_guid=%s where oi_guid=%s and target_guid=%s and term_guid=%s")
    v=(objs['value'],datetime.datetime.now(),user_id,oi_guid,objs['parent_uid'],term[0]['uid'])
    cursor.execute(q,v)
    # Make the changes to the database persistent
    conn.commit()
    records = {}
    records['uid'] = oi_guid
    # Close communication with the database
    cursor.close()
    conn.close()

    return records


def getTreePath(bottom,top):
    # get a connection, if a connect cannot be made an exception will be raised here
    conn = mypool.connect()
    cursor = conn.cursor(cursor_factory=psyext.RealDictCursor)

    cursor.execute("with recursive tree_depth(child_guid,parent_guid,path) as (select child_guid,parent_guid,child_guid||'.'||parent_guid as path from workflow_connectivity where child_guid=%s union all select td.child_guid, c.parent_guid, td.path || c.parent_guid || '.' as path from workflow_connectivity as c join tree_depth as td on c.child_guid=td.parent_guid) select path from tree_depth where parent_guid=top",(bottom,top))
    records = cursor.fetchall()
    # Close communication with the database
    cursor.close()
    conn.close()

    return records
