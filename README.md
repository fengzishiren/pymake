pymake
======


pymake是一个可以替代make的C/C++自动化构建工具
向make、ant、maven、gradle致敬

##pymake具体做什么？

* 通过build.mk文件自动构建项目
* 每次构建的特征数据以json格式存储在.rmk(取remark的缩写)文件
* 控制台仅仅会输出构建项目中的编译命令
* 项目构建的详细日志输出至文件mk.log

#pymake的特点
完全自动化编译，会通过记录文件与当前文件进行比对分析智能推导需要编译的各种因文件更新直接或间接影响到的全部文件，
只需要简单的配置就可以完成。其他的事情全部交给pymake自动处理，无需人工介入。


#pymake如何使用：
项目的根目录（也可是其他目录）下建立构建的配置文件build.mk
eg.
```
[basic]
input = src #源代码目录
output = debug #编译输出目录
exesuff = out #构建可执行文件的后缀 eg. exe, out...

[compiler]
cc = g++
cflags = -O0 -g3 -Wall -c -fmessage-length=0
lflags =
#libs = 


[build]
hello = main.cc|parser.cc|lexer.cc|engine.cc|alarm.cc
#test = lexer.cc|engine.cc|alarm.cc

#[run]
#main = hello

#[test]
#main = test

#[clean]

#[make]
#run = run
```
然后执行pymake，其他的事情全部交给pymake来作。


##有问题反馈
在使用中有任何问题，欢迎反馈给我，可以用以下联系方式跟我交流

* 邮件(xiaoyaozi106@163.com
* 微博: [@小疯子诗人(http://weibo.com/fengzishiren/)


#参考
借鉴以下的项目,排名不分先后

* make
* ant
* maven
* gradle

