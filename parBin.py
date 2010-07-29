import re
import struct
import sys
import traceback
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

literal = re.compile(r"(?P<type>[lsr])'(?P<value>.+)'(/(?P<name>[a-zA-Z_]+))?(?P<multiple>[*+])?$")
name = re.compile(r"(?P<value>[a-zA-Z_]*)(/(?P<name>[a-zA-Z_]+))?(?P<multiple>[*+])?$")

def parseSeq(data,position,token):
	offset = len(token['value'])
	print 'sequence test:',token['value'],data[position:position+offset]
	if token['value'] == data[position:position+offset]:
		return (offset,token['value'])
	raise Exception, 'sequence literal did not match'

def parseRegex(data,position,token):
	match = re.match(token['value'],data[position:])
	if not match:
		raise Exception, 'did not match regex in sequence'
	else:
		offset = match.end
		return (offset,match.group())

def parseForm(data,position,token):
	offset = struct.calcsize(token['value'])
	print 'parsing',token['value']
	val = struct.unpack(token['value'],data[position:position+offset])
	print val
	if len(val)==1:
		return offset,val[0]
	else:
		return offset, list(val)

tokenTypes = [('literal',literal),('name',name)]
parsers = {'l':parseSeq,'s':parseForm,'r':parseRegex}
def checkToken(token, rexprs):
	print token
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
			return gdict
	raise InvalidToken(token)

def parseGrammar(gram):
	for key in gram:
		if not name.match(key):
			raise GrammarKeyException(key)
	grammar = {}
	for key in gram:
		keyOptions = [[checkToken(t,tokenTypes) for t in x.split()] for x in gram[key].split("|")]
		grammar[key] = keyOptions
	return grammar



class ResultObj(object):
	def __init__(self,props):
		print props
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
			print e
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
	print 'node',node
	for option in grammar[node]:
		offset = 0
		elms = []
		try:
			print option
			for token in option:
				type=token['tokenType']	
				if type == 'literal':
					off,val = parseMultiple(data,position+offset,token,lambda d,p,t:parseLiteral(d,p,t))
					print 'reached'
					if token['name']:
						elms.append((token['name'],val))
					offset+=off
					print 'reached',val
				if type == 'name':
					off,val = parseMultiple(data,position+offset,token,lambda d,p,t:parseData(grammar,token['value'],d,p))
					offset+=off
					if token['name']:
						elms.append((token['name'],val))
					else:
						elms.append((token['value'],val))
			return offset,ResultObj(elms)
		except Exception as e:
			traceback.print_exc()
			print e,2
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
	
