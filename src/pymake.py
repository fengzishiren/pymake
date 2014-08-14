# coding: utf-8
'''
Created on 2014年8月5日

@author: lunatic
'''
import json
import os
import logging
import ConfigParser
import time


'''
编译所有存在更新的源文件和受引用更新直接或间接影响的源文件以及编译依赖不存在.o文件的源文件
        
        
处理步骤：
    1.提取所有原始文件时间戳信息
    2.和当前目录的文件时间戳进行对比找到更新的文件
    3.通过引用关系推断出直接或间接受到影响的文件
    4.合并编译所需的依赖文件和受到影响的文件
    5.生成编译器命令
    6.执行生成的命令
    7.将最新的时间戳信息保存到文件
'''


__all__ = []
__version__ = 0.1
__date__ = '2014-08-08'
__updated__ = '2014-08-08'

RECORD_FILE = '.rmk'
CONFIG_FILE = 'build.mk'
MAKE_LOG = 'mk.log'
SRC_SUFFIX = ('c', 'cc', 'cpp')

FILE_STAMP = {}
# HEAD_REGEX = r'^#include "(\w+.h)"$'

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
hdr = logging.FileHandler(MAKE_LOG)
hdr.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
hdr.setLevel(logging.DEBUG)
logger.addHandler(hdr)
 
class Config(object):
    @classmethod
    def load_config(cls, cfg=CONFIG_FILE):
        parser = ConfigParser.ConfigParser()
        ret = parser.read(cfg)
        if not ret:
            raise Exception('File Not Found "%s"' % cfg)
        cls.INPUT = parser.get('basic', 'input')
        cls.OUTPUT = parser.get('basic', 'output')
        if not os.path.exists(Config.OUTPUT):
            os.makedirs(Config.OUTPUT)
        suffix = parser.get('basic', 'exesuff')
        cls.COMPILER = {opt: parser.get('compiler', opt) for opt in parser.options('compiler')}
        cls.BUILD = {opt + '.' + suffix: parser.get('build', opt).split('|') for opt in parser.options('build')}
       
    
class Recorder(object):

    def write(self, data={}):
        with open(RECORD_FILE, "w") as f:
            f.write(json.dumps(data));
            
    def update(self, data={}):
        _data = self.read()  
        _data.update(data)
        self.write(_data)
        
    def read(self):
        if not os.path.exists(RECORD_FILE):
            return dict()
        with open(RECORD_FILE, "r") as f:
            return json.loads(f.read())    

        
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
        if doth in self.passed:  # 循环引用
            return list()
        refs = self.search_refs(doth)
        # maybe sytanx error!
        if not refs:
            return list()
        dotcc = filter(is_src, refs)
        doths = filter(lambda it: it.endswith('.h'), refs)
        # add passed
        self.passed.add(doth)
        if doths:
            for ls in [self.__adjust(doth) for doth in doths]:
                dotcc.extend(ls)
        # return set(dotcc)  # filter distinct
        return set(dotcc)  # 间接引用
        
    def search_refs(self, fn):
        refs = self.table.get(fn)
        return refs if refs else set()
        

def get_timestamp(fn):
    return os.path.getmtime(fn)


def get_content(fn):
    with open(fn, "r") as f:
        content = f.read()
    return content


def is_src(name):       
    segs = name.rsplit('.')
    return segs[-1] in SRC_SUFFIX if segs else False        
 
    
def get_diffs(origin, _dir):
    '''
     获取指定目录下所有更新的源文件以及包含更新源文件的源文件
    '''
    logger.debug('Dir: %s', ' '.join(os.listdir(_dir)))
    files = [name for name in os.listdir(_dir) if name.endswith('.h') or is_src(name)]
    logger.debug('List of files: %s' % ' '.join(files))
    # name_conts = [(name, get_content(name)) for name in files]
    prints = {name: get_timestamp(os.path.join(_dir, name)) for name in files}
    global FILE_STAMP
    FILE_STAMP.update(prints)
    # Compare timstamp
    diff_pins = filter(lambda (name, pin): origin.get(name, 0.0) < pin, prints.items())
    if not diff_pins:
        logger.warn('No files changed!')
        return []
    
    diff_files = zip(*diff_pins)[0]
    logger.debug('List of changed files: %s', ' '.join(diff_files))
    # collect src files exclude .h
    compiles = list(filter(is_src, diff_files))
    # create instance of HeadSet
    hs = HeadSet()
    # diff head files
    diff_hfiles = filter(lambda name: name.endswith('.h'), diff_files)
    # ind out all associated files for all the updated header files
    file_conts = [get_content(os.path.join(_dir, name)) for name in files]
    for hf in diff_hfiles:
        include = '#include "%s"' % hf
        rels = filter(lambda cont: cont.find(include) != -1, file_conts)
        if not rels:
            continue
        relfs = zip(*rels)[0]
        # logger.debug('rels', relfs
        hs.add_refs(hf, relfs)
    hs.adjust_refs()
    logger.debug('adjust: %s' % str(hs.table))
    # extend comiles
    for difls in [hs.search_refs(hf) for hf in diff_hfiles]:
        compiles.extend(difls)
    logger.debug('List of affected files: %s', ''.join(set(compiles)))
    # Remove duplicate by dict style
    return {}.fromkeys(compiles).keys()

    
class CommandBuilder(object):
    # g++ -O0 -g3 -Wall -c -fmessage-length=0 
    COMPILE_CMD = '%(cc)s %(cflags)s -o %(out)s %(input)s'
    LINK_CMD = '%(cc)s %(lflags)s -o %(target)s %(inputs)s'
    def __init__(self):
        self.command = Config.COMPILER
        
    def build_commands(self, diffs, target):
        """
        没有需要编译的文件且链接的目标文件已存在则返回空list
        """
        comps = self.__merge(diffs, target)
        out = lambda arg: os.path.join(Config.OUTPUT, arg.split('.')[0] + '.o')
        _in = lambda arg: os.path.join(Config.INPUT, arg)
        adjust = lambda arg: ' '.join(filter(lambda x:x, arg.split(' ')))
 
        tasks = []
        book = set()
        for fn in comps:
            dots = _in(fn)
            doto = out(fn)
            self.command['out'] = doto
            self.command['input'] = dots
            book.add(doto)
            cmd = self.COMPILE_CMD % self.command
            tasks.append(adjust(cmd))
        
        for fn, deps in target.items():
            inputs = set(map(out, deps))
            target = os.path.join(Config.OUTPUT, fn)
            if not [inp for inp in inputs if inp in book] and os.path.exists(target):
                continue
            self.command['inputs'] = ' '.join(inputs)
            self.command['target'] = target
            cmd = self.LINK_CMD % self.command
            tasks.append(adjust(cmd))
        return tasks;
    
    
    def __merge(self, diffs, target):
        '''
        合并受更新影响的文件和编译依赖文件
        依赖文件编译要求： 如果依赖文件没有受到更新影响 而且.o文件存在则什么也不做 否则编译依赖文件
        注意：确定源文件存在
        '''
        comps = diffs
        logger.debug('merge diff and depends')
        depends = set(reduce(lambda x, y: x + y, target.values()))
        logger.debug('depends: %s', ' '.join(depends))

        out = lambda arg: os.path.join(Config.OUTPUT, arg.split('.')[0] + '.o')
        _in = lambda arg: os.path.join(Config.INPUT, arg)

        logger.debug('comps: %s', ' '.join(comps))
        # comps.extend()
        comps.extend([dep for dep in depends if self.__exists_src(_in(dep)) and dep not in diffs and not os.path.exists(out(dep))])
        logger.debug('extend comps: %s', ' '.join(comps))
        return comps    
    
    def __exists_src(self, dots):
        if not os.path.exists(dots):
            raise Exception('File Not Found "%s"' % dots)
        return True
            

def execute(cmds=[]):
    doit = lambda cmd: os.popen(say(cmd)).read()
    # doit = lambda x:say(x)
    return map(doit, cmds)    


def say(x):
    print x
    logger.debug(x)
    return x


def main(*args, **kwargs):
    Config.load_config()
    recorder = Recorder()
    builder = CommandBuilder()
    origin = recorder.read()
    diffs = get_diffs(origin, Config.INPUT)
    cmds = builder.build_commands(diffs, Config.BUILD)
    # tasks, upfiles = CommandBuilder().__get_comand(diffs, *TARGET['hello.exe'], target='hello.exe')
    execute(cmds)
#     print 'rv:\n', rv, '\n'
    recorder.update(FILE_STAMP)


if __name__ == '__main__':
    logger.debug('make start')
    try:
        start = time.time()
        main()
        print 'time %.3f' % (time.time() - start)
    except Exception, e:
        logger.exception(e)
        print e
    logger.debug('make end')
    
