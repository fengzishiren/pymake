[basic]
input = src
output = debug
exesuff = out

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


