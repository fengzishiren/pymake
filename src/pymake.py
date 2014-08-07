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
from settings import COMPILER, OUTPUT, INPUT, TARGET


'''
规则是：
1）如果这个工程没有编译过，那么我们的所有C 文件都要编译并被链接。
2）如果这个工程的某几个C 文件被修改，那么我们只编译被修改的C 文件，并链接目标程序。
3）如果这个工程的头文件被改变了，那么我们需要编译引用了这几个头文件的C 文件，并链接目标程序。


更详细的说：
        只编译目标文件依赖的所有文件 （其他文件忽略） 
        如果文件已经编译并且没有再更新过  什么也不做
        如果文件已经编译但有新的更新 重新编译
        如果文件没有编译过 （即.o文件不存在），不管是否更新 编译
'''



MAKE_FILE = '.mk'

FILE_PINS = {}
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
        _data = self.read()  
        _data.update(data)
        self.write(_data)
        
    def read(self):
        if not os.path.exists(MAKE_FILE):
            return dict()
        with open(MAKE_FILE, "r") as f:
            return json.loads(f.read())    

def get_content(fn):
    with open(fn, "r") as f:
        content = f.read()
    return content

        
class HeadSet(object):
    '''
     头文件特殊处理：
    为每个头文件建立一个set set里面放入所有包含了该头文件的文件 如果其中有头文件包含了该头文件 递归的求包含该头文件的源文件 代替头文件本身返回
    '''
    def __init__(self):
        self.table = dict()
    
    def add_refs(self, fn, relfns_iter):
        self.table[fn] = set(relfns_iter)
    
    def adjust_refs(self):
        '''
        调整该结构使得所有的set都不包含头文件 
        '''
        self.passed = set()
        for doth in self.table.keys():
            self.passed.clear()
            self.table[doth] = self.__adjust(doth)
            
    def __adjust(self, doth):
        '''
        获取包含该头文件的所有源文件
        '''
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
        
        
    
def get_diffs(origin={}, _dir=INPUT):
    '''
     获取该目录下所有更新的源文件以及包含更新源文件的源文件
    '''
    # os.path.walk(top, func, arg)
    # get_content = lambda x: with open(x, "r") as f.read()
    logger.debug('Dir: %s', ' '.join(os.listdir(_dir)))
    name_conts = [(name, get_content(os.path.join(_dir, name))) for name in os.listdir(_dir) if name.endswith('.h') or name.endswith('.cc')]
    logger.debug('List of files: %s' % str(zip(*name_conts)[0]))
        
    prints = {name: hashlib.sha1(cont).hexdigest() for name, cont in name_conts}
    # 保存所有文件的最新指纹
    global FILE_PINS
    FILE_PINS.update(prints)
    # 比对原始和最新的指纹 过滤出所有变化的文件
    eq = lambda (name, pin): origin.get(name) != pin
    diff_files = zip(*filter(eq, prints.items()))[0]
    logger.debug('List of changed files: %s', ' '.join(diff_files))
    
    compiles = list(filter(lambda name: name.endswith('.cc'), diff_files))
    diff_hfiles = filter(lambda name: name.endswith('.h'), diff_files)
    # 找出所有更新的头文件的所有关联文件
    hs = HeadSet()
    for hf in diff_hfiles:
        include = '#include "%s"' % hf
        rels = filter(lambda (name, cont): cont.find(include) != -1, name_conts)
        if rels.__len__() == 0:
            continue
        relfs = zip(*rels)[0]
        # logger.debug('rels', relfs
        hs.add_refs(hf, relfs)
    hs.adjust_refs()
    logger.debug('adjust: %s' % str(hs.table))
    
    for difls in [hs.search_refs(hf) for hf in diff_hfiles]:
        compiles.extend(difls)
        
    logger.debug('List of affected files: %s', ''.join(set(compiles)))
    return set(compiles)


class CommandBuilder(object):
    # g++ -O0 -g3 -Wall -c -fmessage-length=0 
    COMPILE_CMD = '%(name)s -O%(opt)s -g%(debug)s %(warn)s -c %(other)s -o %(out)s %(input)s'
    LINK_CMD = '%(name)s -o %(target)s %(inputs)s'
    def __init__(self):
        self.command = {}
        self.command['name'] = COMPILER['name']
        
        opt = COMPILER.get('optimization')
        deb = COMPILER.get('debugging')
        warn = COMPILER.get('warning')
        other = COMPILER.get('other')
        
        self.command['opt'] = opt if opt else 0
        self.command['debug'] = deb if deb else 0
        self.command['warn'] = '-Wall' if warn and warn == True else ''
        self.command['other'] = other if other else ''
        
        self.upfiles = set()
        
    def __get_comand(self, diffs, *depends, **target):
        '''
        生成编译命令的条件：目标文件依赖的源代码文件有变化（包括新建）或者.o文件不存在
        返回有变化且即该次编译依赖的文件名称和编译项目列表
        
        
        只编译目标文件依赖的所有文件 （其他文件忽略） 
        如果文件已经编译并且没有再更新过  什么也不做
        如果文件已经编译但有新的更新 重新编译
        如果文件没有编译过 （即.o文件不存在），不管是否更新 编译
        '''
        out = lambda arg: os.path.join(OUTPUT, arg.split('.')[0] + '.o')
        _in = lambda arg: os.path.join(INPUT, arg)
        
        if not os.path.exists(OUTPUT):
            os.mkdir(OUTPUT)
        if not os.path.exists(INPUT):
            raise Exception('Dir Not Found "%s"' % INPUT)
            
        tasks = []
        for arg in depends:
            dots = _in(arg)
            if not os.path.exists(dots):
                raise Exception('File Not Found "%s"' % dots)
            doto = out(arg)
            if arg in diffs or not os.path.exists(doto):
                # 如果编译依赖的文件在变更的文件当中 就加入更新文件列表
                if arg in diffs:
                    self.upfiles.add(arg) 
                self.command['out'] = doto
                self.command['input'] = dots
                tasks.append(self.COMPILE_CMD % self.command)

        self.command['inputs'] = ' '.join(map(out, depends))
        self.command.update(target)
        
        tasks.append(self.LINK_CMD % self.command)
        return tasks
    
    def build_commands(self, diffs, targets={}):
        '''
                        获取命令列表和待更新的文件列表
        '''
        task_list = [self.__get_comand(diffs, *v, target=k) for k, v in targets.items()]
        body = reduce(lambda x, y: x + y, map(lambda ls: ls[0:-1], task_list))
        tail = reduce(lambda x, y: x + y, map(lambda ls: ls[-1:], task_list))
        # return body + tail
        return ({}.fromkeys(body).keys() + tail, self.upfiles)
    

def execute(tasks=[]):
    # doit = lambda task: os.popen(task).read()
    doit = lambda x:x
    return '\n'.join(map(doit, tasks))    

def say(x):
    print x
    return x

def main(*args, **kwargs):
    recorder = Recorder()
    builder = CommandBuilder()

    origin = recorder.read()
    diffs = get_diffs(origin)
    
    tasks, upfiles = builder.build_commands(diffs, TARGET)
    # tasks, upfiles = CommandBuilder().__get_comand(diffs, *TARGET['hello.exe'], target='hello.exe')
    rv = execute(tasks)
    print 'rv:\n', rv, '\n'
    # 从缓存中提取upfile的指纹
    updata = {name: pin for name, pin in FILE_PINS.items() if name in upfiles}
    print updata
    # recorder.update(updata)

if __name__ == '__main__':
#     data = fingerprint()
#     logger.debug(data

    # recorder.update(updata)
    logger.debug('end')
    
