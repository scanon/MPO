#!/usr/bin/env python
"""
Test commandline parsing
Will permit all parsing to be moved to the meta command where it belongs.
Then methods can stay put functional invocation.
argument layout for mpo:
post
get
delete
not implemented: put
add
step
init
collect
comment
record/meta
help

"""
from __future__ import print_function
import requests
import ast, textwrap
import unittest
import sys,os,datetime
import json
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse
import copy
import argparse
import linecache
import traceback

def PrintException():
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    var = traceback.format_exc()
    return var


def str2bool(v):
    if isinstance(v,bool):
        return v
    return str(v).lower() in ("yes", "true", "t", "1")


class AliasedSubParsersAction(argparse._SubParsersAction):
    """
    Support 'aliases' of commands.
    use
    parser.register('action', 'parsers', AliasedSubParsersAction)
    then subparsers can take aliases=()

    Note, this functionality is added to argparse for python 3.2
    """
    class _AliasedPseudoAction(argparse.Action):
        def __init__(self, name, aliases, help):
            dest = name
            if aliases:
                dest += ' (%s)' % ','.join(aliases)
            sup = super(AliasedSubParsersAction._AliasedPseudoAction, self)
            sup.__init__(option_strings=[], dest=dest, help=help)

    def add_parser(self, name, **kwargs):
        if 'aliases' in kwargs:
            aliases = kwargs['aliases']
            del kwargs['aliases']
        else:
            aliases = []

        parser = super(AliasedSubParsersAction, self).add_parser(name, **kwargs)

        # Make the aliases work.
        for alias in aliases:
            self._name_parser_map[alias] = parser
        # Make the help text reflect them, first removing old help entry.
        if 'help' in kwargs:
            help = kwargs.pop('help')
            self._choices_actions.pop()
            pseudo_action = self._AliasedPseudoAction(name, aliases, help)
            self._choices_actions.append(pseudo_action)

        return parser



class shell_exception(Exception):
    def __init__(self, status, *args, **kwargs):
        self.return_status=status
#        Exception.__init__(self, *args, **kwargs)

#Developers note:
# All print statements except those in mpo_cli.storeresult should go to sys.stderr
# AVOID tabs, use spaces.
#Non-standard dependencies: requests.py, argparse.py
class mpo_methods(object):
    """
    Class of RESTful primitives. I/O is through stdin/stdout.
    Implementation of MPO client side API as described at
    http://www.psfc.mit.edu/mpo/

    Functional invocation:
    import mpo.mpo_methods as m
    m.flags=values #set some defaults, eg m.server=$MPO_HOST
    m.mpo_method(url=url,payload=payload,arg1=arg1,arg2=arg2)
    """

    #Need error handling
    #By giving each method **kwargs in its definition, they will accepts
    #arbitrary sets of keywords arguments that they may or may not act upon.
    #kwargs in body will only contain keyword pars that were not matched in the
    #function call
    POSTheaders = {'content-type': 'application/json'}
    GETheaders= {'ACCEPT': 'application/json'}
    ID='uid'
    WORKID='work_uid'
    PARENTID='parent_uid' #field for object id to which comments and metadata are attached
    MPO_PORT='8080' #not used yet
    WORKID_QRY='workid' #query argument for connection table

    MPO_VERSION='v0'
    WORKFLOW_RT = 'workflow'
    COMMENT_RT  = 'comment'
    METADATA_RT = 'metadata'
    CONNECTION_RT='connection'
    COLLECTION_RT='collection'
    COLLECTION_ELEMENT_RT='collection/{cid}/element'
    DATAOBJECT_RT='dataobject'
    ACTIVITY_RT=  'activity'
    ONTOLOGY_TERM_RT = 'ontology/term'
    ONTOLOGY_INSTANCE_RT = 'ontology/instance'


    def __init__(self,api_url='https://localhost:8080',version='v0',
                 user='noone',password='pass',cert='cert',
                 archive_host='psfcstor1.psfc.mit.edu',
                 archive_user='psfcmpo', archive_key=None,
                 archive_prefix=None, debug=False,filter=False,dryrun=False):

        self.debug=debug
        self.dryrun=dryrun
        self.filter=filter
        self.user=user
        self.password=password
        self.version=version
        self.cert=cert
        self.archive_host=archive_host
        self.archive_user=archive_user
        self.archive_key=archive_key
        self.archive_prefix=archive_prefix
        o=urlparse(api_url)
         #makes a clean url ending in trailing slash
        self.api_url=o.scheme+"://"+o.netloc+o.path+'/'+self.version+'/'
        self.requestargs={'cert':self.cert,'verify':False}

        if self.debug:
            print('cert',cert,file=sys.stderr)
            print('cert',cert,file=sys.stderr)
#            print('#MPO user',self.get_user())
#            print('#MPO server',self.get_server())
            pass
        return


### internal methods ###

    def format(self,result,filter='id'):
        """
        Routine to handle reformatting of responses from submethods. It is aware of the
        internal format returned.
        """

        #check that result is a request object.
        # if isinstance(result,requests.models.Response):

        if self.debug:
            text=''
            if isinstance(result,requests.models.Response):
                text=result.text
            print("format",result,str(type(result)),text,file=sys.stderr)
        if filter=='id':
            output=[]
            if isinstance(result.json(),list):
                if self.debug:
                    print("Caution, response format of 'id' used when result is a list.",file=sys.stderr)
                    print("Returning list of ID's",file=sys.stderr)

                for r in result.json():
                    output.append(str(r[self.ID]))

                if len(output)==1: #if it is a one element list, just return contents.
                    output=output[0]
            else:
                if self.ID in result.json():
                    output=result.json()[self.ID]
        elif filter=='json':
            output=result.json()
        elif filter=='pretty':
            output=json.dumps(result.json(),separators=(',', ':'),indent=4)
        elif filter=='raw':
            output=result
            print('raw type',str(type(output)),file=sys.stderr)
            print('raw dir',dir(output),file=sys.stderr)
        elif filter=='text':
            output=result.text
        else:
            output=result.json()

        return output

# define api methods here. All methods must be declared as method(**kwargs).
# explict arguments are allowed but must be keyword=value, this is required
# for compatibility with the commandline parser invokacion

    def test(self,route='default',*a,**kw):
        "NOP routine. Useful for new subcommand development"
        print('init:',a,kw)
        print('with route', route)
        return


    def get(self,route="",params={},verbose=False,**kwargs):
        import re
        """GET a resource from the MPO API server.

        Keyword arguments:
        params -- python dictionary or a list of tuples
        route -- API route for resource
        """

        #if parameters are present, this is a search
        #requests.py reconstructs the url with the parameters appended
        #in the "?param=val" http syntax
        #JCW check on the params syntax for requests
        #check for dict and str instances, requests expects a dict

        url=self.api_url+route

        if isinstance(params,str): #string repr of a dict
            datadict=ast.literal_eval(params)
        elif isinstance(params,dict):
            datadict=params
        elif isinstance(params,list): #list of key=value strings
            datadict=dict(re.findall(r'(\S+)=(".*?"|\S+)', ' '.join(params) ))
        else:
            #throw error
            datadict={}

        if self.debug or verbose or self.dryrun:
            print('MPO.GET from {u} with headers of {h}, request options, {ra}, and arguments of {a}'.format(
                  u=url,h=self.GETheaders,ra=self.requestargs, a=str(datadict) ) ,file=sys.stderr)

        r = requests.get(url,params=datadict,
                             headers=self.GETheaders,**self.requestargs)
        if self.debug or verbose:
            print('MPO.GET response',r.url,r.status_code,file=sys.stderr)

        r.raise_for_status()

#        if self.filter:
#            r=self.format(r,self.filter)

        return r


    def delete(self,route="",params={},verbose=False,**kwargs):
        """
        Delete a resource.
        Keyword arguments:
        params -- python dictionary or a list of tuples, not supported yet
        route -- API route for resource        
        """
        url=self.api_url+route
        if self.debug or verbose or self.dryrun:
            print('MPO.DELETE from {u} with headers of {h}, request options, {ra}, and arguments of {a}'.format(
                  u=url,h=self.GETheaders,ra=self.requestargs, a=str(datadict) ) ,file=sys.stderr)

        r = requests.delete(url,params=datadict,
                             headers=self.DELETEheaders,**self.requestargs)
        if self.debug or verbose:
            print('MPO.DELETE response',r.url,r.status_code,file=sys.stderr)

        r.raise_for_status()

        return r

    
    def post(self,route="",workflow_ID=None,obj_ID=None,data=None,**kwargs):
        """POST a messsage to an MPO route.
        Used by all methods that create objects in an MPO workflow.

        Keyword arguments:
        workflow_ID -- the workflow being added to
        obj_ID -- the object we are making a connection from
        data -- the object being posted
        """
        #need flexible number of args so you can just post to a url.

        # Need to validate body? No, servers job.
        # We might want to use different headers?
        # handling binary data, or data in a file?
        # requests.post is happy to take those in the data argument but server has to handle it.
        # mongo returns {time:,_id:} by default
        # could parse data so see if starts with file:

        if route=="":
            #throw error
            return

        if isinstance(data,str):
            datadict=ast.literal_eval(data)
        elif isinstance(data,dict):
            datadict=data
        else:
            #throw error
            pass

        url=self.api_url+route

        #if obj_ID: #commented out to permit null for ontology entries
        datadict[self.PARENTID]=obj_ID

        if workflow_ID:
            datadict[self.WORKID]=workflow_ID

        if self.debug:
            print('MPO.POST to {u} with workflow:{wid}, parent:{pid} and payload of {p}'.format(
                  u=url,wid=workflow_ID,pid=obj_ID,p=json.dumps(datadict) ),file=sys.stderr)

        if self.dryrun:
            if not self.debug:
                print('DRYRUN in MPO.POST', file=sys.stderr)
                print('MPO.POST to {u} with workflow:{wid}, parent:{pid} and payload of {p}'.format(
                  u=url,wid=workflow_ID,pid=obj_ID,p=json.dumps(datadict) ),file=sys.stderr)
            return

        # note we convert python dict to json format and tell the server and requests.py
        #    in the header it is JSON
        # requests will actually send the dict directly if headers doesn't declare body type
        try:
            r = requests.post(url, json.dumps(datadict),
                              headers=self.POSTheaders, **self.requestargs)
        except requests.exceptions.ConnectionError as err:
            print("ERROR: Could not connect to server, "+url,file=sys.stderr)
            sys.stderr.write('MPO ERROR: %s\n' % str(err))
            print(" ",file=sys.stderr)
            return 1

        if self.debug:
            ('MPO.POST return type', str(type(r)), r.status_code)

        if r.status_code!=200:
            return r  # do something else here, r.status_code, r.text
        else:
            if self.filter:
                r=self.format(r,self.filter)

            return r


    def init(self,name=None, desc="", wtype='None', **kwargs):
        """
        The INIT method starts a workflow.
        It returns the server response for a new workflow.

        args are:
        name -- name
        desc -- description
        wtype -- workflow type

        """

        if not name:
            return {"status":"error", "uid":"-1"}

        payload={"name":name,"description":desc,"type":wtype}
        r=self.post(self.WORKFLOW_RT,data=payload,**kwargs)
        return r


    def add(self, workflow_ID=None, parentobj_ID=None, **kwargs):
        """
        Add at dataobject to a workflow.

        args are:
        workflow_ID --
        parentobj_ID --
        name --
        desc -- description
        uri -- uri for the data object added
        """

        uri = kwargs.get('uri')
        desc = kwargs.get('desc')
        name = kwargs.get('name')
        if (self.debug):
            print('MPO.ADD', workflow_ID, parentobj_ID, name, desc,uri,kwargs, file=sys.stderr)

        if not (workflow_ID and parentobj_ID):
            print('Invalid workflow or parent to add method',workflow_ID, parentobj_ID, file=sys.stderr)
            exit

        payload={"name":name,"description":desc,"uri":uri}
        return self.post(self.DATAOBJECT_RT,workflow_ID,[parentobj_ID],payload,**kwargs)

    def add_do(self, **kwargs):
        """
        Add a dataobject with no workflow or partentobj_id.
        This data object can then be connected to one or more
        workflows.

        if a data object with this workflow already exists, then return it.

        args are:
        name --
        desc -- description
        uri -- uri for the data object added

        """

        uri = kwargs.get('uri')
        desc = kwargs.get('desc')
        name = kwargs.get('name')
        if (self.debug):
            print('MPO.ADD_DO', name, desc,uri,kwargs, file=sys.stderr)

        payload={"name":name,"description":desc,"uri":uri}
        print ("about to post %s\n"%payload)
        ans=self.post(self.DATAOBJECT_RT,data=payload,**kwargs)

        return ans


    def step(self,workflow_ID=None,parentobj_ID=None,input_objs=None,**kwargs):
        """
        For adding actions
        args:
        workflow_ID --
        parentobj_ID --
        name -- name of activity
        desc -- description
        uri -- uri for the data object added
        input_objs -- array of additional inputs
        """

        if not (workflow_ID and parentobj_ID):
            msg = 'Both the workflow and parent object must be specified'
            print(msg,file=sys.stderr)
            return {'error':-1}

        name=kwargs.get('name')
        desc=kwargs.get('desc')
        uri=kwargs.get('uri')
        inp=[parentobj_ID]
        if input_objs:
            inp.extend(input_objs)

        payload={"name":name,"description":desc,"uri":uri}
        r=self.post(self.ACTIVITY_RT,workflow_ID,inp,payload,**kwargs)
        return r


    def ontology_term(self, term=None, parent_ID=None, specified=None, vtype=None,
                      desc=None, units=None, **kwargs):
        """
        Add terms to the ontology
           args:
           term --
           parent_ID -- term above this one in the hierachy,
                           ie the is adding the the parent terms vocabulary
           desc -- the description of the term
           vtype -- its type
           specified -- boolean
           units -- dimensional units if any
        """
        if specified:
            specified=str2bool(specified)

        payload={"term":term,"description":desc,"value_type":vtype,"specified":specified,"units":units}
        r=self.post(self.ONTOLOGY_TERM_RT,None,parent_ID,payload,**kwargs)
        return r


    def ontology_instance(self,target=None,path=None,value=None,**kwargs):
        """
        Add terms to the ontology instance
          target      ID of annotated object
          path        Path of ontology term type
          value       Value of the term, must conform to ontology contraint
        """

        if target == None or path == None or value == None:
            print("Usage: ontology_instance target path value",file=sys.stderr)
            sys.exit(2)

        payload={"path":path,"value":value}
        r=self.post(self.ONTOLOGY_INSTANCE_RT,None,target,payload,**kwargs)
        return r


    def comment(self,obj_ID=None,comment='empty',**kwargs):
        """Takes a returned record and adds a comment to it.
        In this case, data should be a plain string.
        args:
        obj_ID -- object being commented on
        comment -- string containing the comment
        """

        if obj_ID==None:
            print('No object UID given, or invalid UID given',file=sys.stderr)
            return {'error':-1}

        if not (isinstance(comment,str) or isinstance(comment,unicode)):
            print('Error in mpo_commment, should be a plain string')
            return {'error':-1}

        r=self.post(self.COMMENT_RT,None,obj_ID,data={'content':str(comment)})
        return r


    def meta(self,obj_ID=None,key=None,value=None,**kwargs):
        """Takes a returned record and adds a metadata to it.
        In this case, data should be a plain string.

        args:
        obj_ID -- object being commented on
        key -- key identifying the type of metadata stored
        value -- string containing the stored value
        """
        if not (isinstance(key,str) or isinstance(key,unicode)):
            print('Error in mpo_meta, should be a plain string')
            return -1

        r=self.post(self.METADATA_RT,None,obj_ID,data={'value':str(value),'key':key}, **kwargs)

        return r


    def search(self,route,params,**kwargs):
        """Find objects by query. An supermethod of GET.
        Presently, identical to 'get' but can be generalized.

        Keyword arguments:
        params -- python dictionary
        route -- API route for resource
        """
        #Presently, route is specified but search syntax should be developed.
        #eventually, some specialized target route for searching would be used.

        r=self.get(route,params) # ,params=ast.literal_eval(params))
        return r


    def collection(self, name="New_Collection", desc="", collection=None, remove=False,
                   elements=[], **kwargs):
        """
        Create a new collection of objects from a list of UUIDS.

        args are:
        name -- name
        desc -- description
        elements -- list of UUID strings to initialize collection with (may be empty)
        collection -- UUID of existing collection. If present, name and desc are ignored.
        remove -- if set to True, remove rather than add the element to the collection.
        """

        #in the future, MPO may support updates of values such as name and desc. At that point,
        #specifying a UUID will enable updates of those values. May want to be able to remove element
        #from a collection too.
        #remove option could apply to the entire collection in future api extensions

        #still need some input validation
        if collection: #add to existing collection
            
            if remove:
                for element in elements:
                    payload={"name":name,"description":desc,"elements":elements}
                    r=self.delete(self.COLLECTION_ELEMENT_RT.format(cid=collection)+'/'+element, None,
                                collection, **kwargs)
                               
            else:
                payload={"name":name,"description":desc,"elements":elements}
                r=self.post(self.COLLECTION_ELEMENT_RT.format(cid=collection), None,
                            collection, data=payload, **kwargs)
                
        else:  #make new collection
            payload={"name":name,"description":desc,"elements":elements}
            r=self.post(self.COLLECTION_RT, None, None, data=payload, **kwargs)

        return r


    ### Persistent store methods ###

    def archive(self, protocol=None, *arg, **kw):
        import importlib
        modname= "mpo_ar_%s"%protocol[0]
        mod = importlib.import_module(modname)
        archiver_class=getattr(mod, modname)
        archiver=archiver_class(self)
        args = archiver.archive_parse(protocol[1:])
        return archiver.archive(**args)

    def get_uri(self, uri=None, do_uid=None):
        if do_uid!=None:
            r = self.get("%s/%s"%(self.DATAOBJECT_RT,do_uid))
            do=json.loads(r.text)
            if not isinstance(do, dict):
                raise Exception("data_object query did not return a dictionary")
            uri=do.uri
        elif uri != None:
            r = self.get(self.DATAOBJECT_RT, params={'uri': uri})
            print(r)
        else:
            raise Exception("One of uri or do_uid must be specified")
        return uri

    def restore(self, uri=None, do_uid=None, *arg, **kw):
        import importlib
        uri = self.get_uri(uri=uri, do_uid=do_uid)
        protocol = uri.split(':', 1)
        modname= "mpo_ar_%s"%protocol[0]
        mod = importlib.import_module(modname)
        archiver_class=getattr(mod, modname)
        archiver=archiver_class(self)
        print("restore protocol=%s"%protocol[0])
        print("restore args = %s"%protocol[1])
        return archiver.restore(protocol[1])

    def ls(self, uri=None, do_uid=None, *arg, **kw):
        import importlib
        uri = self.get_uri(uri=uri, do_uid=do_uid)
        protocol = uri.split(':', 1)
        modname= "mpo_ar_%s"%protocol[0]
        mod = importlib.import_module(modname)
        archiver_class=getattr(mod, modname)
        archiver=archiver_class(self)
        print("ls protocol=%s"%protocol[0])
        print("ls args = %s"%protocol[1])
        return archiver.ls(protocol[1])


class mpo_cli(object):
    """
    mpo command line interface to restful primitives.
    Commandline invocation:
    mpo <mpo flags> method <url> <method flags> <payload>
    """

#import foreign classes for methods here

    def __init__(self,api_url='https://localhost:8080',version='v0',
                 user='noone',password='pass',mpo_cert='',
                 archive_host='psfcstor1.psfc.mit.edu',
                 archive_user='psfcmpo', archive_key=None,
                 archive_prefix=None, debug=False, dryrun=False):

        self.debug=debug
        self.dryrun=dryrun
        self.api_url=api_url
        self.user=user
        self.password=password
        self.version = version
        self.cert=mpo_cert
        self.archive_host=archive_host
        self.archive_user=archive_user
        self.archive_key=archive_key
        self.archive_prefix=archive_prefix

        #initialize foreign methods here
        #print('init',mpo_cert,archive_key,file=sys.stderr)
        self.mpo=mpo_methods(api_url,version,debug=self.debug,dryrun=self.dryrun,
                             cert=mpo_cert,archive_key=archive_key)

    def type_uuid(self,uuid):
        if not isinstance(uuid,str):
            msg = "%r is not a valid uuid" % uuid
            raise argparse.ArgumentTypeError(msg)
        return uuid


    def cli(self):

        parser = argparse.ArgumentParser(description='MPO Command line API',
                                         epilog="""Metadata Provenance Ontology project""")


        #global mpo options
        parser.add_argument('--user','-u',action='store',help='''Specify user.''',default=self.user)
        parser.add_argument('--pass','-p',action='store',help='''Specify password.''',
                            default=self.password)
        parser.add_argument('--format','-f',action='store',help='Set the format of the response.',
                            choices=['id','raw','text','json','pretty'], default='id') #case insensitive?
        parser.add_argument('--verbose','-v',action='store_true',help='Turn on debugging info',
                            default=False)
        parser.add_argument('--dryrun','-d',action='store_true',
                            help='Show the resulting POST without actually issuing the request',
                            default=False)
        parser.register('action', 'parsers', AliasedSubParsersAction)

        #method options
        subparsers = parser.add_subparsers(help='commands')

        #get
        get_parser=subparsers.add_parser('get',help='GET from a route')
           #add positional argument which will be passed to func 'route' in 'Namespace' named tuple
        get_parser.add_argument('route',action='store',help='Route of resource to query')
           #add keyword argument passed to func as 'params'
        get_parser.add_argument('-p','--params',action='store',nargs='*',
                                help='Query arguments as key=value')
        get_parser.set_defaults(func=self.mpo.get)

        #post
        post_parser=subparsers.add_parser('post',help='POST to a route')
        post_parser.add_argument('route',action='store',help='Route of resource to query')
        post_parser.add_argument('--params',action='store',
                                 help='Payload arguments as {key:value,key2:value2}')
        post_parser.set_defaults(func=self.mpo.post)

        #init
        init_parser=subparsers.add_parser('init',help='Start a new workflow')
        init_parser.add_argument('-n','--name',action='store',help='''Name to assign the workflow\n.
        Label used on workflow graphs.''', default='NoName')
        init_parser.add_argument('-d','--desc',action='store',help='Describe the workflow')
        init_parser.add_argument('-t','--type',action='store',dest='wtype',
                                 help='Type of workflow, an ontology reference.',
                                 required=True)
        init_parser.set_defaults(func=self.mpo.init)

        #add
        add_parser=subparsers.add_parser('add',help='Add a data object to a workflow.')
#        addio = add_parser.add_mutually_exclusive_group() #needed for child vs parent.
        add_parser.add_argument('workflow_ID', action='store',metavar='workflow')
        add_parser.add_argument('parentobj_ID', action='store',metavar='parent')
        add_parser.add_argument('--name', '-n', action='store')
        add_parser.add_argument('--desc', '-d', action='store', help='Describe the workflow')
        add_parser.add_argument('--uri', '-u', action='store', help='Pointer to dataobject addded')
        add_parser.set_defaults(func=self.mpo.add)

        #step, nearly identical to add
        step_parser=subparsers.add_parser('step',help='Add an action to a workflow.')
        step_parser.add_argument('workflow_ID', action='store',metavar='workflow')
        step_parser.add_argument('parentobj_ID', action='store',metavar='parent')
        step_parser.add_argument('--input', '-i', action='append',dest='input_objs')
        step_parser.add_argument('--name', '-n', action='store', default='UnNamed Object')
        step_parser.add_argument('--desc', '-d', action='store', help='Describe the workflow')
        step_parser.add_argument('--uri', '-u', action='store', help='Pointer to dataobject addded')
        step_parser.set_defaults(func=self.mpo.step)


        #ontology_term
        ontologyTerm_parser=subparsers.add_parser('ontology_term', aliases=( ('define',) ),
                                                  help='Add a term to the vocabulary')
        ontologyTerm_parser.add_argument('term', action='store', help='name of the term')
        ontologyTerm_parser.add_argument('--parent','-p', action='store',dest='parent_ID',
                                         help='Term above this one in the ontology')
        ontologyTerm_parser.add_argument('--desc', '-d', action='store', help='Describe the new term')
        ontologyTerm_parser.add_argument('--vtype','-t', action='store', help='The value type')
        ontologyTerm_parser.add_argument('--units','-u', action='store', help='The units, if any')
        sgroup = ontologyTerm_parser.add_mutually_exclusive_group(required=False)
        sgroup.add_argument('--specified','-s',action='store_true', dest='specified',
                                         help='Boolean',default=None) #default is otherwise false if not set
        sgroup.add_argument('--not-specified','-n',action='store_false', dest='specified',
                                         help='Boolean',default=None)
        ontologyTerm_parser.set_defaults(func=self.mpo.ontology_term)


        #ontology_instance
        ontologyInstance_parser=subparsers.add_parser('ontology_instance', aliases=( ('metadata','annotate') ),
                                                  help='Add a term to the vocabulary')
        ontologyInstance_parser.add_argument('target', action='store', help='ID of annotated object')
        ontologyInstance_parser.add_argument('path', action='store', help='Path of ntology term type')
        ontologyInstance_parser.add_argument('value', action='store',
                                             help='Value of the term, must conform to ontology contraint,')
        ontologyInstance_parser.set_defaults(func=self.mpo.ontology_instance)

        #archive, note all arguments must be processed by the protocol
        archive_parser=subparsers.add_parser('archive',help='Archive a data object.')
        archive_parser.add_argument('--protocol', '-p', action='store',metavar='protocol',
                                   nargs=argparse.REMAINDER)
        archive_parser.set_defaults(func=self.mpo.archive)


        #collect
        collect_parser=subparsers.add_parser('collect',help='Create a new collection')
        collect_parser.add_argument('-n','--name',action='store',help='Name of the collection')
        collect_parser.add_argument('-d','--desc',action='store',help='Describe the collection')
        collect_parser.add_argument('-c','--collection',action='store',
                                    help='specify the collection for additional elements and updates')
        collect_parser.add_argument('-e','--elements',action='store',nargs='*',
                                help='Add a list of elements to the collection')
        collect_parser.set_defaults(func=self.mpo.collection)


        #ls
        ls_parser=subparsers.add_parser('ls',help='list the Archive of a data object.')
        grp = ls_parser.add_mutually_exclusive_group(required=True)
        grp.add_argument('--uri', '-u', action='store')
        grp.add_argument('--do_uid', '-d', action='store')
        ls_parser.set_defaults(func=self.mpo.ls)

        #restore
        ls_parser=subparsers.add_parser('restore',help='restore the Archive of a data object.')
        grp = ls_parser.add_mutually_exclusive_group(required=True)
        grp.add_argument('--uri', '-u', action='store')
        grp.add_argument('--do_uid', '-d', action='store')
        ls_parser.set_defaults(func=self.mpo.restore)


        #comment
        comment_parser=subparsers.add_parser('comment',help='Attach a comment an object.')
        comment_parser.add_argument('obj_ID',action='store',metavar='object',
                                    help='UUID of object to comment on',
                                    type=self.type_uuid)
        comment_parser.add_argument('comment',action='store',help='Text of comment')
        comment_parser.set_defaults(func=self.mpo.comment)

        #meta
        meta_parser=subparsers.add_parser('meta',help='Add an action to a workflow.')
        meta_parser.add_argument('obj_ID',action='store',metavar='object',
                                    help='UUID of object to attach metadata to',
                                    type=self.type_uuid)
        meta_parser.add_argument('key',action='store',
                                    help='metadata type/identifier')
        meta_parser.add_argument('value',action='store',
                                    help='metadata data to add')
        meta_parser.set_defaults(func=self.mpo.meta)


        #search
        search_parser=subparsers.add_parser('search',help='SEARCH the MPO store')
           #add positional argument which will be passed to func 'route' in 'Namespace' named tuple
        search_parser.add_argument('-r','--route',action='store',help='Route of resource to query')
           #add keyword argument passed to func as 'params'
        search_parser.add_argument('-p','--params',action='store',help='Query arguments as {key:value,key2:value2}')
        search_parser.set_defaults(func=self.mpo.search)


        args=parser.parse_args()
        kwargs=copy.deepcopy(args.__dict__)

        #turn on debugging
        if kwargs.get('verbose'):
            self.debug=True
            self.mpo.debug=True

        if kwargs.get('dryrun'):
            self.dryrun=kwargs.get('dryrun')
            self.mpo.dryrun=kwargs.get('dryrun')
            kwargs['format']='raw'

        # strip out 'func' method
        del(kwargs['func'])
        if self.debug:
            print('args',kwargs,args.func,file=sys.stderr)

        try:
            r=args.func(**kwargs)
        except requests.exceptions.HTTPError as e:
            return "Route not found: %s"%args.route
        except:
            return PrintException()

        if 'format' in kwargs:
            r=self.mpo.format(r,filter=kwargs['format'])

        return r


####main routine
if __name__ == '__main__':
    import os

    mpo_version    = os.getenv('MPO_VERSION','v0')
    mpo_api_url    = os.getenv('MPO_HOST', 'https://localhost:8080/') #API_URL
    mpo_cert       = os.getenv('MPO_AUTH', '~/.mpo/mpo_cert.pem')
    archive_host   = os.getenv('MPO_ARCHIVE_HOST', 'psfcstor1.psfc.mit.edu')
    archive_user   = os.getenv('MPO_ARCHIVE_USER', 'psfcmpo')
    archive_key    = os.getenv('MPO_ARCHIVE_KEY', '~/.mporsync/id_rsa')
    archive_prefix = os.getenv('MPO_ARCHIVE_PREFIX', 'mpo-persistent-store/')

    cli_app=mpo_cli(version=mpo_version, api_url=mpo_api_url,
                    archive_host=archive_host, archive_user=archive_user,
                    archive_key=archive_key, archive_prefix=archive_prefix,
                    mpo_cert=mpo_cert)
    result=cli_app.cli()
#    print(json.dumps(result.json(),separators=(',', ':'),indent=4))
    print(result)
