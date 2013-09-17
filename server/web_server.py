#!/usr/bin/env python

from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response
import json
import requests
import time
import datetime
from pprint import pprint
import pydot
import re,os
from authentication import get_user_dn

app = Flask(__name__)

MPO_API_SERVER=os.environ['MPO_API_SERVER']
MPO_WEB_CLIENT_CERT=os.environ['MPO_WEB_CLIENT_CERT']
MPO_WEB_CLIENT_KEY=os.environ['MPO_WEB_CLIENT_KEY']
MPO_API_VERSION = 'v0'
API_PREFIX=MPO_API_SERVER+"/"+MPO_API_VERSION
webdebug=True

@app.route("/")
def index():
    #Need to get the latest information from MPO database here
    #and pass it to index.html template 
    dn = get_user_dn(request)
    certargs={'cert':(MPO_WEB_CLIENT_CERT, MPO_WEB_CLIENT_KEY),
              'verify':False, 'headers':{'Real-User-DN':dn}}
    results = False
    try:
	wid=request.args.get('wid', '')

	r=requests.get("%s/workflow"%API_PREFIX, **certargs)
        # need to check the status code
        if r.status_code == 401:
            return redirect(url_for('register', dest_url=request.path))
        else:
	#results = json.loads(r) #results is json object
            results = r.json()
        if webdebug:
            print("results in index")
            pprint(results)
	
	#pagination control
	num_wf=len(results) # number of workflows returned from api call
	
	index=0
	for i in results:	#i is dict
		if wid:
			if wid == i['uid']:
				results[index]['show_comments'] = 'in' #in is the name of the css class to collapse accordion body
		else:
			results[index]['show_comments'] = ''
                pid=i['uid']
                c=requests.get("%s/comment?parent_uid=%s"%(API_PREFIX,pid), **certargs)
                #comments = json.loads(c)
		comments = c.json()

                if webdebug:
                    print("i and c",i,c)
                    print(str(type(c)))
                    print("index:",comments)

		num_comments=0
                if comments == None: #replace null reply in requests body with empty list so below logic still works
                    comments=[]
                for temp in comments: #get number of comments, truncate time string
                    num_comments+=1
                    if temp['time']:
                        time=temp['time'][:16]
                        temp['time']=time

		results[index]['num_comments']=num_comments
		results[index]['comments']=comments
#JCW 19 JUL 2013. Change 'start_time' to 'creation_time'. 'start_time' is not at presently set or returned by db
# need to clarify two different times. index.html does request 'start_time'
# this was throwing an exception because 'start_time' field wasn't found and breaking adding commments or displaying them
#JCW 9 SEP 2013 API exposure of 'creation_time' is 'time' for comments.
		time=results[index]['time'][:16]
		results[index]['time']=time
                cid=requests.get("%s/workflow/%s/alias"%(API_PREFIX,pid), **certargs)
                cid=cid.json()
                if webdebug:
                    print ('web ',cid,cid)
                cid=cid['alias']
                results[index]['alias']=cid
		index+=1
    except Exception, err:
	print "web_server.index()- there was an exception"
	print err
#        pass

    return render_template('index.html', results = results, num_wf = num_wf)


@app.route('/graph/<wid>', methods=['GET'])
@app.route('/graph/<wid>/<format>', methods=['GET'])
def graph(wid, format="svg"):
    dn = get_user_dn(request)
    certargs={'cert':(MPO_WEB_CLIENT_CERT, MPO_WEB_CLIENT_KEY),
              'verify':False, 'headers':{'Real-User-DN':dn}}

    jsfun = """
        <script>
 //               document.getElementById("graph1").addEventListener("click", sendClickToParentDocument, false);
//                document.getElementById("graph1").addEventListener("onmouseover", sendMouseOverToParent, false);
//                document.getElementById("graph1").addEventListener("onmouseout", sendMouseoutToParent, false);
                function sendClickToParentDocument(evt)
                {
                        // SVGElementInstance objects aren't normal DOM nodes, so fetch the corresponding 'use' element instead
                        var target = evt.target;
      
			// call a method in the parent document if it exists
			if (window.parent.svgElementClicked)
				window.parent.svgElementClicked(target);
			else
				alert("You clicked '" + target.id + "' which is a " + target.textContent + " element");
		}

		//get list of nodes for svg xml tag "g" w/ class "node"
		var nodelist = document.querySelectorAll("g.node");
		
		//parse nodelist object and add click event function to each node (w/ respective data)
		for (var key in nodelist) {
		  if (nodelist.hasOwnProperty(key)) {
		    var node=nodelist[key];
		    node.addEventListener(
			"click",
			(function(node) {
				return function(event) {
					alert(node.childNodes[4].textContent + " (" + node.childNodes[0].textContent + ")" + " node clicked.");
				}
			})(node),
			false
		    );
		  }
		}

		//alert(document.getElementsByTagName("title")[1].textContent);
		//alert(nodelist[0].childNodes[0])
		//alert(nodelist[0].childNodes[0].textContent)

        </script>
    """

    r=requests.get("%s/workflow/%s/graph"%(API_PREFIX,wid,), **certargs)
    r = r.json()
    nodeshape={'activity':'rectangle','dataobject':'ellipse','workflow':'diamond'}
    graph=pydot.Dot(graph_type='digraph')
    nodes = r['nodes']
    #add workflow node explicitly since in is not a child
    graph.add_node( pydot.Node(wid,label=nodes[wid]['name'],shape=nodeshape[nodes[wid]['type']]))
    for item in r['connectivity']:
        pid=item['parent_uid']
        cid=item['child_uid']
        name=nodes[cid]['name']
        theshape=nodeshape[nodes[cid]['type']]
#        graph.add_node( pydot.Node(cid, label=name, shape=theshape, URL='javascript:postcomment("\N")') )
        graph.add_node( pydot.Node(cid, id=cid, label=name, shape=theshape) )
        if item['child_type']!='workflow':
                graph.add_edge( pydot.Edge(pid, cid) )
    if format == 'svg' :
        ans = graph.create_svg()
    elif format == 'png' :
        ans = graph.create_png()
    elif format == 'gif' :
        ans = graph.create_gif()
    elif format == 'jpg' :
        ans = graph.create_jpg()
    else: 
	return "unsupported graph format", 404
    ans = ans[:-7] + jsfun + ans[-7:]
    response = make_response(ans)

    if format == 'svg' :
        response.headers['Content-Type'] = 'image/svg+xml'
    elif format == 'png' :
        response.headers['Content-Type'] = 'image/png'
    elif format == 'gif' :
        response.headers['Content-Type'] = 'image/gif'
    elif format == 'jpg' :
        response.headers['Content-Type'] = 'image/jpg'
    return response

def getsvgxml(wid):
    dn = get_user_dn(request)
    certargs={'cert':(MPO_WEB_CLIENT_CERT, MPO_WEB_CLIENT_KEY),
              'verify':False, 'headers':{'Real-User-DN':dn}}

    r=requests.get("%s/workflow/%s/graph"%(API_PREFIX,wid,), **certargs)
    r = r.json()
    nodeshape={'activity':'rectangle','dataobject':'ellipse','workflow':'diamond'}
    graph=pydot.Dot(graph_type='digraph')
    nodes = r['nodes']
    #add workflow node explicitly since in is not a child
    graph.add_node( pydot.Node(wid,label=nodes[wid]['name'],shape=nodeshape[nodes[wid]['type']]))
    for item in r['connectivity']:
        pid=item['parent_uid']
        cid=item['child_uid']
        name=nodes[cid]['name']
        theshape=nodeshape[nodes[cid]['type']]
#        graph.add_node( pydot.Node(cid, label=name, shape=theshape, URL='javascript:postcomment("\N")') )
        graph.add_node( pydot.Node(cid, id=cid, label=name, shape=theshape) )
        if item['child_type']!='workflow':
                graph.add_edge( pydot.Edge(pid, cid) )

    ans = graph.create_svg()
    return ans

# adds the raw svg xml to the html template <svg></svg>
@app.route('/connections/<wid>', methods=['GET'])
def connections(wid):
    dn = get_user_dn(request)
    certargs={'cert':(MPO_WEB_CLIENT_CERT, MPO_WEB_CLIENT_KEY),
              'verify':False, 'headers':{'Real-User-DN':dn}}	
    svgdoc=getsvgxml(wid)
    svg=svgdoc[154:] #removes the svg doctype header so only: <svg>...</svg>
    r=requests.get("%s/dataobject?workflow=%s"%(API_PREFIX,wid,), **certargs) #get data on each workflow element
    
    dataobj = r.json()
    if webdebug:
        print("workflow data objects")
        pprint(dataobj)
    return render_template('conn.html', data=dataobj, **locals())

@app.route('/about')
def about():
    return render_template('about.html') 

@app.route('/search')
def search():
    return render_template('search.html')

@app.route('/submit_comment', methods=['POST'])
def submit_comment():
    dn = get_user_dn(request)
    certargs={'cert':(MPO_WEB_CLIENT_CERT, MPO_WEB_CLIENT_KEY),
              'verify':False, 'headers':{'Real-User-DN':dn}}
    try:
        form = request.form.to_dict() #gets POSTed form fields as dict; fields: 'parent_uid','comment'
        form['user_dn'] = dn
        r = json.dumps(form) #convert to json
        if webdebug:
            print('submit comment', r)

        submit = requests.post("%s/comment"%API_PREFIX, r, **certargs)
    except:
        pass
	
    return redirect(url_for('index', wid=form['parent_uid'])) # redirects to a refreshed homepage
                                                                  # after comment submission,
                                                                  # passes workflow ID so that the
                                                                  # comments will show for that workflow

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    dn = get_user_dn(request) 
    certargs={'cert':(MPO_WEB_CLIENT_CERT, MPO_WEB_CLIENT_KEY), 
              'verify':False, 'headers':{'Real-User-DN':dn}}     

    if request.method == 'POST':
	try:
	    form = request.form.to_dict() #gets POSTed form fields as dict
	    form['user_dn'] = dn
	    r = json.dumps(form) #convert to json
	    if webdebug:
		print(r)
	    #submit = requests.post("%s/user"%API_PREFIX, r, **certargs)
	    submit = requests.post("%s/user"%API_PREFIX, r)
	except:
	    pass
    
    return render_template('register.html')

if __name__ == "__main__":
    #adding debug option here, so we can see what is going on.	
    app.debug = True
    #app.run()
    #app.run(host='0.0.0.0', port=8080) #api server
    #app.run(host='0.0.0.0', port=8889) #web server
