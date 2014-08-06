# coding: utf-8
'''
Created on 2014年8月5日

@author: lunatic
'''
import json
import os
import hashlib
import logging
import sys
from settings import Compiler, Output, Input, Target


'''
规则是：
1）如果这个工程没有编译过，那么我们的所有C 文件都要编译并被链接。
2）如果这个工程的某几个C 文件被修改，那么我们只编译被修改的C 文件，并链接目标程序。
3）如果这个工程的头文件被改变了，那么我们需要编译引用了这几个头文件的C 文件，并链接目标程序。
'''



MAKE_FILE = '.mk'
# HEAD_REGEX = r'^#include "(\w+.h)"$'

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
ch.setLevel(logging.DEBUG)
logger.addHandler(ch)

def get_logger(cls, name):
    # create logger with 'spam_application'
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    # create file handler which logs even debug messages
    fh = logging.FileHandler(name + '.log')
    fh.setLevel(logging.DEBUG)
    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger
    
class Recorder(object):

    def write(self, data={}):
        with open(MAKE_FILE, "w") as f:
            f.write(json.dumps(data));
            
    def update(self, data={}):    
        self.write(data)
        
    def read(self):
        if not os.path.exists(MAKE_FILE):
            return dict()
        with open(MAKE_FILE, "r") as f:
            return json.loads(f.read())    


class Compile(object):
    # g++ -O0 -g3 -Wall -c -fmessage-length=0 
    COMPILE_CMD = '%(name)s -O%(opt)s -g%(debug)s %(warn)s -c %(other)s -o %(out)s %(input)s'
    LINK_CMD = '%(name)s -o %(target)s %(inputs)s'
    def __init__(self):
        self.command = {}
        self.command['name'] = Compiler['name']
        
        opt = Compiler.get('optimization')
        deb = Compiler.get('debugging')
        warn = Compiler.get('warning')
        other = Compiler.get('other')
        
        self.command['opt'] = opt if opt else 0
        self.command['debug'] = deb if deb else 0
        self.command['warn'] = '-Wall' if warn and warn == True else ''
        self.command['other'] = other if other else ''
        
    def __str__(self, *args, **kwargs):
        out = lambda arg: os.path.join(Output, arg.split('.')[0] + '.o')
        _input = lambda arg: os.path.join(Input, arg)
        
        tasks = []
        for arg in args:
            self.command['out'] = out(arg)
            self.command['input'] = _input(arg)
            tasks.append(self.COMPILE_CMD % self.command)

        self.command['inputs'] = ' '.join(map(out, args))
        self.command.update(kwargs)
        tasks.append(self.LINK_CMD %  self.command)
        return tasks
         

def get_content(fn):
    with open(fn, "r") as f:
        content = f.read()
    return (fn, content)

        
class HeadSet(object):
    def __init__(self):
        self.table = dict()
    
    def add_refs(self, fn, relfns_iter):
        self.table[fn] = set(relfns_iter)
    
    def adjust_refs(self):
        self.passed = set()
        for doth in self.table.keys():
            self.passed.clear()
            self.table[doth] = self.__adjust(doth)
            
    def __adjust(self, doth):
        # check processed return empty list 
        # logger.debug(doth, self.passed
        if doth in self.passed:
            return list()
        refs = self.search_refs(doth)
        # maybe sytanx error!
        if refs.__len__() == 0:
            return list()
        dotcc = filter(lambda it: it.endswith('.cc'), refs)
        doths = filter(lambda it: it.endswith('.h'), refs)
        # add passed
        self.passed.add(doth)
        if doths.__len__():
            for ls in [self.__adjust(doth) for doth in doths]:
                dotcc.extend(ls)
        # return set(dotcc)  # filter distinct
        return dotcc
        
        
    def search_refs(self, fn):
        refs = self.table.get(fn)
        return refs if refs else set()
        
        
    
def get_diffs(hs=HeadSet(), _dir='.', origin={}):
    # os.path.walk(top, func, arg)
    # get_content = lambda x: with open(x, "r") as f.read()
    logger.debug(os.listdir(_dir))
    name_conts = [get_content(name) for name in os.listdir(_dir) if name.endswith('.h') or name.endswith('.cc')]
    logger.debug('files: %s' % str(zip(*name_conts)[0]))
    # get head files
    head_files = zip(*filter(lambda (name, _): name.endswith('.h'), name_conts))[0]
    for hf in head_files:
        include = '#include "%s"' % hf
        # [k, v for k, v in name_conts if k != name]
        # relfs = zip(*filter(lambda (name, cont): name != hf and cont.find(include) != -1, name_conts))[0]
        relfs = zip(*filter(lambda (name, cont): cont.find(include) != -1, name_conts))[0]
        # logger.debug('rels', relfs
        hs.add_refs(hf, relfs)
        
    hs.adjust_refs()
    logger.debug('adjust: %s' % str(hs.table))
    
    prints = [(name, hashlib.sha1(cont).hexdigest()) for name, cont in name_conts]

    eq = lambda (name, pin): origin.get(name) != pin
    diff_files = zip(*filter(eq, prints))[0]
    
    logger.debug('diff: %s' % str(diff_files))
    
    compiles = list(filter(lambda name: name.endswith('.cc'), diff_files))
    logger.debug('will: %s' % str(compiles))
    
    diff_hfiles = filter(lambda name: name.endswith('.h'), diff_files)
    logger.debug('h will: %s' % str(diff_hfiles))
    
    for difls in [hs.search_refs(hf) for hf in diff_hfiles]:
        compiles.extend(difls)
        
    logger.debug('compiles: %s' % str(set(compiles)))
    
    return set(compiles)

    
def execute(tasks=[]):
    doit = lambda task: os.popen(task).read()
    return '\n'.join(map(doit, tasks))    

def main(*args, **kwargs):
    pass

if __name__ == '__main__':
#     data = fingerprint()
#     logger.debug(data
#     recorder = Recorder()
#     recorder.write(data)
#     logger.debug(re.findall(HEAD_REGEX, getstring("main.cc"), re.M)
    # data = deserialize()
#     fingerprint()
#     s = os.popen('ls -al').read()
    tasks = Compile().__str__(*Target['hello.exe'], target = 'hello.exe')
    rv = execute(tasks)
    print rv
    logger.debug('end')
    
