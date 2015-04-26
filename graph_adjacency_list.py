#!/usr/bin/env python

import sys, re, optparse

__doc__="""

Provides functionality for generating a directed graph (in the form of a graphviz DOT file or yEd graphml file) from a properties file with the format:

  SOURCE_NODE=ADJACENT_NODE_1,ADJACENT_NODE_2,etc

For more information on graphviz, see http://www.graphviz.org. For more information on yEd, see http://www.yworks.com/en/products/yfiles/yed/

"""

class Node(object):

    def __init__(self, name):
        self.color=None
        self.name=name
        self.out_edges=[]
        self.in_edges=[]
        self.printed=False

    def add_out_edge(self, out_node):
        self.out_edges.append(out_node)
        out_node.add_in_edge(self)

    def add_in_edge(self, in_node):
        self.in_edges.append(in_node)


class AdjacencyGraph(object):

    def __init__(self):
        self.nodes=[]

    def parseFile(self, inputFile):
        for line in inputFile:
            self.parseLine(line)


    def parseLine(self, line):
        matchPair = self.matchLine(line)

        if not matchPair:
            return

        src = self.makeNode(matchPair[0])
        self.nodes.append(src)

        for x in matchPair[1]:
            dest = self.makeNode(x)
            if not dest == src:
                src.add_out_edge(dest)
                self.nodes.append(dest)


    def matchLine(self, line):
        kv = line.strip().split('=')
        vals = []

        if len(kv) ==0:
            return None
        elif len(kv) > 1:
            vals = kv[1].split(',')

        return (kv[0], vals)

    

    def makeNode(self, name):
        f = filter(lambda y: y.name == name, self.nodes)

        if len(f) == 0:
            n = Node(name)
            return n
        else: 
            return f[0]



class Font(object):
    """
    Simple font struct
    """

    def __init__(self, label, size):
        self.label=label
        self.size=size



class GraphPrinter(object):
    """
    Base class for graph printing.
    """

    def __init__(self, root, suppressRoots=False):
        self.root=root
        self.suppressRoots=suppressRoots


    def printGraph(self, graph, file):
        self.printGraphHeader(file)

        root_filter = lambda x: len(x.in_edges) == 0

        if self.root:
            root_filter = lambda x: x.name == self.root

        for n in filter(root_filter, graph.nodes):
            self.printNode(n, file, self.suppressRoots)

        self.printGraphFooter(file)



    def makeNodeName(self, name):
        return '%s' % (name)





class GraphmlPrinter(GraphPrinter):
    """
    Print a graph in GraphML, compatible with yEd.
    """

    def printGraphFooter(self, file):
        file.write('</graph></graphml>');

    def printGraphHeader(self, file):

        xml_header="""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<graphml xmlns=\"http://graphml.graphdrawing.org/xmlns\"  
    xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\"
    xmlns:y=\"http://www.yworks.com/xml/graphml\"
    xsi:schemaLocation=\"http://graphml.graphdrawing.org/xmlns http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd\">
        <key for="node" id="d1" yfiles.type="nodegraphics"/>
        <graph id="G" edgedefault="directed">
        """
        file.write(xml_header)


    def printEdge(self, file, fromNode, toNode):
        file.write('<edge source="%s" target="%s"/>' % (fromNode, toNode))

    def printNode(self, node, file, skipNode=False):
        if node.printed:
            return

        node.printed=True
        nodeName=self.makeNodeName(node.name)

        nodeXml="""<node id="%s"><data key="d1">
        <y:ShapeNode>
          <y:Shape type="rectangle"/>                              <!-- node shape -->
          <y:Geometry height="30.0" width="60.0" x="0.0" y="0.0"/> <!-- position and size -->
          <y:Fill color="#FFCC00" transparent="false"/>            <!-- fill color -->
          <y:BorderStyle color="#000000" type="line" width="1.0"/> <!-- border -->
          <y:NodeLabel>%s</y:NodeLabel>                    <!-- label text -->
        </y:ShapeNode>
      </data></node>"""

        if not skipNode:
            file.write(nodeXml % (nodeName, nodeName))

        for x in node.out_edges:
            self.printNode(x, file)
            # if we're skipping this node, we don't need its out edges either
            if not skipNode:
                nodeFrom=nodeName
                nodeTo=self.makeNodeName(x.name)
                self.printEdge(file, nodeFrom, nodeTo)



class DotPrinter(GraphPrinter):
    """
    Prints a directed graph in the graphviz DOT format.  There are external libraries to do this task,
    but the goal here was to keep this script relatively simple and free of dependencies.
    """

    def __init__(self, root, suppressRoots=False):
        super(DotPrinter, self).__init__(root, suppressRoots)

        self.colors={}
        self.colors['background']='white'
        self.fonts={}
        self.fonts['edge']=Font('Helvetica', 10)
        self.fonts['edgeLabel']=Font('Helvetica', 10)
        self.fonts['node']=Font('Helvetica', 10)
        self.graphName='G'
        self.rankDir='LR'
        self.rankSep=1
        self.nodeShape='record'
        self.nodeStyle='filled'
        self.edgeArrowHead='normal'
        self.edgeArrowTail='none'


    def printGraphFooter(self, file):
        file.write('}\n')


    def printGraphHeader(self, file):
        file.write('digraph %s {\n' % (self.graphName));

        edgeFmt=(self.fonts['edge'].label, self.fonts['edge'].size, self.fonts['edgeLabel'].label, self.fonts['edgeLabel'].size) 
        file.write('edge [fontname="%s",fontsize=%d,labelfontname="%s",labelfontsize=%d];\n' % edgeFmt)

        nodeFmt=(self.fonts['node'].label, self.fonts['node'].size, self.nodeShape, self.nodeStyle)
        file.write('node [fontname="%s",fontsize=%d,shape=%s, style=%s];\n' % nodeFmt)

        graphFmt=(self.rankDir, self.rankSep, self.colors['background'])
        file.write('rankdir=%s;\nranksep=%d;\nbgcolor=%s;\n' % graphFmt)
                  

    def printNode(self, node, file, skipNode=False):
        if node.printed:
            return

        node.printed=True
        nodeColor = 'green'
        sep=","
        nodeName=self.makeNodeName(node.name)

        if not skipNode:
            file.write('\n  %s [label="%s"  fillcolor=%s ];\n' % (nodeName, node.name, nodeColor))

        for x in node.out_edges:
            self.printNode(x, file)
            # if we're skipping this node, we don't need its out edges either
            if not skipNode:
                nodeFrom=nodeName
                nodeTo=self.makeNodeName(x.name)
                file.write('\n  %s -> %s [arrowhead=%s,arrowtail=%s];\n' % (nodeFrom, nodeTo, self.edgeArrowHead, self.edgeArrowTail))



if __name__=='__main__':

    usage="""usage: %prog [options] INPUT_FILE_NAME

Takes an input file representing a directed graph in a simple Java-style properties file, where each line represents a source node and its out-edges using the format:

SOURCE_NODE_ID=TARGET_NODE_ID_1,TARGET_NODE_ID_2,...,TARGET_NODE_ID_N

The program can print its output in Graphviz 'dot' format, or in GraphML format (compatible with yEd)."""

    op = optparse.OptionParser(usage=usage)
    op.add_option("-o", dest="output_file", default=None, help="Output file name (stdout by default)")
    op.add_option("--root", dest="root_node", default=None, help="Identifier of root node (otherwise, autodetect roots)")
    op.add_option("--suppress-roots", dest="suppress_roots", action="store_true", default=False, help="Suppress printing of root nodes")
    op.add_option("--format", dest="format", default='dot', help="Output format, must be one of 'dot' or 'graphml'")

    (options, args) = op.parse_args()

    if not args:
        op.error("You must specify an input file. Use -h option to display help message.")
    elif len(args) > 1:
        op.error("You cannot specify more than one input file. Use -h option to display help message.")

    root = options.root_node
    suppressRoots = options.suppress_roots

    inputFile = open(args[0], 'r')
    outputFile = sys.stdout

    if options.output_file:
        if options.output_file == args[0]:
            op.error("You may not specify the same file name (%s) as both input and output file." % options.output_file)
        outputFile = open(options.output_file, 'w')

    printer = None
    if options.format == 'dot':
        printer = DotPrinter(root, suppressRoots)
    elif options.format == 'graphml':
        printer = GraphmlPrinter(root, suppressRoots)
    else:
        op.error("Invalid format '%s'. Use -h option to display help message." % options.format)

    graph = AdjacencyGraph()
    graph.parseFile(inputFile)
    inputFile.close()
    printer.printGraph(graph, outputFile)
    outputFile.close()

