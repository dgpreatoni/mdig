from bottle import route, validate, run, request, redirect
from bottle import view
import bottle

from multiprocessing import Process, Queue, JoinableQueue
from threading import Thread
import Queue as q

import os
import sys
import re
import tempfile
import shutil
import datetime

import pdb

import mdig
from DispersalModel import DispersalModel
import MDiGConfig
import GRASSInterface

app = None

reloader = False
if True:
    bottle.debug(True)
    sys.path.insert(0, './mdig/')
    # reloader is nice, but it loads all module code twice and this
    # confuses the GRASS module.
    #reloader = True
# TODO - make this based on where mdig executable is
bottle.TEMPLATE_PATH = ['./mdig/views/', './mdig/' ]
# needed for error template to find bottle

@route('/models/')
def redirect_index():
    redirect('/')

# Which models are currently doing something.
# Each item to have format: [ACTION, state]
models_in_queue = {}

# when the last status headline display completed tasks
last_notice = datetime.datetime.now()

# This queue is used to submit jobs to an mdig process(es) that will run simulations
# and do computational tasks that can be done immediately
work_q = JoinableQueue()

# When the mdig process(es) have completed (either totally or partly) a job
# from the work_q, it will put the results here
results_q = Queue()

# dictionary of models that are being uploaded but have yet to have supporting
# files uploaded
# key: model_name, value:
# { dir: tempdir, "maps": [survival], "CODA": [filename], ...
# }
models_staging = {}

def validate_model_name(mname):
    # Get existing models in repository
    models = mdig.repository.get_models()
    if mname not in models.keys():
        raise ValueError()
    try:
        dm = DispersalModel(models[mname],setup=False)
    except mdig.DispersalModel.ValidationError, e:
        return "Model %s is badly formed" % mname
    return dm 

@route('/models/',method="POST")
def submit_model():
    model_file = request.POST.get('new_model')
    data = model_file.file.read()
    # use ModelRepository to add model, but we'll need to implement a method
    # that accepts a string and uses a temp file as a proxy.
    model_name = ""
    try:
        model_name = add_model_to_staging(data)
    except Exception, e:
        pdb.set_trace()
        if "Model exists" in str(e):
            # TODO provide a force parameter in query string which asks user
            # whether to overwrite model (or just to overwrite the model xml
            # file, and leave the uploaded maps)
            return "Model already exists in staging area"
    # check if model name exists in repository 
    return str(models_staging[model_name])

def process_completed_tasks():
    """ go through all the tasks in models_in_queue and when they were
    completed.
    return those that have been completed since last time this method was
    called.
    """
    global last_notice
    new_last_notice = last_notice
    updates = {}
    time_index = {}
    for m_name, tasks in models_in_queue.items():
        for task in tasks:
            if 'complete' in tasks[task]:
                if tasks[task]['complete'] > last_notice:
                    if m_name not in updates: updates[m_name] = {}
                    updates[m_name][task] = tasks[task]
                    t = tasks[task]['complete']
                    if new_last_notice < t:
                        new_last_notice = t
                    time_index[(m_name,task)]=t
    last_notice = new_last_notice
    k = time_index.keys()
    k.sort(key=lambda x: time_index[x])
    print "updates:" + str(k)
    return k, updates

@route('/models/:model/run',method='POST')
@view('run.tpl')
@validate(model=validate_model_name)
def run_model(model):
    qsize = work_q.qsize()
    m_name = model.get_name()
    exists=False
    global models_in_queue
    if m_name not in models_in_queue:
        models_in_queue[m_name] = {}
    if 'RUN' in models_in_queue[m_name] and 'complete' not in models_in_queue[m_name]:
        exists = True
    else:
        models_in_queue[m_name]['RUN'] = {"approx_q_pos":qsize}
        work_q.put(['RUN',model.get_name(),10])
    task_order, task_updates = process_completed_tasks()
    return dict(model=model, already_exists=exists,
            started = 'started' in models_in_queue[m_name]['RUN'],
            name=mdig.version_string,
            queue_size=qsize,
            task_order=task_order, task_updates = task_updates)

def add_model_to_staging(data):
    """ Create a temporary directory to store a model file and extract required
    files.
    """
    # make temp dir
    temp_model_dir = tempfile.mkdtemp(prefix="mdig_web")
    # write data to actual file
    model_fn = os.path.join(temp_model_dir, "model.xml") 
    f = open(model_fn,'w')
    f.write(data)
    f.close()
    # open temp dir to extract info like name and dependencies
    dm = DispersalModel(model_fn,setup=False)
    name = dm.get_name()
    if name in models_staging:
        shutil.rmtree(temp_model_dir)
        raise Exception("Model exists")
    models_staging[name] = {}
    models_staging[name]["dir"] = temp_model_dir
    maps = dm.get_map_dependencies()
    if len(maps) > 0:
        models_staging[name]["maps"] = maps
    transition_files = dm.get_popmod_files()
    #maps = dm.get_coda_files()
    if len(transition_files) > 0:
        models_staging[name]["ls_transition"] = transition_files
    return name

@route('/')
@view('index.tpl')
def index():
    # Get existing models in repository
    models = mdig.repository.get_models()
    ms=models.keys()[:]
    ms.sort()

    m_list = []
    for m in ms:
        try:
            dm = DispersalModel(models[m],setup=False)
            desc = dm.get_description()
            desc = re.sub("[\\s\\t]+"," ",desc)
            m_list.append((m,desc))
        except mdig.DispersalModel.ValidationError, e:
            print str(e)
            pass
    env = GRASSInterface.get_g().get_gis_env()
    task_order, task_updates = process_completed_tasks()
    return dict(name=mdig.version_string, version=mdig.version,
            v_name=mdig.version_name, models=m_list,
            repo_location=mdig.repository.db,
            grass_env=env,
            task_order=task_order, task_updates = task_updates)

@route('/models/:model',method='GET')
@route('/models/:model',method='POST')
@view('model.tpl')
@validate(model=validate_model_name)
def show_model(model):
    dm=model
    if request.method=="POST":
        to_enable = [int(x) for x in request.POST.getall('enabled')]
        if len(to_enable) != 0:
            i_index=0
            for i in dm.get_instances():
                if i.enabled and i_index not in to_enable:
                    print "changing to false"
                    i.enabled=False
                    i.update_xml()
                if not i.enabled and i_index in to_enable:
                    print "changing to true"
                    i.enabled=True
                    i.update_xml()
                i_index+=1
                # TODO this isn't saving the models, instead it's creating a new model
                # everytime I think
        else:
            print "unknown post"
        #event_to_remove = request.POST.getall('delEvent')]
        #elif if len(event_to_remove) > 0:
        #    ls.delEvent(
    task_order, task_updates = process_completed_tasks()
    return dict(model=dm, name=mdig.version_string,
            repo_location=mdig.repository.db,
            task_order = task_order, task_updates= task_updates)

@route('/models/:model/instances/:instance',method='GET')
@route('/models/:model/instances/:instance',method='POST')
@view('instance.tpl')
@validate(instance=int, model=validate_model_name)
def show_instance(model,instance):
    dm=model
    idx = int(instance)
    instance = dm.get_instances()[idx]
    if request.method=="POST":
        #to_enable = [int(x) for x in request.POST.getall('enabled')]
        pass

    task_order, task_updates = process_completed_tasks()
    return dict(idx=idx, instance=instance, name=mdig.version_string,
            repo_location=mdig.repository.db,
            task_order=task_order, task_updates = task_updates)

def mdig_launcher(work_q,results_q):
    running = True
    # Have to replace some of the environment variables, otherwise they get
    # remembered and recreating GRASSInterface is no use!
    g = GRASSInterface.get_g()
    g.init_pid_specific_files()
    g.grass_vars["MAPSET"] = "PERMANENT"
    g.set_gis_env()
    while running:
        try:
            s = work_q.get(timeout=1)
            print s
            if s[0] == "SHUTDOWN": running = False
            elif s[0] == "RUN":
                #TODO actually launch MDiG actions
                s[2] = "started"
                m_name = s[1]
                model_file = mdig.repository.get_models()[m_name]
                #import pdb;
                #pdb.Pdb(stdin=open('/dev/stdin', 'r+'), stdout=open('/dev/stdout', 'r+')).set_trace()
                dm = DispersalModel(model_file)
                results_q.put(s)
                dm.run()
                s[2] = "complete"
                results_q.put(s)
            else:
                results_q.put(s)
            work_q.task_done()
        except q.Empty:
            pass

class ResultMonitor(Thread):
    def __init__ (self, result_q):
        Thread.__init__(self)
        self.result_q = result_q
        self.running = False

    def run(self):
        self.running = True
        global models_in_queue
        while self.running:
            try:
                s = self.result_q.get(timeout=1)
                m_action = s[0]
                m_name = s[1]
                m_status = s[2]
                print models_in_queue
                if m_status == "started":
                    models_in_queue[m_name][m_action][m_status] = datetime.datetime.now()
                elif m_status == "complete":
                    models_in_queue[m_name][m_action]["complete"] = datetime.datetime.now()
                print models_in_queue
            except q.Empty:
                pass
        
# This thread monitors the results_q and updates the local process status (since
# there is no easy other way except processing the queues on HTTP requests, and
# this would potentially lead to slow responsiveness).
rt = ResultMonitor(results_q)
# spawn a thread with mdig.py and use a multiprocessing queue
mdig_launcher = Process(target=mdig_launcher, args=(work_q,results_q))

def start_web_service():
    change_to_web_mapset()
    rt.start()
    mdig_launcher.start()

    # setup and run webapp
    global app; app = bottle.app()
    app.catchall = False
    import paste.evalexception
    myapp = paste.evalexception.middleware.EvalException(app)
    c = MDiGConfig.get_config()
    run(app=myapp, host=c["WEB"]["host"], port=c["WEB"]["port"], reloader=reloader)

# Store the web mapsets that have been created so that we can tidy up afterwards
mapsets = {} # indexed by location
def change_to_web_mapset():
    g = GRASSInterface.get_g(create=False)
    ms = "mdig_webservice"
    if not g.check_mapset(ms):
        g.change_mapset(ms, create=True)
        mapsets[g.grass_vars["LOCATION_NAME"]] = ms
    else: g.change_mapset(ms)

def shutdown_webapp():
    if app is None: return
    print "TODO: delete temporary webservice files, " + \
            "stop result monitor and join mdig child process"
    rt.running = False
    work_q.put(["SHUTDOWN","now please"])
    mdig_launcher.join()

