import re
import struct
import sys
import traceback
import logging
logging.basicConfig(level=logging.DEBUG)
#example grammar:
#
#{
#'packet' : "s'l'\id cmd",
#'cmd' : "l'move'\type s'l'\xtarget s'l'\ytarget|
#	l'stop'\type",
#}
#
#grammar format:
#{
#	<name>: "<term1> <term2>..." #one or more terms separated by spaces
#}
#
#grammar term:
#<type>'<format>'\<identifier>
#or
#<namedTerm>\<identifier>
#type is:
#s : format string for unpacking with struct moduke
#r : string matching a regex
#l : string literal
#
#format:
#type dependent
#either struct format string, or the literal string depending on the type
#
#identifier(optional):
#name the value is stored under in result



class GrammarKeyException(Exception):
	def __init__(self,value):
		self.key = value
		self.args = [value]
	def __str__(self):
		return "Invalid key %s."%self.key

class InvalidToken(Exception):
	def __init__(self,value):
		self.token = value
		self.args = [value]
	def __str__(self):
		return "Token %s didn't match any allowed type"%self.token

literal = re.compile(r"(?P<type>[lsr])'(?P<value>.+)'(/(?P<name>[a-zA-Z_]+))?(?P<multiple>[*+])?$",re.DOTALL)
name = re.compile(r"(?P<value>[a-zA-Z_]*)(/(?P<name>[a-zA-Z_]+))?(?P<multiple>[*+])?$")

def parseSeq(data,position,token):
	offset = len(token['value'])
	logging.debug('sequence test: %s %s'%(token['value'],data[position:position+offset]))
	if token['value'] == data[position:position+offset]:
		return (offset,token['value'])
	raise Exception, 'sequence literal "%s" did not match'%token['value']

def parseRegex(data,position,token):
	logging.debug('testing regex %s'%token['value'])
	match = re.match(token['value'],data[position:])
	if not match:
		raise Exception, 'did not match regex "%s" in sequence'%token['value']
	else:
		offset = match.end()
		return (offset,match.group())

def parseForm(data,position,token):
	offset = struct.calcsize(token['value'])
	logging.debug('parsing %s'%token['value'])
	val = struct.unpack(token['value'],data[position:position+offset])
	logging.debug(str(val))
	if len(val)==1:
		return offset,val[0]
	else:
		return offset, list(val)

tokenTypes = [('literal',literal),('name',name)]
parsers = {'l':parseSeq,'s':parseForm,'r':parseRegex}
def checkToken(token, rexprs):
	logging.debug(token)
	for name, expr in rexprs:
		m = expr.match(token)
		if m:
			gdict = m.groupdict()
			gdict['tokenType'] = name
			mult = gdict['multiple']
			if mult:
				gdict['max'] = sys.maxint
				if mult == '*':
					gdict['min'] = 0
				if mult == '+':
					gdict['min']=1
			else:
				gdict['min']=1
				gdict['max']=1
			if name == 'literal':
				gdict['parser']=parsers[gdict['type']]
				if gdict['type'] == 'r':
					gdict['value'] = re.compile(gdict['value'],re.DOTALL)
			return gdict
	raise InvalidToken(token)

def parseGrammar(gram):
	for key in gram:
		if not name.match(key):
			raise GrammarKeyException(key)
	grammar = {}
	for key in gram:
		keyOptions = [[checkToken(t,tokenTypes) for t in re.split('[ \t]+',x)] for x in gram[key].split("|")]
		grammar[key] = keyOptions
	return grammar



class ResultObj(object):
	def __init__(self,props):
		logging.debug(props)
		for name,val in props:
			setattr(self,name,val)
			#setattr(self,name,property(lambda:val))
		


def parseLiteral(data,position,token):
	return token['parser'](data,position,token)

def parseMultiple(data,position,token,handler):
	offset = 0
	numfound = 0
	min = token['min']
	max = token['max']
	results = []
	while numfound < max:
		try:
			off,val = handler(data,position+offset,token)
			offset+=off
			results.append(val)
			numfound+=1
		except Exception as e:
			logging.warn(e)
			break
	if numfound<min:
		raise Exception, 'did not match'
	if max<=1:
		if numfound==0:
			return offset,None
		else:
			return offset,results[0]
	return offset,results

def parseData(grammar,node,data,position):
	logging.debug('node %s'%node)
	for option in grammar[node]:
		offset = 0
		elms = []
		try:
			logging.debug(option)
			for token in option:
				type=token['tokenType']	
				if type == 'literal':
					off,val = parseMultiple(data,position+offset,token,lambda d,p,t:parseLiteral(d,p,t))
					if token['name']:
						elms.append((token['name'],val))
					offset+=off
				if type == 'name':
					off,val = parseMultiple(data,position+offset,token,lambda d,p,t:parseData(grammar,token['value'],d,p))
					offset+=off
					if token['name']:
						elms.append((token['name'],val))
					else:
						elms.append((token['value'],val))
			return offset,ResultObj(elms)
		except Exception as e:
			logging.warn(traceback.format_exc(limit=None,chain=True))
			logging.warn(e)
	raise Exception, "data did not match grammar"

def makeGrammar(gramDict,startname):
	grammar = parseGrammar(gramDict)
	print grammar
	print ''
	print ''
	def parse(data):
		off,val = parseData(grammar,startname,data,0)
		return val
	return parse
	
